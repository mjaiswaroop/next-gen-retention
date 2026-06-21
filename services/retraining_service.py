"""
services/retraining_service.py — Automated ML Retraining Pipeline
==================================================================
Implements Section 1.1: Scheduled 7-day retraining with per-tenant
versioned model artifacts and AUC-ROC gated promotion.

Key behaviours:
- Loads fresh data from DuckDB/SQLite for the target tenant
- Trains XGBoost classifier with class-imbalance handling (scale_pos_weight)
- Computes full classification metrics: accuracy, f1, auc_roc, precision, recall
- Compares AUC-ROC against current active model (must improve by ≥1%)
- If improvement threshold met: saves versioned artifact, promotes in registry
- If not met: keeps old model, logs warning, saves artifact for audit only
- Supports per-tenant independent model versions (Merchant A ≠ Merchant B)
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score, precision_score, recall_score
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("retention_core.retraining")

FEATURES = [
    "recency_days", "frequency", "monetary_value",
    "session_failures", "payment_friction_index", "active_support_tickets",
]
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)

AUC_IMPROVEMENT_THRESHOLD = 0.01  # ≥1% improvement required for promotion


def _load_training_data(tenant_id: int) -> pd.DataFrame:
    """Load all non-deleted customers for this tenant from SQLite."""
    from database import SessionLocal
    from repositories.customer_repo import CustomerRepository

    db = SessionLocal()
    try:
        repo = CustomerRepository(db)
        df = repo.get_as_dataframe(tenant_id)
        if df.empty:
            return df
        # Label: churned if recency > 30 days (same convention as train_models.py)
        df["churned"] = (df["recency_days"] > 30).astype(int)
        return df
    finally:
        db.close()


def _get_current_active_model(tenant_id: int) -> Optional[dict]:
    """Returns dict of the currently active model registry entry, or None."""
    from database import SessionLocal
    from models import ModelRegistry
    from sqlalchemy import and_

    db = SessionLocal()
    try:
        record = (
            db.query(ModelRegistry)
            .filter(and_(
                ModelRegistry.tenant_id == tenant_id,
                ModelRegistry.is_active == True
            ))
            .first()
        )
        if not record:
            return None
        return {
            "model_id": record.model_id,
            "auc_roc": record.auc_roc,
            "version": record.version,
            "artifact_path": record.artifact_path,
        }
    finally:
        db.close()


def _get_next_version(tenant_id: int) -> int:
    """Returns the next sequential version number for this tenant."""
    from database import SessionLocal
    from models import ModelRegistry
    from sqlalchemy import func

    db = SessionLocal()
    try:
        max_ver = (
            db.query(func.max(ModelRegistry.version))
            .filter(ModelRegistry.tenant_id == tenant_id)
            .scalar()
        )
        return (max_ver or 0) + 1
    finally:
        db.close()


def _register_model(
    tenant_id: int,
    version: int,
    artifact_path: str,
    metrics: dict,
    promote: bool,
    notes: str,
) -> str:
    """Insert a new model_registry row. If promote=True, deactivate all others."""
    from database import SessionLocal
    from models import ModelRegistry

    model_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        if promote:
            # Deactivate all current active models for this tenant
            db.query(ModelRegistry).filter(
                ModelRegistry.tenant_id == tenant_id,
                ModelRegistry.is_active == True,
            ).update({"is_active": False, "updated_at": datetime.now(timezone.utc)})

        entry = ModelRegistry(
            model_id=model_id,
            tenant_id=tenant_id,
            version=version,
            artifact_path=str(artifact_path),
            auc_roc=metrics.get("auc_roc"),
            accuracy=metrics.get("accuracy"),
            f1_score=metrics.get("f1_score"),
            precision=metrics.get("precision"),
            recall=metrics.get("recall"),
            is_active=promote,
            promoted_at=datetime.now(timezone.utc) if promote else None,
            notes=notes,
        )
        db.add(entry)
        db.commit()
        return model_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def retrain_tenant_model(tenant_id: int) -> dict:
    """
    Full retraining pipeline for a single tenant.

    Returns:
        dict with keys: promoted (bool), version (int), metrics (dict), notes (str)
    """
    logger.info("Starting retraining for tenant_id=%d", tenant_id)

    df = _load_training_data(tenant_id)
    if df.empty or len(df) < 50:
        msg = f"Insufficient training data for tenant {tenant_id} (rows={len(df)})"
        logger.warning(msg)
        return {"promoted": False, "version": 0, "metrics": {}, "notes": msg}

    # ── Feature matrix ────────────────────────────────────────────────────────
    available = [f for f in FEATURES if f in df.columns]
    X = df[available].fillna(0).values
    y = df["churned"].values

    # Guard against degenerate label distributions
    if y.sum() == 0 or y.sum() == len(y):
        msg = f"Degenerate labels for tenant {tenant_id}: all samples same class."
        logger.warning(msg)
        return {"promoted": False, "version": 0, "metrics": {}, "notes": msg}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # ── Train XGBoost ─────────────────────────────────────────────────────────
    try:
        import xgboost as xgb
    except ImportError:
        raise RuntimeError("xgboost not installed. Run: pip install xgboost")

    pos_count = y_train.sum()
    neg_count = len(y_train) - pos_count
    scale_pos = neg_count / pos_count if pos_count > 0 else 1.0

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=scale_pos,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        X_train_s, y_train,
        eval_set=[(X_test_s, y_test)],
        verbose=False,
    )

    # ── Evaluate ──────────────────────────────────────────────────────────────
    y_pred = model.predict(X_test_s)
    y_prob = model.predict_proba(X_test_s)[:, 1]

    metrics = {
        "accuracy":  round(float(accuracy_score(y_test, y_pred)), 4),
        "f1_score":  round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "auc_roc":   round(float(roc_auc_score(y_test, y_prob)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall":    round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
    }
    logger.info("New model metrics for tenant %d: %s", tenant_id, metrics)

    # ── Compare vs active model ───────────────────────────────────────────────
    current = _get_current_active_model(tenant_id)
    version = _get_next_version(tenant_id)

    if current is None:
        promote = True
        notes = f"First model for tenant {tenant_id}. Auto-promoted."
        logger.info(notes)
    else:
        old_auc = current["auc_roc"] or 0.0
        delta = metrics["auc_roc"] - old_auc
        if delta >= AUC_IMPROVEMENT_THRESHOLD:
            promote = True
            notes = (
                f"Promoted v{version}: AUC improved {delta:+.4f} "
                f"({old_auc:.4f} → {metrics['auc_roc']:.4f})"
            )
            logger.info(notes)
        else:
            promote = False
            notes = (
                f"Not promoted (AUC delta={delta:+.4f} < {AUC_IMPROVEMENT_THRESHOLD}). "
                f"Keeping v{current['version']}."
            )
            logger.warning(notes)

    # ── Save versioned artifact ───────────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifact_name = f"merchant_{tenant_id}_xgb_v{version}_{ts}.joblib"
    artifact_path = MODEL_DIR / artifact_name

    # Bundle model + scaler so inference needs only one file
    joblib.dump({"model": model, "scaler": scaler, "features": available}, artifact_path)
    logger.info("Saved artifact: %s", artifact_path)

    # Also save as the canonical active path if promoted (backwards compat)
    if promote:
        canonical = MODEL_DIR / f"merchant_{tenant_id}_xgb.joblib"
        joblib.dump({"model": model, "scaler": scaler, "features": available}, canonical)

    # ── Register in DB ────────────────────────────────────────────────────────
    model_id = _register_model(
        tenant_id=tenant_id,
        version=version,
        artifact_path=str(artifact_path),
        metrics=metrics,
        promote=promote,
        notes=notes,
    )

    return {
        "model_id": model_id,
        "promoted": promote,
        "version": version,
        "metrics": metrics,
        "notes": notes,
        "artifact_path": str(artifact_path),
    }


def load_active_model(tenant_id: int) -> Optional[dict]:
    """
    Loads the currently active model bundle for a tenant.
    Returns dict with keys: model, scaler, features — or None if no model exists.
    """
    # Try canonical path first (fastest path)
    canonical = MODEL_DIR / f"merchant_{tenant_id}_xgb.joblib"
    if canonical.exists():
        try:
            return joblib.load(canonical)
        except Exception as e:
            logger.warning("Failed to load canonical model for tenant %d: %s", tenant_id, e)

    # Fallback: look up registry
    current = _get_current_active_model(tenant_id)
    if not current:
        return None
    path = Path(current["artifact_path"])
    if not path.exists():
        logger.error("Model artifact not found on disk: %s", path)
        return None
    try:
        return joblib.load(path)
    except Exception as e:
        logger.error("Failed to load model artifact %s: %s", path, e)
        return None

"""
train_models.py — Machine Learning & Segmentation Engine
========================================================
Trains an XGBoost churn-probability classifier (with class-imbalance
handling) and a K-Means clustering model for customer segmentation.

Outputs
-------
  models/xgb_churn_model.joblib    — serialised XGBoost classifier
  models/kmeans_segments.joblib    — serialised K-Means model
  models/scaler.joblib             — fitted StandardScaler
  models/segment_map.json          — cluster-id → persona-label mapping
  plots/feature_importance.png     — XGBoost feature importance chart
  plots/roc_pr_curves.png          — ROC & Precision-Recall curves
  plots/cluster_scatter.png        — 2-D cluster visualisation

Usage
-----
  python train_models.py
"""

import json
import os
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")                       # headless-safe backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from database import SessionLocal
from repositories.customer_repo import CustomerRepository

def load_training_data(merchant_id: int):
    """Drop-in replacement for: df = pd.read_csv('customers.csv')"""
    db = SessionLocal()
    try:
        df = CustomerRepository(db).get_as_dataframe(merchant_id)
        if not df.empty:
            df["churned"] = (df["recency_days"] > 30).astype(int)
        return df
    finally:
        db.close()

def write_scores_back(merchant_id: int, scored_df):
    """Drop-in replacement for: scored_df.to_csv('scored.csv')"""
    db = SessionLocal()
    try:
        records = scored_df[["user_id", "churn_probability", "segment"]].to_dict("records")
        CustomerRepository(db).bulk_upsert(merchant_id, records)
    finally:
        db.close()

from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────
DATA_PATH = Path("data/customer_features.csv")
MODEL_DIR = Path("models")
PLOT_DIR = Path("plots")

FEATURE_COLS = [
    "recency_days",
    "frequency",
    "monetary_value",
    "session_failures",
    "payment_friction_index",
    "active_support_tickets"
]

# Persona labels for K-Means clusters (ordered by spend descending)
SEGMENT_LABELS = {
    0: "High-Value Loyalists",
    1: "Casual Browsers",
    2: "At-Risk Spenders",
}


# ──────────────────────────────────────────────────────────────────────
# 1. DATA LOADING
# ──────────────────────────────────────────────────────────────────────
def load_data(merchant_id: int) -> pd.DataFrame:
    df = load_training_data(merchant_id)
    if not df.empty:
        print(f"Loaded {len(df):,} customers  |  Churn rate: {df['churned'].mean():.1%}")
    return df


# ──────────────────────────────────────────────────────────────────────
# 2. CHURN CLASSIFIER  (XGBoost)
# ──────────────────────────────────────────────────────────────────────
def train_churn_model(df: pd.DataFrame, merchant_id: int, db: SessionLocal):
    """
    Train an isolated XGBoost Classifier per-tenant using their specific data contract.
    Utilizes scale_pos_weight instead of SMOTE to support native categorical features.
    """
    from models import TenantConfig
    config = db.query(TenantConfig).filter(TenantConfig.tenant_id == merchant_id).first()
    if not config or not config.feature_schema:
        print(f"Skipping ML for {merchant_id}: No feature schema registered.")
        return None, []
        
    schema = config.feature_schema
    all_features = []
    cat_features = []
    
    # ── Map Dtypes based on Schema Contract ──────────────────────────
    for feat in schema.get("core_features", []) + schema.get("custom_features", []):
        fname = feat["name"]
        if fname == "user_id": continue
        
        all_features.append(fname)
        if fname not in df.columns:
            # Handle missing data cleanly if schema out of sync
            df[fname] = np.nan
            
        if feat["dtype"] == "categorical":
            cat_features.append(fname)
            df[fname] = df[fname].astype("category")
        elif feat["dtype"] == "numeric":
            df[fname] = pd.to_numeric(df[fname], errors='coerce')
            
    if not all_features:
        print("No features found to train on.")
        return None, []
        
    X = df[all_features]
    y = df["churned"]

    # ── train / test split ───────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # ── Imbalance Handling (Algorithmic) ─────────────────────────────
    neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
    spw = neg / pos if pos > 0 else 1.0
    print(f"\nClass balance -> Retained: {neg} | Churned: {pos} | SPW: {spw:.2f}")

    # ── XGBoost with Native Categorical Support ──────────────────────
    model = XGBClassifier(
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
        enable_categorical=True,
        scale_pos_weight=spw
    )
    
    # ── hyperparameter tuning ────────────────────────────────────────
    param_dist = {
        'n_estimators': [100, 200],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.05, 0.1]
    }
    
    print(f"\nTraining Tenant-Isolated XGBoost for Merchant {merchant_id}...")
    search = RandomizedSearchCV(
        model,
        param_distributions=param_dist,
        n_iter=5,
        scoring='roc_auc',
        cv=3,
        random_state=42,
        n_jobs=-1,
        verbose=1
    )

    # ── training ─────────────────────────────────────────────────────
    search.fit(X_train, y_train)
    best_model = search.best_estimator_
    print(f"Best params: {search.best_params_}")

    # ── evaluation ───────────────────────────────────────────────────
    y_proba = best_model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    roc_auc = roc_auc_score(y_test, y_proba)
    pr_auc = average_precision_score(y_test, y_proba)
    f1 = f1_score(y_test, y_pred)

    print(f"\n{'-' * 50}")
    print(f"  ROC-AUC          : {roc_auc:.4f}")
    print(f"  PR-AUC           : {pr_auc:.4f}")
    print(f"  F1-Score         : {f1:.4f}")
    print(f"{'-' * 50}")
    
    # ── plots ────────────────────────────────────────────────────────
    _plot_feature_importance(best_model, all_features, merchant_id)
    _plot_roc_pr(y_test, y_proba, merchant_id)

    return best_model, all_features


def _plot_feature_importance(model, feature_names: list[str], merchant_id: int) -> None:
    """Bar chart of XGBoost gain-based feature importances."""
    importances = model.feature_importances_
    idx = np.argsort(importances)

    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Take top 15 features to avoid crowding if schema is huge
    top_n = min(15, len(feature_names))
    idx = idx[-top_n:]
    
    ax.barh(
        [feature_names[i] for i in idx],
        importances[idx],
        color="#6366f1",
        edgecolor="#4338ca",
    )
    ax.set_xlabel("Importance (Gain)")
    ax.set_title(f"XGBoost — Feature Importance (Tenant {merchant_id})")
    plt.tight_layout()
    fig.savefig(PLOT_DIR / f"feature_importance_{merchant_id}.png", dpi=150)
    plt.close(fig)
    print(f"[PLOT] Feature importance plot -> {PLOT_DIR / f'feature_importance_{merchant_id}.png'}")


def _plot_roc_pr(y_true, y_proba, merchant_id: int) -> None:
    """Side-by-side ROC and Precision-Recall curves."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # ROC
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    axes[0].plot(fpr, tpr, color="#6366f1", lw=2,
                 label=f"AUC = {roc_auc_score(y_true, y_proba):.3f}")
    axes[0].plot([0, 1], [0, 1], "--", color="grey")
    axes[0].set(xlabel="FPR", ylabel="TPR", title=f"ROC Curve (Tenant {merchant_id})")
    axes[0].legend(loc="lower right")

    # PR
    prec, rec, _ = precision_recall_curve(y_true, y_proba)
    axes[1].plot(rec, prec, color="#f59e0b", lw=2,
                 label=f"AP = {average_precision_score(y_true, y_proba):.3f}")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Precision-Recall Curve")
    axes[1].legend(loc="upper right")

    plt.tight_layout()
    fig.savefig(PLOT_DIR / "roc_pr_curves.png", dpi=150)
    plt.close(fig)
    print(f"[PLOT] ROC & PR curves -> {PLOT_DIR / 'roc_pr_curves.png'}")


# ──────────────────────────────────────────────────────────────────────
# 3. CUSTOMER SEGMENTATION  (K-Means)
# ──────────────────────────────────────────────────────────────────────
def train_segmentation(df: pd.DataFrame):
    """
    Cluster *active (non-churned)* users into 3 marketing personas
    based on spending & engagement metrics.

    Returns
    -------
    kmeans : fitted KMeans model
    scaler : fitted StandardScaler (needed at inference time)
    seg_map: dict mapping cluster id → human-readable label
    """
    active = df[df["churned"] == 0].copy()
    print(f"\nSegmenting {len(active):,} active users into 3 clusters ...")

    seg_features = [
        "frequency",
        "monetary_value",
        "recency_days"
    ]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(active[seg_features])

    kmeans = KMeans(n_clusters=3, n_init=20, random_state=42)
    active["cluster"] = kmeans.fit_predict(X_scaled)

    # ── assign human-readable labels based on cluster centroids ──────
    centroids_df = pd.DataFrame(
        scaler.inverse_transform(kmeans.cluster_centers_),
        columns=seg_features,
    )
    # Rank clusters by monetary_value descending
    ranked = centroids_df["monetary_value"].sort_values(ascending=False).index.tolist()
    labels = ["High-Value Loyalists", "At-Risk Spenders", "Casual Browsers"]
    seg_map = {int(ranked[i]): labels[i] for i in range(3)}

    active["segment"] = active["cluster"].map(seg_map)

    print("\nCluster Centroids (original scale):")
    centroids_df["label"] = [seg_map[i] for i in range(3)]
    print(centroids_df.to_string(index=False))

    print("\nSegment Sizes:")
    print(active["segment"].value_counts().to_string())

    # ── scatter plot ─────────────────────────────────────────────────
    _plot_clusters(active, seg_map)

    return kmeans, scaler, seg_map


def _plot_clusters(active: pd.DataFrame, seg_map: dict) -> None:
    """2-D scatter: Monetary Value vs. Frequency, coloured by cluster."""
    palette = {"High-Value Loyalists": "#6366f1", "Casual Browsers": "#22c55e",
               "At-Risk Spenders": "#f59e0b"}
    fig, ax = plt.subplots(figsize=(9, 6))
    for label, colour in palette.items():
        mask = active["segment"] == label
        ax.scatter(
            active.loc[mask, "frequency"],
            active.loc[mask, "monetary_value"],
            c=colour, label=label, alpha=0.55, edgecolors="w", s=40,
        )
    ax.set(xlabel="Purchase Frequency", ylabel="Monetary Value ($)",
           title="Customer Segments — Active Users")
    ax.legend()
    plt.tight_layout()
    fig.savefig(PLOT_DIR / "cluster_scatter.png", dpi=150)
    plt.close(fig)
    print(f"[PLOT] Cluster scatter -> {PLOT_DIR / 'cluster_scatter.png'}")


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────
def main() -> None:
    from database import active_tenant_id
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        for merchant_id in [1, 2]:
            active_tenant_id.set(merchant_id)
            print(f"\n=======================================================")
            print(f"  TRAINING FOR MERCHANT {merchant_id}")
            print(f"=======================================================")
            
            df = load_data(merchant_id)
            if df.empty:
                print(f"No data for merchant {merchant_id}, skipping.")
                continue

            xgb_model, all_features = train_churn_model(df, merchant_id, db)
            if not xgb_model:
                continue
                
            kmeans, scaler, seg_map = train_segmentation(df)

            df["churn_probability"] = xgb_model.predict_proba(df[all_features])[:, 1].round(4)
            active_mask = df["churned"] == 0
            seg_features_cols = ["frequency", "monetary_value", "recency_days"]
            df.loc[active_mask, "segment"] = kmeans.predict(
                scaler.transform(df.loc[active_mask, seg_features_cols])
            )
            
            df["segment"] = df["segment"].map(
                lambda x: x if isinstance(x, str) else (seg_map.get(int(x), "Churned") if pd.notna(x) else "Churned")
            )

            # ── persist per-merchant models for live inference ──────────────
            joblib.dump(xgb_model, MODEL_DIR / f"merchant_{merchant_id}_xgb.joblib")
            joblib.dump(kmeans, MODEL_DIR / f"merchant_{merchant_id}_kmeans.joblib")
            joblib.dump(scaler, MODEL_DIR / f"merchant_{merchant_id}_scaler.joblib")
            
            # Save segment map (can be JSON)
            with open(MODEL_DIR / f"merchant_{merchant_id}_segment_map.json", "w") as f:
                json.dump(seg_map, f)
                
            print(f"[MODEL] XGBoost model -> {MODEL_DIR / f'merchant_{merchant_id}_xgb.joblib'}")
            print(f"[MODEL] K-Means model -> {MODEL_DIR / f'merchant_{merchant_id}_kmeans.joblib'}")

            write_scores_back(merchant_id, df)
            print(f"[SAVED] Scored dataset written back to DB for merchant {merchant_id}")

        print(f"\n[OK] Training pipeline complete.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
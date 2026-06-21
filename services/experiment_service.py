"""
services/experiment_service.py — A/B Campaign Experiment Framework
==================================================================
Implements Section 1.4:
- 50/50 random group assignment (A / B) per tenant at risk-threshold crossing
- Stores assignment in experiment_assignments (DuckDB + SQLite)
- Outcome fields populated by a Celery task after 30 days
- Chi-squared test to determine statistical significance (p < 0.05)
- Auto-promotes winning template and logs in experiment_results
"""

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("retention_core.experiments")


def assign_experiment_group(
    customer_id: int,
    tenant_id: int,
) -> str:
    """
    Assigns an at-risk customer to group A or B (50/50 split per tenant).
    Records assignment in experiment_assignments table.

    Returns: 'A' or 'B'
    """
    group = "A" if random.random() < 0.5 else "B"
    template_map = {"A": "v1_rag_standard", "B": "v2_vip_consultation"}
    template = template_map[group]

    from database import SessionLocal
    from models import ExperimentAssignment

    experiment_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        assignment = ExperimentAssignment(
            experiment_id=experiment_id,
            customer_id=customer_id,
            tenant_id=tenant_id,
            group=group,
            template_version=template,
        )
        db.add(assignment)
        db.commit()
        logger.info(
            "Experiment assigned: customer_id=%s, tenant=%d, group=%s, template=%s",
            customer_id, tenant_id, group, template
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return group


def get_active_template(tenant_id: int) -> str:
    """
    Returns the currently active campaign template for a tenant.
    Defaults to 'A' unless a previous experiment auto-promoted 'B'.
    """
    from database import SessionLocal
    from models import TenantConfig

    db = SessionLocal()
    try:
        config = db.query(TenantConfig).filter_by(tenant_id=tenant_id).first()
        return config.active_template if config else "A"
    finally:
        db.close()


def get_email_template(group: str) -> str:
    """
    Returns the template version string for a given group.
    Template A: Standard RAG-generated personalised email
    Template B: VIP Consultation (no financial offer, human success manager)
    """
    templates = {
        "A": "v1_rag_standard",
        "B": "v2_vip_consultation",
    }
    return templates.get(group, "v1_rag_standard")


def update_experiment_outcome(
    customer_id: int,
    tenant_id: int,
    event_type: str,   # "opened" | "clicked" | "churned_7d" | "churned_30d"
    value: bool = True,
) -> None:
    """Updates the outcome fields on an ExperimentAssignment row."""
    from database import SessionLocal
    from models import ExperimentAssignment
    from sqlalchemy import and_, desc

    db = SessionLocal()
    try:
        assignment = (
            db.query(ExperimentAssignment)
            .filter(and_(
                ExperimentAssignment.customer_id == customer_id,
                ExperimentAssignment.tenant_id == tenant_id,
            ))
            .order_by(desc(ExperimentAssignment.assigned_at))
            .first()
        )
        if not assignment:
            return

        field_map = {
            "opened":       "email_opened",
            "clicked":      "email_clicked",
            "churned_7d":   "churned_after_7d",
            "churned_30d":  "churned_after_30d",
        }
        field = field_map.get(event_type)
        if field:
            setattr(assignment, field, value)
            assignment.updated_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def evaluate_experiment(tenant_id: int) -> Optional[dict]:
    """
    Runs chi-squared test on 30-day outcomes for tenant.
    Called by Celery task every 30 days.

    Returns result dict or None if insufficient data.
    Auto-promotes winning template if p < 0.05.
    """
    from scipy.stats import chi2_contingency
    from database import SessionLocal
    from models import ExperimentAssignment, ExperimentResult, TenantConfig

    db = SessionLocal()
    try:
        # Only consider assignments with 30d outcome recorded
        assignments = (
            db.query(ExperimentAssignment)
            .filter(
                ExperimentAssignment.tenant_id == tenant_id,
                ExperimentAssignment.churned_after_30d.isnot(None),
            )
            .all()
        )

        if len(assignments) < 30:
            logger.info(
                "Insufficient data for chi-squared test (tenant=%d, n=%d)",
                tenant_id, len(assignments)
            )
            return None

        # Split by group
        a_rows = [a for a in assignments if a.group == "A"]
        b_rows = [a for a in assignments if a.group == "B"]

        # "Retained" = did NOT churn after 30d
        a_retained = sum(1 for a in a_rows if a.churned_after_30d == False)
        b_retained = sum(1 for a in b_rows if a.churned_after_30d == False)
        a_churned  = len(a_rows) - a_retained
        b_churned  = len(b_rows) - b_retained

        # Contingency table: [[retained_A, churned_A], [retained_B, churned_B]]
        table = [[a_retained, a_churned], [b_retained, b_churned]]
        chi2, p_value, _, _ = chi2_contingency(table)

        if p_value < 0.05:
            winning_group = "A" if a_retained / max(len(a_rows), 1) >= b_retained / max(len(b_rows), 1) else "B"
            auto_promoted = True
            notes = (
                f"Statistically significant result (p={p_value:.4f}). "
                f"Group {winning_group} wins. Auto-promoted."
            )
            logger.info(notes)

            # Promote winning template
            config = db.query(TenantConfig).filter_by(tenant_id=tenant_id).first()
            if config:
                config.active_template = winning_group
                config.updated_at = datetime.now(timezone.utc)
        else:
            winning_group = None
            auto_promoted = False
            notes = (
                f"No statistical significance (p={p_value:.4f}). "
                f"Keeping existing template."
            )
            logger.info(notes)

        # Record result
        result = ExperimentResult(
            result_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            group_a_count=len(a_rows),
            group_b_count=len(b_rows),
            group_a_retained=a_retained,
            group_b_retained=b_retained,
            chi_squared_stat=float(chi2),
            p_value=float(p_value),
            winning_group=winning_group,
            auto_promoted=auto_promoted,
            notes=notes,
        )
        db.add(result)
        db.commit()

        return {
            "tenant_id": tenant_id,
            "p_value": float(p_value),
            "chi2": float(chi2),
            "winning_group": winning_group,
            "auto_promoted": auto_promoted,
            "notes": notes,
        }
    except Exception as e:
        db.rollback()
        logger.error("Experiment evaluation failed for tenant %d: %s", tenant_id, e)
        raise
    finally:
        db.close()

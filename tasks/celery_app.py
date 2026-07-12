"""
tasks/celery_app.py — Celery Application + Beat Schedule
=========================================================
Central Celery configuration for all background tasks.
Broker: Redis (configured via REDIS_URL env var)
Beat schedule: periodic task definitions for all sections.

Usage:
    Start worker:  celery -A tasks.celery_app worker -l info
    Start beat:    celery -A tasks.celery_app beat   -l info
    Combined:      celery -A tasks.celery_app worker -l info -B
"""

from celery import Celery
from celery.schedules import crontab
from config import settings

celery_app = Celery(
    "retention_core",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "tasks.ml_tasks",
        "tasks.integration_tasks",
        "tasks.digest_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # Fair distribution; LLM calls are slow
    task_default_retry_delay=60,
    task_max_retries=3,
    result_expires=86400,           # Results retained 24 hours
)

# ── Beat periodic schedule ─────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Section 1.1: Retrain all tenants every 7 days (Sunday 2 AM UTC)
    "retrain-all-tenants-weekly": {
        "task": "tasks.ml_tasks.retrain_all_tenants_task",
        "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
    },
    # Section 1.2: Drift check every 24 hours (3 AM UTC)
    "drift-evaluation-daily": {
        "task": "tasks.ml_tasks.evaluate_drift_all_tenants_task",
        "schedule": crontab(hour=3, minute=0),
    },
    # Section 1.4: Experiment evaluation every 30 days (1st of month, 4 AM)
    "experiment-evaluation-monthly": {
        "task": "tasks.ml_tasks.evaluate_experiments_all_tenants_task",
        "schedule": crontab(hour=4, minute=0, day_of_month="1"),
    },
    # Section 4.1: Auto-approve stale campaigns every hour
    "auto-approve-campaigns": {
        "task": "tasks.ml_tasks.auto_approve_campaigns_task",
        "schedule": crontab(minute=30),
    },
    # Section 6.3: Zendesk sync every hour
    "zendesk-sync-hourly": {
        "task": "tasks.integration_tasks.poll_zendesk_all_tenants",
        "schedule": crontab(minute=0),
    },
    # Section 6.4: Retry failed outbound webhooks every 15 minutes
    "retry-failed-webhooks": {
        "task": "tasks.integration_tasks.retry_failed_webhooks_task",
        "schedule": crontab(minute="*/15"),
    },
    # Section 9.1: Weekly cohort report (Monday 5 AM UTC)
    "weekly-cohort-report": {
        "task": "tasks.digest_tasks.send_weekly_digest_all_tenants",
        "schedule": crontab(hour=5, minute=0, day_of_week="monday"),
    },
    # Section 9.5: Executive digest (Monday 9 AM UTC)
    "executive-digest-weekly": {
        "task": "tasks.digest_tasks.send_weekly_digest_all_tenants",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    },
}

"""Celery application (section 38). Background jobs so user-facing requests
never block on recommendation refresh, memory summarization, or cleanup.

Run the worker with: celery -A app.tasks.celery_app worker --loglevel=info
Run the beat scheduler (for the periodic schedule below) with:
    celery -A app.tasks.celery_app beat --loglevel=info
(docker-compose's `worker` service runs the worker only; add a `beat` service,
or run `celery ... worker -B` for combined worker+beat in a single-instance
dev/demo setup, before relying on the periodic schedule in production.)
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("lingoadapt", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["app.tasks.jobs"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=200,  # recycle workers periodically to bound memory growth
)

celery_app.conf.beat_schedule = {
    "generate-recommendations-for-active-users": {
        "task": "app.tasks.jobs.generate_recommendations_for_active_users",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "send-due-review-reminders": {
        "task": "app.tasks.jobs.send_due_review_reminders",
        "schedule": crontab(minute=0, hour="9,18"),
    },
    "summarize-recent-learner-activity": {
        "task": "app.tasks.jobs.summarize_recent_learner_activity",
        "schedule": crontab(minute=0, hour=3),
    },
    "cleanup-stale-sessions": {
        "task": "app.tasks.jobs.cleanup_stale_sessions",
        "schedule": crontab(minute=30, hour=3),
    },
}

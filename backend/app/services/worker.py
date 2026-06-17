"""In-process background worker: fires due reminders and dispatches the outbox.

Started from the FastAPI lifespan (real server only) when WISHBOX_ENABLE_WORKER
is true. The single-tick function `run_tick` is pure and unit-testable, so tests
never need the thread running.
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from sqlalchemy.orm import Session

from app import models
from app.core.config import settings
from app.core.database import SessionLocal
from app.services import notifications

_started = False


def _advance_recurrence(reminder: models.Reminder) -> None:
    """Yearly/monthly reminders roll forward; one-offs are marked notified."""
    if reminder.recurrence == "yearly":
        try:
            reminder.reminder_date = reminder.reminder_date.replace(year=reminder.reminder_date.year + 1)
        except ValueError:  # Feb 29 -> Mar 1
            reminder.reminder_date = reminder.reminder_date.replace(year=reminder.reminder_date.year + 1, day=1, month=3)
        reminder.notified = False
    elif reminder.recurrence == "monthly":
        m = reminder.reminder_date.month % 12 + 1
        y = reminder.reminder_date.year + (1 if m == 1 else 0)
        day = min(reminder.reminder_date.day, 28)
        reminder.reminder_date = reminder.reminder_date.replace(year=y, month=m, day=day)
        reminder.notified = False
    else:
        reminder.notified = True


def fire_due_reminders(db: Session, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    due = (
        db.query(models.Reminder)
        .filter(models.Reminder.reminder_date <= today, models.Reminder.notified.is_(False))
        .all()
    )
    for r in due:
        user = db.get(models.User, r.user_id)
        title = f"Reminder: {r.title}"
        body = f"{r.title}" + (f" for {r.recipient_name}" if r.recipient_name else "") + " is coming up. 🎁"
        db.add(models.Notification(
            user_id=r.user_id, type="reminder", title=title, body=body, link="/account",
        ))
        if user and user.email:
            notifications.queue_email(db, user.email, title, body + "\nShop now at WishBox.", user_id=user.id)
        _advance_recurrence(r)
    db.commit()
    return len(due)


def run_tick(db: Session) -> dict:
    """One unit of work: fire reminders, then flush the outbox."""
    fired = fire_due_reminders(db)
    sent = notifications.dispatch_pending(db)
    return {"reminders_fired": fired, "messages_sent": sent}


def _loop():
    while True:
        try:
            db = SessionLocal()
            try:
                run_tick(db)
            finally:
                db.close()
        except Exception as e:  # never let the worker thread die
            print(f"[worker] tick error: {e}")
        time.sleep(max(5, settings.WORKER_INTERVAL_SECONDS))


def start_worker() -> bool:
    """Start the daemon thread once. Returns True if it started."""
    global _started
    if _started or not settings.ENABLE_WORKER:
        return False
    _started = True
    threading.Thread(target=_loop, name="wishbox-worker", daemon=True).start()
    return True

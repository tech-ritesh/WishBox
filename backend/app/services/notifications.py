"""Outbound email/SMS via a local outbox.

Messages are persisted to the OutboxMessage table, then dispatched by the
background worker (or synchronously in tests). With no SMTP/Twilio creds the
dispatcher just prints to the console and marks the row sent — so the whole
flow works offline. Configure creds in .env to send for real.
"""
from __future__ import annotations

import datetime as dt
import smtplib
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app import models
from app.core.config import settings


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --- Queueing ----------------------------------------------------------------
def queue_email(db: Session, to: str, subject: str, body: str, user_id: int | None = None) -> models.OutboxMessage:
    msg = models.OutboxMessage(channel="email", to_address=to, subject=subject, body=body, user_id=user_id)
    db.add(msg)
    return msg


def queue_sms(db: Session, to: str, body: str, user_id: int | None = None) -> models.OutboxMessage:
    msg = models.OutboxMessage(channel="sms", to_address=to, body=body, user_id=user_id)
    db.add(msg)
    return msg


# --- Adapters ----------------------------------------------------------------
def _send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        print(f"[OUTBOX:email] to={to} subject={subject!r}\n{body}\n")  # offline mode
        return
    mime = MIMEText(body, "plain", "utf-8")
    mime["Subject"] = subject or "(no subject)"
    mime["From"] = settings.EMAIL_FROM
    mime["To"] = to
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, [to], mime.as_string())


def _send_sms(to: str, body: str) -> None:
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        print(f"[OUTBOX:sms] to={to}\n{body}\n")  # offline mode
        return
    from twilio.rest import Client  # lazy import; only when configured
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(to=to, from_=settings.TWILIO_FROM_NUMBER, body=body)


# --- Dispatch ----------------------------------------------------------------
def dispatch_pending(db: Session, limit: int = 50) -> int:
    """Send all queued messages. Returns count sent. Safe to call repeatedly."""
    pending = (
        db.query(models.OutboxMessage)
        .filter(models.OutboxMessage.status == "queued")
        .order_by(models.OutboxMessage.id.asc())
        .limit(limit)
        .all()
    )
    sent = 0
    for m in pending:
        try:
            if m.channel == "sms":
                _send_sms(m.to_address, m.body)
            else:
                _send_email(m.to_address, m.subject or "", m.body)
            m.status = "sent"
            m.sent_at = _utcnow()
            sent += 1
        except Exception as e:  # keep the queue moving; record the failure
            m.status = "failed"
            m.error = str(e)[:500]
    db.commit()
    return sent

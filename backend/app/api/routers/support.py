"""Help center (FAQ) + customer support tickets."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.services import notifications

router = APIRouter(tags=["Support"])


# --- FAQ (public) ---
@router.get("/faqs", response_model=List[schemas.FaqOut])
def list_faqs(db: Session = Depends(get_db)):
    return (
        db.query(models.FaqEntry)
        .filter(models.FaqEntry.is_active.is_(True))
        .order_by(models.FaqEntry.sort_order.asc(), models.FaqEntry.id.asc())
        .all()
    )


# --- Tickets ---
@router.get("/support/tickets", response_model=List[schemas.TicketOut])
def my_tickets(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.SupportTicket)
        .options(joinedload(models.SupportTicket.messages))
        .filter(models.SupportTicket.user_id == current_user.id)
        .order_by(models.SupportTicket.created_at.desc())
        .all()
    )


@router.post("/support/tickets", response_model=schemas.TicketOut, status_code=201)
def open_ticket(data: schemas.TicketCreate, current_user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    ticket = models.SupportTicket(
        user_id=current_user.id, subject=data.subject, order_number=data.order_number, status="open",
    )
    db.add(ticket)
    db.flush()
    db.add(models.TicketMessage(ticket_id=ticket.id, user_id=current_user.id, body=data.body, is_staff=False))
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/support/tickets/{ticket_id}/messages", response_model=schemas.TicketOut)
def reply_ticket(ticket_id: int, data: schemas.TicketReply,
                 current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = db.query(models.SupportTicket).filter(
        models.SupportTicket.id == ticket_id, models.SupportTicket.user_id == current_user.id
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    db.add(models.TicketMessage(ticket_id=ticket.id, user_id=current_user.id, body=data.body, is_staff=False))
    ticket.status = "open"
    db.commit()
    db.refresh(ticket)
    return ticket

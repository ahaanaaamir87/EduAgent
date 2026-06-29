from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Note
from app.services import academic_service
from app.services.activity_logger import log_activity

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/notes", response_class=HTMLResponse)
def notes_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    notes = db.query(Note).filter(Note.user_id == user.id).order_by(Note.created_at.desc()).all()
    return templates.TemplateResponse("notes.html", {
        "request": request, "user": user, "active_page": "notes", "notes": notes, "active_note": None,
    })


@router.post("/notes/generate", response_class=HTMLResponse)
def notes_generate(
    request: Request,
    topic: str = Form(...),
    use_rag: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    content = academic_service.generate_notes(user.id, topic, use_rag=use_rag)

    note = Note(user_id=user.id, topic=topic, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)

    log_activity(db, user.id, "notes", topic)

    notes = db.query(Note).filter(Note.user_id == user.id).order_by(Note.created_at.desc()).all()
    return templates.TemplateResponse("notes.html", {
        "request": request, "user": user, "active_page": "notes", "notes": notes, "active_note": note,
    })


@router.get("/notes/{note_id}", response_class=HTMLResponse)
def notes_view(note_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    active_note = db.query(Note).filter(Note.id == note_id, Note.user_id == user.id).first()
    notes = db.query(Note).filter(Note.user_id == user.id).order_by(Note.created_at.desc()).all()
    return templates.TemplateResponse("notes.html", {
        "request": request, "user": user, "active_page": "notes", "notes": notes, "active_note": active_note,
    })

import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import FlashcardSet
from app.services import academic_service
from app.services.activity_logger import log_activity

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/flashcards", response_class=HTMLResponse)
def flashcards_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    sets_ = db.query(FlashcardSet).filter(FlashcardSet.user_id == user.id).order_by(FlashcardSet.created_at.desc()).all()
    return templates.TemplateResponse("flashcards.html", {
        "request": request, "user": user, "active_page": "flashcards", "sets": sets_, "active_set": None,
    })


@router.post("/flashcards/generate", response_class=HTMLResponse)
def flashcards_generate(
    request: Request,
    topic: str = Form(...),
    num_cards: int = Form(8),
    use_rag: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    cards = academic_service.generate_flashcards(user.id, topic, num_cards=num_cards, use_rag=use_rag)

    fc_set = FlashcardSet(user_id=user.id, topic=topic, cards_json=json.dumps(cards))
    db.add(fc_set)
    db.commit()
    db.refresh(fc_set)
    log_activity(db, user.id, "flashcards", topic)

    sets_ = db.query(FlashcardSet).filter(FlashcardSet.user_id == user.id).order_by(FlashcardSet.created_at.desc()).all()
    return templates.TemplateResponse("flashcards.html", {
        "request": request, "user": user, "active_page": "flashcards", "sets": sets_, "active_set": fc_set,
    })


@router.get("/flashcards/{set_id}", response_class=HTMLResponse)
def flashcards_view(set_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    active_set = db.query(FlashcardSet).filter(FlashcardSet.id == set_id, FlashcardSet.user_id == user.id).first()
    sets_ = db.query(FlashcardSet).filter(FlashcardSet.user_id == user.id).order_by(FlashcardSet.created_at.desc()).all()
    return templates.TemplateResponse("flashcards.html", {
        "request": request, "user": user, "active_page": "flashcards", "sets": sets_, "active_set": active_set,
    })

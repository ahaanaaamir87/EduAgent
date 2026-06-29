import datetime as dt
from collections import Counter

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, hash_password, verify_password
from app.models import Activity, ChatMessage, Note, Quiz, FlashcardSet, Assignment, Summary

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    activities = db.query(Activity).filter(Activity.user_id == user.id).all()
    kind_counts = Counter(a.kind for a in activities)
    labels = {
        "chat": "AI Chat", "notes": "Notes Generator", "summarizer": "Summarizer",
        "quiz": "Quiz Generator", "flashcards": "Flashcards", "assignment": "Assignment Helper",
    }
    breakdown = [{"label": labels.get(k, k.title()), "count": v} for k, v in kind_counts.most_common()]

    # last 14 days activity counts for a trend chart
    trend_labels, trend_values = [], []
    for i in range(13, -1, -1):
        d = dt.datetime.utcnow().date() - dt.timedelta(days=i)
        count = sum(1 for a in activities if a.created_at.date() == d)
        trend_labels.append(d.strftime("%d %b"))
        trend_values.append(count)

    totals = {
        "chats": db.query(ChatMessage).filter(ChatMessage.user_id == user.id, ChatMessage.role == "user").count(),
        "notes": db.query(Note).filter(Note.user_id == user.id).count(),
        "summaries": db.query(Summary).filter(Summary.user_id == user.id).count(),
        "quizzes": db.query(Quiz).filter(Quiz.user_id == user.id).count(),
        "flashcard_sets": db.query(FlashcardSet).filter(FlashcardSet.user_id == user.id).count(),
        "assignments": db.query(Assignment).filter(Assignment.user_id == user.id).count(),
    }

    avg_quiz_score = 0
    quizzes = db.query(Quiz).filter(Quiz.user_id == user.id, Quiz.attempts > 0).all()
    if quizzes:
        avg_quiz_score = round(sum(q.best_score for q in quizzes) / len(quizzes))

    return templates.TemplateResponse("analytics.html", {
        "request": request, "user": user, "active_page": "analytics",
        "breakdown": breakdown, "trend_labels": trend_labels, "trend_values": trend_values,
        "totals": totals, "avg_quiz_score": avg_quiz_score,
    })


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    activities = db.query(Activity).filter(Activity.user_id == user.id).order_by(Activity.created_at.desc()).limit(200).all()
    return templates.TemplateResponse("history.html", {
        "request": request, "user": user, "active_page": "history", "activities": activities,
    })


@router.get("/bookmarks", response_class=HTMLResponse)
def bookmarks_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    # Bookmarks reuse Notes for now (a lightweight, working stand-in)
    notes = db.query(Note).filter(Note.user_id == user.id).order_by(Note.created_at.desc()).all()
    return templates.TemplateResponse("bookmarks.html", {
        "request": request, "user": user, "active_page": "bookmarks", "notes": notes,
    })


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "active_page": "settings", "message": None, "error": None,
    })


@router.post("/settings/profile", response_class=HTMLResponse)
def settings_update_profile(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    user.name = name.strip()
    db.commit()
    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "active_page": "settings",
        "message": "Profile updated.", "error": None,
    })


@router.post("/settings/password", response_class=HTMLResponse)
def settings_update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse("settings.html", {
            "request": request, "user": user, "active_page": "settings",
            "message": None, "error": "Current password is incorrect.",
        })

    user.hashed_password = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "active_page": "settings",
        "message": "Password changed successfully.", "error": None,
    })

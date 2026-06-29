import datetime as dt
from collections import Counter

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth import get_current_user
from app.models import ChatMessage, Note, Quiz, Activity, StudyTask, FlashcardSet

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SUBJECT_COLORS = ["#ef4444", "#a855f7", "#3b82f6", "#f59e0b", "#9ca3af", "#10b981"]


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    total_queries = db.query(ChatMessage).filter(
        ChatMessage.user_id == user.id, ChatMessage.role == "user"
    ).count()
    notes_generated = db.query(Note).filter(Note.user_id == user.id).count()
    quizzes_created = db.query(Quiz).filter(Quiz.user_id == user.id).count()

    recent_activities = (
        db.query(Activity)
        .filter(Activity.user_id == user.id)
        .order_by(Activity.created_at.desc())
        .limit(6)
        .all()
    )

    upcoming_tasks = (
        db.query(StudyTask)
        .filter(StudyTask.user_id == user.id, StudyTask.is_done == False)  # noqa: E712
        .order_by(StudyTask.due_date.is_(None), StudyTask.due_date.asc())
        .limit(5)
        .all()
    )

    # Study streak: count consecutive days (including today) with at least one activity
    streak = 0
    day_cursor = dt.datetime.utcnow().date()
    activity_dates = {
        a.created_at.date()
        for a in db.query(Activity).filter(Activity.user_id == user.id).all()
    }
    while day_cursor in activity_dates:
        streak += 1
        day_cursor -= dt.timedelta(days=1)

    week_days = ["M", "T", "W", "T", "F", "S", "S"]
    today_idx = dt.datetime.utcnow().weekday()  # Monday=0
    week_start = dt.datetime.utcnow().date() - dt.timedelta(days=today_idx)
    week_status = []
    for i in range(7):
        d = week_start + dt.timedelta(days=i)
        week_status.append({"label": week_days[i], "active": d in activity_dates, "is_today": d == dt.datetime.utcnow().date()})

    # Top subjects = most common activity "kind" as a stand-in for subject distribution
    kind_counts = Counter(a.kind for a in db.query(Activity).filter(Activity.user_id == user.id).all())
    total_kinds = sum(kind_counts.values()) or 1
    top_subjects = []
    labels = {
        "chat": "AI Chat", "notes": "Notes", "summarizer": "Summarizer",
        "quiz": "Quizzes", "flashcards": "Flashcards", "assignment": "Assignments",
    }
    for i, (kind, count) in enumerate(kind_counts.most_common(6)):
        top_subjects.append({
            "label": labels.get(kind, kind.title()),
            "pct": round(100 * count / total_kinds),
            "color": SUBJECT_COLORS[i % len(SUBJECT_COLORS)],
        })
    if not top_subjects:
        top_subjects = [{"label": "No activity yet", "pct": 100, "color": "#374151"}]

    # Learning overview: queries per day, last 7 days
    chart_labels = []
    chart_values = []
    for i in range(6, -1, -1):
        d = dt.datetime.utcnow().date() - dt.timedelta(days=i)
        count = db.query(Activity).filter(
            Activity.user_id == user.id,
            func.date(Activity.created_at) == d.isoformat(),
        ).count()
        chart_labels.append(d.strftime("%a"))
        chart_values.append(count)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "active_page": "dashboard",
        "stats": {
            "total_queries": total_queries,
            "notes_generated": notes_generated,
            "quizzes_created": quizzes_created,
            "study_hours": round(total_queries * 0.08 + notes_generated * 0.15, 1),
        },
        "recent_activities": recent_activities,
        "upcoming_tasks": upcoming_tasks,
        "streak": streak,
        "week_status": week_status,
        "top_subjects": top_subjects,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
    })

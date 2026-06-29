import datetime as dt

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import StudyTask

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/planner", response_class=HTMLResponse)
def planner_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    tasks = db.query(StudyTask).filter(StudyTask.user_id == user.id).order_by(
        StudyTask.is_done.asc(), StudyTask.due_date.asc()
    ).all()
    return templates.TemplateResponse("planner.html", {
        "request": request, "user": user, "active_page": "planner", "tasks": tasks,
    })


@router.post("/planner/add")
def planner_add(
    request: Request,
    title: str = Form(...),
    subject: str = Form(""),
    due_date: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    due = None
    if due_date:
        try:
            due = dt.datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            due = None

    task = StudyTask(user_id=user.id, title=title, subject=subject, due_date=due)
    db.add(task)
    db.commit()
    return RedirectResponse(url="/planner", status_code=302)


@router.post("/planner/{task_id}/toggle")
def planner_toggle(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == user.id).first()
    if task:
        task.is_done = not task.is_done
        db.commit()
    return RedirectResponse(url="/planner", status_code=302)


@router.post("/planner/{task_id}/delete")
def planner_delete(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == user.id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse(url="/planner", status_code=302)

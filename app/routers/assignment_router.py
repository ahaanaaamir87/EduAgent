from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Assignment
from app.services import academic_service
from app.services.activity_logger import log_activity

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/assignment-helper", response_class=HTMLResponse)
def assignment_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    assignments = db.query(Assignment).filter(Assignment.user_id == user.id).order_by(Assignment.created_at.desc()).all()
    return templates.TemplateResponse("assignment_helper.html", {
        "request": request, "user": user, "active_page": "assignment", "assignments": assignments, "active_assignment": None,
    })


@router.post("/assignment-helper/solve", response_class=HTMLResponse)
def assignment_solve(
    request: Request,
    title: str = Form(""),
    question: str = Form(...),
    use_rag: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    solution = academic_service.solve_assignment(user.id, question, use_rag=use_rag)

    assignment = Assignment(
        user_id=user.id, title=title or question[:80], question=question, solution=solution,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    log_activity(db, user.id, "assignment", title or question[:80])

    assignments = db.query(Assignment).filter(Assignment.user_id == user.id).order_by(Assignment.created_at.desc()).all()
    return templates.TemplateResponse("assignment_helper.html", {
        "request": request, "user": user, "active_page": "assignment",
        "assignments": assignments, "active_assignment": assignment,
    })


@router.get("/assignment-helper/{assignment_id}", response_class=HTMLResponse)
def assignment_view(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    active_assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id, Assignment.user_id == user.id
    ).first()
    assignments = db.query(Assignment).filter(Assignment.user_id == user.id).order_by(Assignment.created_at.desc()).all()
    return templates.TemplateResponse("assignment_helper.html", {
        "request": request, "user": user, "active_page": "assignment",
        "assignments": assignments, "active_assignment": active_assignment,
    })

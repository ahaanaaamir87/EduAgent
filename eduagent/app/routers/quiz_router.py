import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Quiz
from app.services import academic_service
from app.services.activity_logger import log_activity

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/quiz", response_class=HTMLResponse)
def quiz_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    quizzes = db.query(Quiz).filter(Quiz.user_id == user.id).order_by(Quiz.created_at.desc()).all()
    return templates.TemplateResponse("quiz.html", {
        "request": request, "user": user, "active_page": "quiz", "quizzes": quizzes, "active_quiz": None,
    })


@router.post("/quiz/generate", response_class=HTMLResponse)
def quiz_generate(
    request: Request,
    topic: str = Form(...),
    num_questions: int = Form(5),
    difficulty: str = Form("medium"),
    use_rag: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    questions = academic_service.generate_quiz(
        user.id, topic, num_questions=num_questions, difficulty=difficulty, use_rag=use_rag
    )

    quiz = Quiz(
        user_id=user.id, topic=topic, difficulty=difficulty,
        questions_json=json.dumps(questions),
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    log_activity(db, user.id, "quiz", topic)

    quizzes = db.query(Quiz).filter(Quiz.user_id == user.id).order_by(Quiz.created_at.desc()).all()
    return templates.TemplateResponse("quiz.html", {
        "request": request, "user": user, "active_page": "quiz", "quizzes": quizzes, "active_quiz": quiz,
    })


@router.get("/quiz/{quiz_id}", response_class=HTMLResponse)
def quiz_view(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    active_quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user.id).first()
    quizzes = db.query(Quiz).filter(Quiz.user_id == user.id).order_by(Quiz.created_at.desc()).all()
    return templates.TemplateResponse("quiz.html", {
        "request": request, "user": user, "active_page": "quiz", "quizzes": quizzes, "active_quiz": active_quiz,
    })


@router.post("/quiz/{quiz_id}/submit")
def quiz_submit(quiz_id: int, request: Request, answers: str = Form(...), db: Session = Depends(get_db)):
    """answers: JSON string mapping question index -> chosen option index"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user.id).first()
    if not quiz:
        return JSONResponse({"error": "quiz not found"}, status_code=404)

    questions = quiz.questions()
    try:
        chosen = json.loads(answers)
    except Exception:
        return JSONResponse({"error": "invalid answers payload"}, status_code=400)

    correct = 0
    results = []
    for i, q in enumerate(questions):
        chosen_idx = chosen.get(str(i))
        is_correct = chosen_idx == q.get("answer_index")
        if is_correct:
            correct += 1
        results.append({
            "question": q.get("question"),
            "chosen_index": chosen_idx,
            "correct_index": q.get("answer_index"),
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "options": q.get("options", []),
        })

    score_pct = round(100 * correct / len(questions)) if questions else 0
    quiz.attempts = (quiz.attempts or 0) + 1
    quiz.best_score = max(quiz.best_score or 0, score_pct)
    db.commit()

    return JSONResponse({
        "score_pct": score_pct, "correct": correct, "total": len(questions), "results": results,
    })

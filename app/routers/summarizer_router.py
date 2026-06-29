import uuid
from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Summary
from app.services import academic_service, rag_service
from app.services.activity_logger import log_activity
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/summarizer", response_class=HTMLResponse)
def summarizer_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    summaries = db.query(Summary).filter(Summary.user_id == user.id).order_by(Summary.created_at.desc()).all()
    return templates.TemplateResponse("summarizer.html", {
        "request": request, "user": user, "active_page": "summarizer",
        "summaries": summaries, "active_summary": None,
    })


@router.post("/summarizer/text", response_class=HTMLResponse)
def summarize_pasted_text(
    request: Request,
    title: str = Form(""),
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    content = academic_service.summarize_text(user.id, text, title=title)
    summary = Summary(
        user_id=user.id, title=title or "Pasted text", source_type="text",
        original_excerpt=text[:1000], content=content,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    log_activity(db, user.id, "summarizer", title or "Pasted text")

    summaries = db.query(Summary).filter(Summary.user_id == user.id).order_by(Summary.created_at.desc()).all()
    return templates.TemplateResponse("summarizer.html", {
        "request": request, "user": user, "active_page": "summarizer",
        "summaries": summaries, "active_summary": summary,
    })


@router.post("/summarizer/pdf", response_class=HTMLResponse)
async def summarize_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    user_dir = Path(settings.UPLOAD_DIR) / str(user.id) / "summarizer"
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{uuid.uuid4().hex}_{file.filename}"
    dest.write_bytes(await file.read())

    text = rag_service.extract_text(str(dest))
    content = academic_service.summarize_text(user.id, text, title=file.filename)

    summary = Summary(
        user_id=user.id, title=file.filename, source_type="pdf",
        original_excerpt=text[:1000], content=content,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    log_activity(db, user.id, "summarizer", file.filename)

    summaries = db.query(Summary).filter(Summary.user_id == user.id).order_by(Summary.created_at.desc()).all()
    return templates.TemplateResponse("summarizer.html", {
        "request": request, "user": user, "active_page": "summarizer",
        "summaries": summaries, "active_summary": summary,
    })


@router.get("/summarizer/{summary_id}", response_class=HTMLResponse)
def summarizer_view(summary_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    active_summary = db.query(Summary).filter(Summary.id == summary_id, Summary.user_id == user.id).first()
    summaries = db.query(Summary).filter(Summary.user_id == user.id).order_by(Summary.created_at.desc()).all()
    return templates.TemplateResponse("summarizer.html", {
        "request": request, "user": user, "active_page": "summarizer",
        "summaries": summaries, "active_summary": active_summary,
    })

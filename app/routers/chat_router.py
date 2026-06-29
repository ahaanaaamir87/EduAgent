import uuid
from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import ChatMessage, Document
from app.services import academic_service, rag_service
from app.services.activity_logger import log_activity
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    session_id = request.session.get("chat_session_id")
    if not session_id:
        session_id = uuid.uuid4().hex
        request.session["chat_session_id"] = session_id

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    documents = db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).all()

    return templates.TemplateResponse("chat.html", {
        "request": request, "user": user, "active_page": "chat",
        "history": history, "documents": documents,
    })


@router.post("/chat/send")
def chat_send(
    request: Request,
    message: str = Form(...),
    use_rag: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    session_id = request.session.get("chat_session_id") or uuid.uuid4().hex
    request.session["chat_session_id"] = session_id

    prior = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in prior[-12:]]  # cap context window

    user_msg = ChatMessage(user_id=user.id, session_id=session_id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    result = academic_service.chat_answer(user.id, message, history, use_rag=use_rag)

    assistant_msg = ChatMessage(
        user_id=user.id, session_id=session_id, role="assistant",
        content=result["reply"], used_rag=result["used_rag"],
    )
    db.add(assistant_msg)
    db.commit()

    log_activity(db, user.id, "chat", message[:120])

    return JSONResponse({
        "reply": result["reply"],
        "used_rag": result["used_rag"],
    })


@router.post("/chat/upload")
async def chat_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    allowed_ext = {".pdf", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        return JSONResponse({"error": "Only .pdf, .txt, .md files are supported"}, status_code=400)

    user_dir = Path(settings.UPLOAD_DIR) / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{uuid.uuid4().hex}_{file.filename}"
    contents = await file.read()
    dest.write_bytes(contents)

    doc = Document(user_id=user.id, filename=file.filename, filepath=str(dest), num_chunks=0)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        num_chunks = rag_service.ingest_document(user.id, str(dest), doc.id)
        doc.num_chunks = num_chunks
        db.commit()
    except Exception as e:
        return JSONResponse({"error": f"Failed to process document: {e}"}, status_code=500)

    log_activity(db, user.id, "chat", f"Uploaded document: {file.filename}")

    return JSONResponse({
        "id": doc.id, "filename": doc.filename, "num_chunks": doc.num_chunks,
    })


@router.post("/chat/new")
def chat_new_session(request: Request):
    request.session["chat_session_id"] = uuid.uuid4().hex
    return RedirectResponse(url="/chat", status_code=302)

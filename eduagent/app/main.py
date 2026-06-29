"""
EduAgent -- AI Academic Assistant
Main FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings, BASE_DIR
from app.database import engine, Base

# Import routers
from app.routers import (
    auth_router,
    dashboard_router,
    chat_router,
    notes_router,
    summarizer_router,
    quiz_router,
    flashcards_router,
    assignment_router,
    planner_router,
    misc_router,
)
from app.routers import google_auth_router

# Warn loudly (rather than silently falling back to defaults) if .env is missing --
# this has bitten people before when a file got dropped during a copy/zip step.
if not (BASE_DIR / ".env").exists():
    print(
        "\n"
        "  WARNING: no .env file found at the project root.\n"
        "  The app will run on hardcoded defaults (model: 'llama3', host:\n"
        "  'http://localhost:11434', etc.) which may not match what you've\n"
        "  actually pulled in Ollama. Copy .env.example to .env and adjust\n"
        "  it, then restart the server.\n"
    )

# Create all DB tables on startup (simple approach; use Alembic for real migrations)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EduAgent - AI Academic Assistant")

# Sessions (cookie-based login)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Static files (css/js/img)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(chat_router.router)
app.include_router(notes_router.router)
app.include_router(summarizer_router.router)
app.include_router(quiz_router.router)
app.include_router(flashcards_router.router)
app.include_router(assignment_router.router)
app.include_router(planner_router.router)
app.include_router(misc_router.router)
app.include_router(google_auth_router.router)


@app.get("/healthz")
def health_check():
    """Surfaces the active config so you can confirm what model/host the
    app is actually using, e.g. http://localhost:8000/healthz"""
    return {
        "status": "ok",
        "agent_backend": settings.AGENT_BACKEND,
        "chat_model": settings.OLLAMA_CHAT_MODEL,
        "embed_model": settings.OLLAMA_EMBED_MODEL,
        "ollama_host": settings.OLLAMA_HOST,
        "max_tokens": settings.OLLAMA_MAX_TOKENS,
        "env_file_loaded": (BASE_DIR / ".env").exists(),
    }

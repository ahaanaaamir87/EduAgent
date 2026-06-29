"""
Central configuration for EduAgent.
Reads from .env (or real environment variables) using python-dotenv.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # Ollama
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    # Max tokens the model will generate per reply. Lower = faster on CPU.
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "350"))
    # Context window size in tokens. Lower = faster on CPU, less memory.
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "2048"))

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/db/eduagent.db")

    # RAG
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", str(BASE_DIR / "data" / "chroma"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "4"))

    # Agent backend: "local" (Ollama) or "adk" (Google ADK + Gemini)
    AGENT_BACKEND: str = os.getenv("AGENT_BACKEND", "local")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")


settings = Settings()

# Ensure runtime directories exist
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_DIR).mkdir(parents=True, exist_ok=True)
Path(BASE_DIR / "data" / "db").mkdir(parents=True, exist_ok=True)

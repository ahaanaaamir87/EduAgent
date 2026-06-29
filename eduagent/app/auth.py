"""
Authentication helpers: password hashing + simple cookie-session login.

Uses the `bcrypt` library directly (rather than passlib's CryptContext)
because passlib's bcrypt backend has a known compatibility break with
bcrypt>=4.1 (it probes `bcrypt.__about__.__version__`, which was removed,
and its fallback detection path then crashes on a >72-byte test string).
Calling bcrypt directly sidesteps that issue entirely.
"""
import bcrypt
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from app.models import User

# bcrypt has a hard 72-byte limit on the input password; truncate safely
# rather than letting very long passwords raise an error.
_BCRYPT_MAX_BYTES = 72


def _prepare_password_bytes(password: str) -> bytes:
    pw_bytes = password.encode("utf-8")
    return pw_bytes[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    pw_bytes = _prepare_password_bytes(password)
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = _prepare_password_bytes(plain)
    try:
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except ValueError:
        # Malformed/legacy hash in the DB -- treat as non-matching rather than crashing.
        return False


def get_current_user(request: Request, db: Session) -> User | None:
    """Reads user_id from the signed session cookie and loads the User."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request, db: Session) -> User:
    """Like get_current_user but raises 401 if not logged in (for API-style routes)."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

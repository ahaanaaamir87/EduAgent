from sqlalchemy.orm import Session
from app.models import Activity


def log_activity(db: Session, user_id: int, kind: str, title: str):
    activity = Activity(user_id=user_id, kind=kind, title=title[:500])
    db.add(activity)
    db.commit()

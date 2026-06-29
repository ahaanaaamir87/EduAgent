"""
ORM models for EduAgent: users, chat history, notes, summaries,
quizzes, flashcards, assignments, study tasks, documents (RAG sources).
"""
import datetime as dt
import json

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
)
from sqlalchemy.orm import relationship

from app.database import Base


def now():
    return dt.datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="Student")
    created_at = Column(DateTime, default=now)

    chats = relationship("ChatMessage", back_populates="user", cascade="all,delete")
    notes = relationship("Note", back_populates="user", cascade="all,delete")
    summaries = relationship("Summary", back_populates="user", cascade="all,delete")
    quizzes = relationship("Quiz", back_populates="user", cascade="all,delete")
    flashcard_sets = relationship("FlashcardSet", back_populates="user", cascade="all,delete")
    assignments = relationship("Assignment", back_populates="user", cascade="all,delete")
    tasks = relationship("StudyTask", back_populates="user", cascade="all,delete")
    documents = relationship("Document", back_populates="user", cascade="all,delete")
    activities = relationship("Activity", back_populates="user", cascade="all,delete")


class Document(Base):
    """An uploaded source file used for Retrieval-Augmented Generation."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(500))
    filepath = Column(String(1000))
    num_chunks = Column(Integer, default=0)
    collection_name = Column(String(255))
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="documents")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(100), index=True)  # groups messages into a conversation
    role = Column(String(20))  # "user" | "assistant"
    content = Column(Text)
    used_rag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="chats")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String(500))
    content = Column(Text)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="notes")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(500))
    source_type = Column(String(50))  # "text" | "pdf"
    original_excerpt = Column(Text)
    content = Column(Text)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="summaries")


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String(500))
    difficulty = Column(String(50))
    questions_json = Column(Text)  # JSON list of {question, options, answer_index, explanation}
    best_score = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="quizzes")

    def questions(self):
        return json.loads(self.questions_json or "[]")


class FlashcardSet(Base):
    __tablename__ = "flashcard_sets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String(500))
    cards_json = Column(Text)  # JSON list of {front, back}
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="flashcard_sets")

    def cards(self):
        return json.loads(self.cards_json or "[]")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(500))
    question = Column(Text)
    solution = Column(Text)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="assignments")


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(500))
    subject = Column(String(200))
    due_date = Column(DateTime, nullable=True)
    is_done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="tasks")


class Activity(Base):
    """Lightweight activity log powering Dashboard 'Recent History' + Analytics."""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    kind = Column(String(50))   # chat | notes | summarizer | quiz | flashcards | assignment
    title = Column(String(500))
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="activities")

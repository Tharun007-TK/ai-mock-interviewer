"""
SQLAlchemy ORM models for the AI Mock Interviewer.

Tables: User, Interview, Question, Answer, Report
All use UUID primary keys and UTC timestamps.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from database import Base


# ── Enums ──

class InterviewStatus(str, PyEnum):
    """Interview lifecycle states."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"


# ── Helper ──

def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return uuid.uuid4()


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    interviews = relationship("Interview", back_populates="user", lazy="selectin")

    def __repr__(self):
        return f"<User {self.email}>"


# ──────────────────────────────────────────────
# Interview (replaces in-memory InterviewSession)
# ──────────────────────────────────────────────

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    job_description = Column(Text, nullable=False)
    resume_data = Column(JSONB, nullable=False, default=dict)
    status = Column(
        Enum(InterviewStatus, name="interview_status", create_constraint=True),
        default=InterviewStatus.PENDING,
        nullable=False,
    )
    current_question_index = Column(Integer, default=0, nullable=False)
    total_questions = Column(Integer, default=0, nullable=False)
    overall_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="interviews")
    questions = relationship(
        "Question", back_populates="interview", lazy="selectin",
        order_by="Question.order_index",
    )
    answers = relationship("Answer", back_populates="interview", lazy="selectin")
    report = relationship("Report", back_populates="interview", uselist=False, lazy="selectin")

    def __repr__(self):
        return f"<Interview {self.id} [{self.status}]>"


# ──────────────────────────────────────────────
# Question
# ──────────────────────────────────────────────

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    category = Column(String(50), default="general")
    is_follow_up = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    interview = relationship("Interview", back_populates="questions")
    answer = relationship("Answer", back_populates="question", uselist=False, lazy="selectin")

    def __repr__(self):
        return f"<Question {self.order_index}: {self.question_text[:40]}>"


# ──────────────────────────────────────────────
# Answer
# ──────────────────────────────────────────────

class Answer(Base):
    __tablename__ = "answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    transcript = Column(Text, nullable=False)
    scores = Column(JSONB, nullable=False, default=dict)  # {relevance, clarity, depth, overall}
    feedback = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    interview = relationship("Interview", back_populates="answers")
    question = relationship("Question", back_populates="answer")

    __table_args__ = (
        UniqueConstraint("interview_id", "question_id", name="uq_answer_per_question"),
    )

    def __repr__(self):
        return f"<Answer for Q {self.question_id}>"


# ──────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), unique=True, nullable=False)
    overall_score = Column(Float, default=0.0)
    category_scores = Column(JSONB, default=list)   # [{category, average_score, questions_count}]
    strengths = Column(JSONB, default=list)          # ["strength1", ...]
    improvements = Column(JSONB, default=list)       # ["improvement1", ...]
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    interview = relationship("Interview", back_populates="report")

    def __repr__(self):
        return f"<Report for Interview {self.interview_id}>"

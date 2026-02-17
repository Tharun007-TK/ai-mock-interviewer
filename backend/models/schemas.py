"""
Pydantic request / response schemas for all API endpoints.
These define the contract between frontend and backend.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ──────────────────────────────────────────────
# Resume Upload
# ──────────────────────────────────────────────

class ParsedResume(BaseModel):
    """Structured data extracted from a resume PDF."""
    name: str = ""
    email: str = ""
    phone: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    summary: str = ""


class ResumeUploadResponse(BaseModel):
    """Response after uploading and parsing a resume."""
    success: bool
    message: str
    data: ParsedResume


# ──────────────────────────────────────────────
# Start Interview
# ──────────────────────────────────────────────

class StartInterviewRequest(BaseModel):
    """Request to begin an interview session."""
    job_description: str = Field(..., min_length=10, description="Job description text")
    resume_data: ParsedResume = Field(..., description="Previously parsed resume data")


class QuestionOut(BaseModel):
    """A single interview question."""
    question_id: int
    question_text: str
    category: str = ""  # e.g. "technical", "behavioral", "situational"


class StartInterviewResponse(BaseModel):
    """Response when interview session is created."""
    session_id: str
    total_questions: int
    first_question: QuestionOut


# ──────────────────────────────────────────────
# Answer Submission
# ──────────────────────────────────────────────

class AnswerRequest(BaseModel):
    """Submit an answer for evaluation."""
    session_id: str
    question_id: int
    transcript: str = Field(..., min_length=1, description="User's answer (speech-to-text transcript)")


class AnswerScore(BaseModel):
    """Rubric-based score for a single answer."""
    relevance: float = Field(0.0, ge=0, le=10)
    clarity: float = Field(0.0, ge=0, le=10)
    depth: float = Field(0.0, ge=0, le=10)
    overall: float = Field(0.0, ge=0, le=10)
    feedback: str = ""


class AnswerResponse(BaseModel):
    """Response after evaluating an answer."""
    session_id: str
    question_id: int
    score: AnswerScore
    is_follow_up: bool = False
    next_question: Optional[QuestionOut] = None
    interview_complete: bool = False


# ──────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────

class CategoryScore(BaseModel):
    """Aggregated score per category."""
    category: str
    average_score: float
    questions_count: int


class ReportResponse(BaseModel):
    """Final interview report."""
    session_id: str
    overall_score: float
    total_questions: int
    category_scores: list[CategoryScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    download_url: Optional[str] = None

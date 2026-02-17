"""
Route: POST /start-interview
Creates a new interview session, generates questions, and returns the first question.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import (
    StartInterviewRequest,
    StartInterviewResponse,
    QuestionOut,
)
from models.session import create_session, add_questions_to_session
from services.question_engine import question_engine_service
from services.embeddings import embedding_service

router = APIRouter(tags=["Interview"])


@router.post("/start-interview", response_model=StartInterviewResponse)
async def start_interview(
    request: StartInterviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new interview session.

    - Accepts: Job description + parsed resume data
    - Creates a session, generates questions, returns the first question
    """
    resume_dict = request.resume_data.model_dump()

    # TODO: Embed resume + JD and compute similarity (embedding_service)
    # resume_embedding = await embedding_service.embed_resume_skills(resume_dict.get("skills", []))
    # jd_embedding = await embedding_service.embed_job_description(request.job_description)
    # similarity = await embedding_service.compute_similarity(resume_embedding, jd_embedding)

    # Generate interview questions
    questions_data = await question_engine_service.generate_questions(
        resume_data=resume_dict,
        job_description=request.job_description,
    )

    if not questions_data:
        raise HTTPException(status_code=500, detail="Failed to generate interview questions.")

    # Create session in DB
    interview = await create_session(
        db=db,
        resume_data=resume_dict,
        job_description=request.job_description,
    )

    # Persist questions
    db_questions = await add_questions_to_session(
        db=db,
        interview_id=interview.id,
        questions_data=questions_data,
    )

    # Get first question
    first_q = db_questions[0]
    first_question = QuestionOut(
        question_id=first_q.order_index,
        question_text=first_q.question_text,
        category=first_q.category or "",
    )

    return StartInterviewResponse(
        session_id=str(interview.id),
        total_questions=len(db_questions),
        first_question=first_question,
    )

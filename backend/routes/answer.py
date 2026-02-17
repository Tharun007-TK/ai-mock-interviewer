"""
Route: POST /answer
Submits a user's answer, evaluates it, and returns the next question or completion.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import AnswerRequest, AnswerResponse, QuestionOut
from models.session import get_session, complete_session
from models.db_models import InterviewStatus
from services import crud
from services.evaluation import evaluation_engine_service
from services.question_engine import question_engine_service

router = APIRouter(tags=["Interview"])


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    request: AnswerRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an answer for the current interview question.

    - Accepts: session_id, question_id (order_index), transcript
    - Evaluates the answer with rubric scoring
    - Returns score + next question (or interview complete flag)
    """
    # Retrieve session from DB
    interview = await get_session(db, request.session_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if interview.status == InterviewStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Interview session is already complete.")

    # Find the current question by order_index
    questions = await crud.get_questions_for_interview(db, interview.id)
    current_q = None
    for q in questions:
        if q.order_index == request.question_id:
            current_q = q
            break

    if not current_q:
        raise HTTPException(status_code=400, detail="Invalid question ID for this session.")

    # Evaluate the answer
    score = await evaluation_engine_service.evaluate_answer(
        question=current_q.question_text,
        answer=request.transcript,
        job_description=interview.job_description,
        resume_data=interview.resume_data,
    )

    # Store the answer in DB
    await crud.create_answer(
        db=db,
        interview_id=interview.id,
        question_id=current_q.id,
        transcript=request.transcript,
        scores=score.model_dump(),
        feedback=score.feedback,
    )

    # Check for follow-up
    should_follow_up = await evaluation_engine_service.should_follow_up(score)
    follow_up_question = None

    if should_follow_up:
        follow_up_question = await question_engine_service.generate_follow_up(
            original_question=current_q.question_text,
            user_answer=request.transcript,
            score=score.model_dump(),
        )

    # Advance question index
    await crud.increment_question_index(db, interview)

    # Determine next question
    next_question = None
    interview_complete = False

    if follow_up_question:
        next_question = follow_up_question
    else:
        next_q = await crud.get_question_by_index(
            db, interview.id, interview.current_question_index
        )
        if next_q:
            next_question = QuestionOut(
                question_id=next_q.order_index,
                question_text=next_q.question_text,
                category=next_q.category or "",
            )

    if next_question is None:
        interview_complete = True
        await complete_session(db, interview)

    return AnswerResponse(
        session_id=request.session_id,
        question_id=request.question_id,
        score=score,
        is_follow_up=follow_up_question is not None,
        next_question=next_question,
        interview_complete=interview_complete,
    )

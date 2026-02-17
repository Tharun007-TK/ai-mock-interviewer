"""
WebSocket Interview Endpoint — Real-time voice interview with mid-answer
interruption and AI voice output via Deepgram TTS.

Flow:
  1. Client connects to WS /ws/interview/{session_id}
  2. Client streams audio chunks → Deepgram live transcription
  3. Periodic analysis (every 3s) checks if AI should interrupt
  4. On utterance end OR interruption → evaluate answer → stream LLM response
  5. LLM tokens are sentence-buffered → Deepgram TTS → audio pushed to client
  6. Server pushes transcripts, scores, audio, and next questions

Protocol (JSON messages):
  Client → Server:
    {"type": "audio_chunk", "data": "<base64-encoded audio>"}
    {"type": "end_utterance"}

  Server → Client:
    {"type": "transcript_partial", "text": "..."}
    {"type": "transcript_final", "text": "..."}
    {"type": "eval_score", "score": {...}}
    {"type": "llm_token", "token": "..."}
    {"type": "tts_audio", "data": "<base64-encoded audio>", "encoding": "linear16", "sample_rate": 16000}
    {"type": "next_question", "question": {...}}
    {"type": "interview_complete"}
    {"type": "state_change", "state": "..."}
    {"type": "interrupt", "reason": "..."}
    {"type": "error", "message": "..."}

TODO: Advanced VAD with energy-based silence detection for more precise endpointing.
TODO: Voice style customization (pitch, speed, emotion) via config.
"""

import asyncio
import base64
import json
import logging
import re
import time
import uuid
from collections import deque
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import get_settings
from database import async_session_factory
from models.db_models import InterviewStatus
from services import crud
from services.deepgram_live import DeepgramLiveClient, TranscriptResult
from services.deepgram_tts import DeepgramTTSClient, SentenceBuffer
from services.evaluation import evaluation_engine_service
from services.openrouter_client import generate_completion
from services.openrouter_stream import stream_completion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# ── Constants ──

ANALYSIS_INTERVAL_S = 3.0       # How often to check for interruption
SLIDING_BUFFER_MAX_ITEMS = 30   # Max transcript segments in buffer (~15-20s of speech)
TTS_AUDIO_ENCODING = "linear16"
TTS_AUDIO_SAMPLE_RATE = 16000


# ── Interview State Machine ──

class InterviewState(str, Enum):
    """States for the WebSocket interview session."""
    WAITING_FOR_ANSWER = "waiting_for_answer"
    ANALYZING_PARTIAL = "analyzing_partial"
    INTERRUPTING = "interrupting"
    AI_SPEAKING = "ai_speaking"


# ── Prompts ──

EVAL_STREAM_SYSTEM = """You are an expert technical interviewer evaluating a candidate's answer.

Score the answer and provide brief feedback.

Return valid JSON on ONE line:
{"relevance": X.X, "clarity": X.X, "depth": X.X, "overall": X.X, "feedback": "2-3 sentences"}

Then on a NEW line, write a brief encouraging transition to the next question.
Be concise — max 2 sentences for the transition."""

INTERRUPTION_CHECK_SYSTEM = """You are an interview assistant monitoring a live interview.

Decide if the interviewer should interrupt the candidate RIGHT NOW.

Interrupt ONLY if:
- The candidate is clearly going off-topic for an extended period
- The candidate is stuck in a long pause or repeating themselves
- The candidate has already answered the core question fully and is rambling
- The answer is excessively long (> 2 minutes of speech) with no new information

Do NOT interrupt if:
- The candidate is still building toward a point
- The candidate is providing relevant examples
- Less than 30 seconds of speech so far

Return ONLY valid JSON:
{"should_interrupt": true/false, "reason": "brief explanation"}"""

INTERRUPTION_FOLLOW_UP_SYSTEM = """You are a professional technical interviewer.
The candidate was speaking and you need to politely interject.

Be brief, natural, and encouraging. Acknowledge what they said,
then redirect or ask a follow-up. Max 2-3 sentences."""


class InterviewWSSession:
    """
    Manages state for a single WebSocket interview session.
    Coordinates Deepgram STT, LLM evaluation, Deepgram TTS,
    DB persistence, and mid-answer interruption analysis.
    """

    def __init__(self, ws: WebSocket, session_id: str):
        self.ws = ws
        self.session_id = session_id
        self.interview = None
        self.questions = []
        self.deepgram: DeepgramLiveClient | None = None

        # ── TTS ──
        self._tts: DeepgramTTSClient | None = None
        self._tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._tts_worker_task: asyncio.Task | None = None

        # ── State machine ──
        self._state = InterviewState.WAITING_FOR_ANSWER

        # ── Transcript accumulator (full answer) ──
        self._transcript_parts: list[str] = []

        # ── Sliding buffer for interruption analysis (last ~15-20s) ──
        self._sliding_buffer: deque[str] = deque(maxlen=SLIDING_BUFFER_MAX_ITEMS)
        self._speech_start_time: float | None = None

        # ── Concurrency controls ──
        self._llm_lock = asyncio.Lock()        # Prevents overlapping LLM calls
        self._processing_lock = asyncio.Lock() # Guards answer processing pipeline
        self._utterance_complete = asyncio.Event()

        # ── Background tasks ──
        self._analysis_task: asyncio.Task | None = None

    @property
    def state(self) -> InterviewState:
        return self._state

    async def _set_state(self, new_state: InterviewState) -> None:
        """Transition state and notify the client."""
        old = self._state
        self._state = new_state
        logger.info(f"State: {old.value} → {new_state.value} [{self.session_id}]")
        await self._send_json({"type": "state_change", "state": new_state.value})

    # ────────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────────

    async def initialize(self) -> bool:
        """Load interview from DB and validate state. Returns False if invalid."""
        async with async_session_factory() as db:
            try:
                interview_uuid = uuid.UUID(self.session_id)
            except ValueError:
                await self._send_error("Invalid session ID format.")
                return False

            self.interview = await crud.get_interview(db, interview_uuid)
            if not self.interview:
                await self._send_error("Interview session not found.")
                return False

            if self.interview.status == InterviewStatus.COMPLETE:
                await self._send_error("Interview is already complete.")
                return False

            self.questions = await crud.get_questions_for_interview(db, self.interview.id)
            if not self.questions:
                await self._send_error("No questions found for this interview.")
                return False

        # Send the current question to the client
        current_idx = self.interview.current_question_index
        if current_idx < len(self.questions):
            q = self.questions[current_idx]
            await self._send_json({
                "type": "next_question",
                "question": {
                    "question_id": q.order_index,
                    "question_text": q.question_text,
                    "category": q.category or "",
                },
            })

        await self._set_state(InterviewState.WAITING_FOR_ANSWER)
        return True

    async def start_deepgram(self) -> None:
        """Open Deepgram live transcription WebSocket."""
        self.deepgram = DeepgramLiveClient(on_transcript=self._on_transcript)
        await self.deepgram.connect()
        logger.info(f"Deepgram STT started for session {self.session_id}")

    async def start_tts(self) -> None:
        """Open Deepgram TTS WebSocket and start background TTS worker."""
        self._tts = DeepgramTTSClient(
            on_audio=self._on_tts_audio,
            sample_rate=TTS_AUDIO_SAMPLE_RATE,
            encoding=TTS_AUDIO_ENCODING,
        )
        await self._tts.connect()
        self._tts_worker_task = asyncio.create_task(self._tts_worker())
        logger.info(f"Deepgram TTS started for session {self.session_id}")

    def start_analysis_loop(self) -> None:
        """Start the periodic interruption analysis background task."""
        self._analysis_task = asyncio.create_task(self._analysis_loop())

    async def cleanup(self) -> None:
        """Close connections and cancel all background tasks."""
        # Cancel analysis loop
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass

        # Cancel TTS worker
        if self._tts_worker_task and not self._tts_worker_task.done():
            self._tts_worker_task.cancel()
            try:
                await self._tts_worker_task
            except asyncio.CancelledError:
                pass

        # Close TTS connection
        if self._tts:
            await self._tts.close()
            self._tts = None

        # Close STT connection
        if self.deepgram:
            await self.deepgram.close()
            self.deepgram = None

        logger.info(f"WS session {self.session_id} cleaned up")

    # ────────────────────────────────────────
    # Audio Input
    # ────────────────────────────────────────

    async def handle_audio_chunk(self, data_b64: str) -> None:
        """Decode base64 audio and forward to Deepgram."""
        # Don't accept audio while AI is speaking or interrupting
        if self._state in (InterviewState.INTERRUPTING, InterviewState.AI_SPEAKING):
            return

        try:
            audio_bytes = base64.b64decode(data_b64)
        except Exception:
            await self._send_error("Invalid base64 audio data.")
            return

        if self.deepgram:
            await self.deepgram.send(audio_bytes)

    async def handle_end_utterance(self) -> None:
        """Client signals end of speech — trigger evaluation."""
        if self._state == InterviewState.WAITING_FOR_ANSWER:
            self._utterance_complete.set()

    # ────────────────────────────────────────
    # Transcript Callbacks (from Deepgram STT)
    # ────────────────────────────────────────

    async def _on_transcript(self, result: TranscriptResult) -> None:
        """Called by DeepgramLiveClient for each transcript result."""

        # Ignore transcripts while AI is speaking
        if self._state in (InterviewState.INTERRUPTING, InterviewState.AI_SPEAKING):
            return

        if result.speech_final and not result.transcript:
            # Utterance end detected by Deepgram VAD
            if self._state == InterviewState.WAITING_FOR_ANSWER:
                self._utterance_complete.set()
            return

        if not result.is_final:
            # Partial transcript — forward for live display
            await self._send_json({
                "type": "transcript_partial",
                "text": result.transcript,
            })
        else:
            # Final segment — accumulate and add to sliding buffer
            if self._speech_start_time is None:
                self._speech_start_time = time.monotonic()

            self._transcript_parts.append(result.transcript)
            self._sliding_buffer.append(result.transcript)
            await self._send_json({
                "type": "transcript_final",
                "text": result.transcript,
            })

    # ────────────────────────────────────────
    # TTS Pipeline
    # ────────────────────────────────────────

    async def _on_tts_audio(self, audio_bytes: bytes) -> None:
        """
        Callback from DeepgramTTSClient — each audio frame is forwarded
        to the client as a base64-encoded tts_audio message.
        """
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        await self._send_json({
            "type": "tts_audio",
            "data": b64,
            "encoding": TTS_AUDIO_ENCODING,
            "sample_rate": TTS_AUDIO_SAMPLE_RATE,
        })

    async def _tts_worker(self) -> None:
        """
        Background task: reads sentences from _tts_queue, sends them to
        Deepgram TTS, and flushes after each sentence for low-latency output.

        Queue protocol:
          str  → text to synthesise
          None → sentinel: flush remaining audio and stop
        """
        try:
            while True:
                item = await self._tts_queue.get()

                if item is None:
                    # Sentinel: flush and stop
                    if self._tts:
                        await self._tts.flush()
                    self._tts_queue.task_done()
                    break

                if self._tts and item.strip():
                    start = time.monotonic()
                    await self._tts.send_text(item)
                    await self._tts.flush()
                    latency_ms = (time.monotonic() - start) * 1000
                    logger.debug(f"TTS sentence sent+flushed in {latency_ms:.0f}ms: {len(item)} chars")

                self._tts_queue.task_done()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TTS worker error: {e}")

    async def _speak_with_tts(
        self,
        llm_stream,
        *,
        send_tokens_to_client: bool = True,
    ) -> str:
        """
        Core TTS pipeline: consumes an LLM token stream, buffers tokens
        into sentences, and queues each sentence for TTS synthesis.

        Args:
            llm_stream: AsyncGenerator yielding string tokens.
            send_tokens_to_client: If True, also forward each token as llm_token msg.

        Returns:
            The full concatenated LLM response text.
        """
        sentence_buf = SentenceBuffer(min_chars=20)
        all_parts: list[str] = []
        tts_start = time.monotonic()
        first_sentence_sent = False

        async for token in llm_stream:
            all_parts.append(token)

            if send_tokens_to_client:
                await self._send_json({"type": "llm_token", "token": token})

            # Buffer into sentences
            sentence = sentence_buf.add(token)
            if sentence:
                if not first_sentence_sent:
                    ttfs_ms = (time.monotonic() - tts_start) * 1000
                    logger.info(f"TTS TTFS (time-to-first-sentence): {ttfs_ms:.0f}ms")
                    first_sentence_sent = True
                await self._tts_queue.put(sentence)

        # Drain any remaining text
        remainder = sentence_buf.drain()
        if remainder:
            await self._tts_queue.put(remainder)

        # Send sentinel and wait for TTS to finish speaking
        await self._tts_queue.put(None)
        await self._tts_queue.join()

        total_ms = (time.monotonic() - tts_start) * 1000
        full_text = "".join(all_parts)
        logger.info(f"TTS pipeline complete: {len(full_text)} chars in {total_ms:.0f}ms")

        # Re-create worker for next speaking turn
        self._tts_worker_task = asyncio.create_task(self._tts_worker())

        return full_text

    # ────────────────────────────────────────
    # Periodic Interruption Analysis
    # ────────────────────────────────────────

    async def _analysis_loop(self) -> None:
        """
        Background task: every ANALYSIS_INTERVAL_S seconds, check if the AI
        should interrupt the candidate mid-answer.
        """
        try:
            while True:
                await asyncio.sleep(ANALYSIS_INTERVAL_S)

                # Only analyze while waiting for an answer
                if self._state != InterviewState.WAITING_FOR_ANSWER:
                    continue

                # Need enough speech to analyze (at least a few segments)
                if len(self._sliding_buffer) < 3:
                    continue

                # Need the LLM lock — skip if another LLM call is running
                if self._llm_lock.locked():
                    continue

                await self._check_for_interruption()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Analysis loop error: {e}")

    async def _check_for_interruption(self) -> None:
        """
        Send partial transcript to a lightweight LLM to decide
        if the interviewer should interrupt.
        """
        async with self._llm_lock:
            # Double-check state after acquiring lock
            if self._state != InterviewState.WAITING_FOR_ANSWER:
                return

            await self._set_state(InterviewState.ANALYZING_PARTIAL)

            buffer_text = " ".join(self._sliding_buffer)
            current_idx = self.interview.current_question_index

            if current_idx >= len(self.questions):
                await self._set_state(InterviewState.WAITING_FOR_ANSWER)
                return

            current_q = self.questions[current_idx]
            speech_duration = (
                time.monotonic() - self._speech_start_time
                if self._speech_start_time else 0
            )

            prompt = f"""Current question: {current_q.question_text}
Candidate's speech so far (last ~15-20s): {buffer_text[:1000]}
Total speech duration: {speech_duration:.0f} seconds

Should the interviewer interrupt right now?"""

            start = time.monotonic()
            try:
                settings = get_settings()
                # Use a fast, cheap model for interruption checks
                raw = await generate_completion(
                    prompt=prompt,
                    system_prompt=INTERRUPTION_CHECK_SYSTEM,
                    model=settings.OPENROUTER_MODEL_QUESTION,  # lightweight model
                    temperature=0.1,
                    max_tokens=100,
                    json_mode=True,
                )

                latency_ms = (time.monotonic() - start) * 1000
                logger.info(f"Interruption check: {latency_ms:.0f}ms")

                # Parse response
                decision = json.loads(raw)
                should_interrupt = decision.get("should_interrupt", False)
                reason = decision.get("reason", "")

                if should_interrupt:
                    logger.info(f"Interrupting candidate: {reason}")
                    await self._execute_interruption(reason, current_q)
                else:
                    await self._set_state(InterviewState.WAITING_FOR_ANSWER)

            except Exception as e:
                logger.warning(f"Interruption check failed: {e}")
                # Fail open — don't interrupt, go back to waiting
                await self._set_state(InterviewState.WAITING_FOR_ANSWER)

    async def _execute_interruption(self, reason: str, current_q) -> None:
        """Execute the interruption: notify client, speak follow-up via TTS, resume."""
        await self._set_state(InterviewState.INTERRUPTING)

        # Notify client to stop mic input
        await self._send_json({
            "type": "interrupt",
            "reason": reason,
        })

        # Brief pause so client can process the interrupt signal
        await asyncio.sleep(0.3)

        await self._set_state(InterviewState.AI_SPEAKING)

        # Stream the AI's follow-up / interjection with TTS
        buffer_text = " ".join(self._sliding_buffer)
        prompt = f"""You need to politely interrupt the candidate.

Question they were answering: {current_q.question_text}
What they've said so far: {buffer_text[:800]}
Reason for interruption: {reason}

Briefly acknowledge their point, then redirect or probe deeper."""

        try:
            llm_stream = stream_completion(
                prompt=prompt,
                system_prompt=INTERRUPTION_FOLLOW_UP_SYSTEM,
                temperature=0.6,
                max_tokens=200,
            )
            await self._speak_with_tts(llm_stream, send_tokens_to_client=True)

        except Exception as e:
            logger.error(f"Interruption follow-up failed: {e}")
            await self._send_error("Failed to generate follow-up.")

        # Reset sliding buffer but keep full transcript
        self._sliding_buffer.clear()
        self._speech_start_time = None

        # Return to accepting answers
        await self._set_state(InterviewState.WAITING_FOR_ANSWER)

    # ────────────────────────────────────────
    # Answer Processing Pipeline
    # ────────────────────────────────────────

    async def wait_and_process_answer(self) -> bool:
        """
        Wait for utterance end, then evaluate and advance.
        Returns True if interview should continue, False if complete.
        """
        await self._utterance_complete.wait()
        self._utterance_complete.clear()

        async with self._processing_lock:
            # Acquire LLM lock to prevent overlap with interruption checks
            async with self._llm_lock:
                return await self._process_current_answer()

    async def _process_current_answer(self) -> bool:
        """Evaluate current transcript, persist, speak result via TTS, and advance."""
        full_transcript = " ".join(self._transcript_parts).strip()
        self._transcript_parts.clear()
        self._sliding_buffer.clear()
        self._speech_start_time = None

        if not full_transcript:
            await self._send_error("No speech detected. Please try again.")
            return True  # Continue, don't advance

        current_idx = self.interview.current_question_index
        if current_idx >= len(self.questions):
            await self._send_json({"type": "interview_complete"})
            return False

        current_q = self.questions[current_idx]

        await self._set_state(InterviewState.AI_SPEAKING)

        start = time.monotonic()
        logger.info(f"Processing answer for Q{current_idx}: {len(full_transcript)} chars")

        # ── Evaluate via streaming LLM → TTS pipeline ──
        eval_prompt = f"""Evaluate this interview answer.

Question: {current_q.question_text}
Answer: {full_transcript}
Job Description: {self.interview.job_description[:800]}

Return JSON scores then a brief transition."""

        llm_stream = stream_completion(
            prompt=eval_prompt,
            system_prompt=EVAL_STREAM_SYSTEM,
            model=None,  # uses default
            temperature=0.2,
            max_tokens=500,
        )

        eval_text = await self._speak_with_tts(llm_stream, send_tokens_to_client=True)

        latency_ms = (time.monotonic() - start) * 1000
        logger.info(f"Answer evaluation + TTS completed in {latency_ms:.0f}ms")

        # ── Parse scores from LLM response ──
        score_dict = self._extract_scores(eval_text)

        await self._send_json({
            "type": "eval_score",
            "score": score_dict,
        })

        # ── Persist to DB ──
        async with async_session_factory() as db:
            await crud.create_answer(
                db=db,
                interview_id=self.interview.id,
                question_id=current_q.id,
                transcript=full_transcript,
                scores=score_dict,
                feedback=score_dict.get("feedback", ""),
            )

            await crud.increment_question_index(db, self.interview)
            await db.commit()

        # ── Advance to next question ──
        self.interview.current_question_index += 1
        next_idx = self.interview.current_question_index

        if next_idx >= len(self.questions):
            # Mark interview complete
            async with async_session_factory() as db:
                interview = await crud.get_interview(db, self.interview.id)
                if interview:
                    await crud.update_interview_status(db, interview, InterviewStatus.COMPLETE)
                    await db.commit()

            await self._send_json({"type": "interview_complete"})
            return False

        # Send next question
        next_q = self.questions[next_idx]
        await self._send_json({
            "type": "next_question",
            "question": {
                "question_id": next_q.order_index,
                "question_text": next_q.question_text,
                "category": next_q.category or "",
            },
        })

        await self._set_state(InterviewState.WAITING_FOR_ANSWER)
        return True

    # ────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────

    @staticmethod
    def _extract_scores(text: str) -> dict:
        """Try to parse JSON scores from the LLM response text."""
        json_match = re.search(r'\{[^{}]*"overall"[^{}]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback neutral scores
        return {
            "relevance": 5.0,
            "clarity": 5.0,
            "depth": 5.0,
            "overall": 5.0,
            "feedback": "Score parsing failed — using neutral scores.",
        }

    async def _send_json(self, data: dict) -> None:
        """Send a JSON message to the WebSocket client."""
        try:
            await self.ws.send_json(data)
        except Exception as e:
            logger.warning(f"Failed to send WS message: {e}")

    async def _send_error(self, message: str) -> None:
        """Send an error message to the client."""
        await self._send_json({"type": "error", "message": message})


# ──────────────────────────────────────────────
# WebSocket Endpoint
# ──────────────────────────────────────────────

@router.websocket("/ws/interview/{session_id}")
async def interview_websocket(ws: WebSocket, session_id: str):
    """
    Real-time interview WebSocket endpoint with mid-answer interruption
    and AI voice output via Deepgram TTS.

    1. Client streams audio → Deepgram STT transcribes
    2. Every 3s, partial transcript analyzed for interruption
    3. On utterance end → LLM evaluates → tokens sentence-buffered → TTS → audio pushed
    4. Next question pushed → loop until interview complete
    """
    await ws.accept()
    logger.info(f"WS connected: session={session_id}")

    session = InterviewWSSession(ws, session_id)
    processing_task: asyncio.Task | None = None

    try:
        # Load interview from DB
        if not await session.initialize():
            await ws.close(code=4000, reason="Invalid session")
            return

        # Open Deepgram STT + TTS connections
        await session.start_deepgram()
        await session.start_tts()

        # Start background tasks
        processing_task = asyncio.create_task(_answer_loop(session))
        session.start_analysis_loop()

        # Main loop: receive client messages
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "audio_chunk":
                    await session.handle_audio_chunk(msg.get("data", ""))

                elif msg_type == "end_utterance":
                    await session.handle_end_utterance()

                else:
                    logger.debug(f"Unknown WS message type: {msg_type}")

        except WebSocketDisconnect:
            logger.info(f"WS disconnected: session={session_id}")

    except Exception as e:
        logger.error(f"WS error for session {session_id}: {e}")
        try:
            await session._send_error(f"Server error: {e}")
        except Exception:
            pass
    finally:
        # Cancel processing loop
        if processing_task is not None:
            processing_task.cancel()
            try:
                await processing_task
            except asyncio.CancelledError:
                pass

        await session.cleanup()
        logger.info(f"WS session {session_id} ended")


async def _answer_loop(session: InterviewWSSession) -> None:
    """
    Background task that waits for completed utterances and processes them.
    Runs until interview is complete or cancelled.
    """
    try:
        while True:
            should_continue = await session.wait_and_process_answer()
            if not should_continue:
                break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Answer processing loop error: {e}")
        await session._send_error(f"Processing error: {e}")

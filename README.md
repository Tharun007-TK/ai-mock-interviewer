# AI Mock Interviewer

AI-powered mock interview platform with voice-first interactions. Candidates upload a resume, provide a job description, and practice live with adaptive questions, real-time speech-to-text, LLM-based evaluation, and synthesized interviewer feedback.

## Architecture
- **Frontend**: React (Vite) single-page app with pages for landing, setup, interview room, and report. WebSocket client streams audio and renders live transcripts/scores.
- **Backend**: FastAPI with async SQLAlchemy, PostgreSQL, WebSocket pipeline, OpenRouter LLMs, Deepgram STT/TTS, and Alembic for migrations.
- **Docs**: See [docs/backend.md](docs/backend.md), [docs/frontend.md](docs/frontend.md), and [docs/flow.md](docs/flow.md) for MVP scope.

## Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL (running and accessible)
- Deepgram API key (STT/TTS) and OpenRouter API key (LLM)

## Backend Setup
1) Install deps
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
2) Configure env
- Copy `.env` and set values. Key fields:
  - `DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/mock_interview`
  - `OPENROUTER_API_KEY=<your-key>`
  - `DEEPGRAM_API_KEY=<your-key>`
3) Run migrations
```
cd backend
alembic upgrade head
```
4) Start API
```
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- REST: `POST /api/upload-resume`, `POST /api/start-interview`, `POST /api/answer`, `GET /api/report/{session_id}`
- WS: `/ws/interview/{session_id}` for live audio, transcripts, scores, and TTS.

## Frontend Setup
1) Install deps
```
cd frontend
npm install
```
2) Configure env (optional)
- Create `frontend/.env` or `.env.local` for overrides (e.g., API base URL, WS URL). Default WS URL in code is `ws://localhost:8000/ws/interview`.
3) Run dev server
```
npm run dev
```
- Vite serves at `http://localhost:5173` by default.

## Development Notes
- Keep backend and frontend running together for full flow (resume upload → session start → WebSocket interview → report).
- If DB schema changes, update Alembic models and run new migrations.
- Logs: backend prints WS/Deepgram/LLM timing info; watch console for disconnections.

## Testing Checklist
- Resume upload returns `session_id` and first question.
- WebSocket connects and streams partial/final transcripts.
- AI responses synthesize audio back to the client.
- Scores persist and report endpoint returns aggregated results.

## Troubleshooting
- `relation "interviews" does not exist`: run `alembic upgrade head` against the configured DB.
- WebSocket send errors: ensure Deepgram/OpenRouter keys are valid and network allows outbound `wss://api.deepgram.com`.
- CORS/WS: frontend dev uses `http://localhost:5173`; backend CORS origins include 3000/5173 by default.

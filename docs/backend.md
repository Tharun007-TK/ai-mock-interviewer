# Backend Architecture – MVP

## Core Modules

1. Resume Parser Service
   - Extract text from PDF
   - LLM structuring into JSON

2. Embedding & Matching Service
   - Embed resume skills
   - Embed JD requirements
   - Compute similarity score

3. Question Engine
   - Retrieve relevant questions (Vector DB)
   - Generate adaptive question (LLM)

4. Voice Processing Service
   - Accept audio
   - Convert to text (Whisper)
   - Store transcript

5. Evaluation Engine
   - Rubric-based structured scoring
   - Output JSON scores

6. Report Generator
   - Aggregate session scores
   - Generate formatted PDF

## API Endpoints

POST /upload-resume
POST /start-interview
POST /answer
GET /report/{session_id}

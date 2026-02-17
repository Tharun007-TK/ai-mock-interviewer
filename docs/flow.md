# System Flow – MVP

1. User uploads resume
2. Backend parses resume → structured JSON
3. User enters job description
4. Backend embeds resume + JD
5. System retrieves relevant questions
6. Interview session begins

For each question:
    a. Display question
    b. User speaks
    c. Audio → Whisper → Transcript
    d. LLM evaluates answer
    e. Store structured score
    f. Generate follow-up if needed

After final question:
    - Aggregate scores
    - Compute overall rating
    - Generate PDF report
    - Display summary

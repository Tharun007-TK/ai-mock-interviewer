/**
 * SetupPage — Resume upload + Job description input → Start Interview.
 */

import { useNavigate } from 'react-router-dom';
import { useInterviewContext } from '../context/InterviewContext';
import ResumeUploader from '../components/ResumeUploader';
import JDInputBox from '../components/JDInputBox';

export default function SetupPage() {
  const navigate = useNavigate();
  const { state, uploadResume, setJobDescription, startInterview } = useInterviewContext();

  const canStart = state.resumeData && state.jobDescription.length >= 10;
  const isLoading = state.status === 'uploading';

  async function handleStart() {
    if (!canStart) return;
    await startInterview();
    navigate('/interview');
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg space-y-8 animate-fade-in">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-text">Setup Your Interview</h1>
          <p className="mt-2 text-sm text-text-muted">
            Upload your resume and paste the job description to begin.
          </p>
        </div>

        {/* Error */}
        {state.error && (
          <div className="rounded-lg bg-danger/10 border border-danger/20 p-4 text-sm text-danger">
            {state.error}
          </div>
        )}

        {/* Step 1: Resume Upload */}
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-text-muted">
            Step 1 — Upload Resume
          </h2>
          <ResumeUploader onUpload={uploadResume} isLoading={isLoading} />
          {state.resumeData && (
            <p className="text-xs text-success">
              ✓ Resume parsed ({state.resumeData.skills?.length || 0} skills extracted)
            </p>
          )}
        </div>

        {/* Step 2: Job Description */}
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-text-muted">
            Step 2 — Job Description
          </h2>
          <JDInputBox value={state.jobDescription} onChange={setJobDescription} />
        </div>

        {/* Start Button */}
        <button
          onClick={handleStart}
          disabled={!canStart || state.status === 'interviewing'}
          className={`
            w-full rounded-xl py-4 text-base font-semibold transition-all duration-300
            ${canStart
              ? 'bg-primary text-white shadow-lg shadow-primary/25 hover:bg-primary-dark hover:shadow-xl hover:-translate-y-0.5'
              : 'bg-surface-light text-text-muted cursor-not-allowed'
            }
          `}
        >
          {state.status === 'interviewing' ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Starting...
            </span>
          ) : (
            'Start Interview →'
          )}
        </button>
      </div>
    </div>
  );
}

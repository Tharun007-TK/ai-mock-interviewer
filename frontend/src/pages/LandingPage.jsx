/**
 * LandingPage — Hero section with product intro and Start CTA.
 */

import { useNavigate } from 'react-router-dom';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="mx-auto max-w-2xl text-center animate-fade-in">
        {/* Badge */}
        <span className="mb-6 inline-block rounded-full bg-primary/10 px-4 py-1.5 text-xs font-medium text-primary">
          AI-Powered Mock Interviews
        </span>

        {/* Headline */}
        <h1 className="mb-6 text-5xl font-bold leading-tight tracking-tight text-text">
          Ace Your Next{' '}
          <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Interview
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mb-10 text-lg leading-relaxed text-text-muted">
          Practice with an AI interviewer that adapts to your resume and target role.
          Get real-time voice-based Q&A, structured feedback, and a detailed performance report.
        </p>

        {/* CTA */}
        <button
          onClick={() => navigate('/setup')}
          className="group inline-flex items-center gap-2 rounded-xl bg-primary px-8 py-4 text-base font-semibold text-white
                     shadow-lg shadow-primary/25 transition-all duration-300
                     hover:bg-primary-dark hover:shadow-xl hover:shadow-primary/30 hover:-translate-y-0.5
                     active:translate-y-0"
        >
          Start Interview
          <svg className="h-5 w-5 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
          </svg>
        </button>

        {/* Feature highlights */}
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {[
            { icon: '📄', title: 'Resume-Based', desc: 'Questions tailored to your skills' },
            { icon: '🎙️', title: 'Voice Interview', desc: '10–15 adaptive questions' },
            { icon: '📊', title: 'Detailed Report', desc: 'Rubric scoring + PDF download' },
          ].map((f) => (
            <div key={f.title} className="rounded-xl bg-surface-light/50 p-5 text-center">
              <span className="mb-2 block text-2xl">{f.icon}</span>
              <h3 className="text-sm font-semibold text-text">{f.title}</h3>
              <p className="mt-1 text-xs text-text-muted">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

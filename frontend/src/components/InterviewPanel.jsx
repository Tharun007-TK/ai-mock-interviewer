/**
 * InterviewPanel — Displays the current question, progress bar, audio controls.
 * Integrated with WebSocket logic for real-time interaction.
 */

import ProgressTracker from './ProgressTracker';
import VoiceRecorder from './VoiceRecorder';

export default function InterviewPanel({
  question,
  questionIndex,
  totalQuestions,
  isEvaluating,
  isAiSpeaking,
  onAudioData,
  onRecordingChange,
}) {
  return (
    <div className="mx-auto max-w-2xl space-y-8 animate-fade-in">
      {/* Progress */}
      <ProgressTracker current={questionIndex} total={totalQuestions} />

      {/* Question card */}
      <div className={`
        relative overflow-hidden rounded-2xl border p-8 shadow-lg transition-all duration-500
        ${isAiSpeaking 
          ? 'border-indigo-500/50 bg-indigo-500/5 shadow-indigo-500/20 scale-[1.02]' 
          : 'border-white/10 bg-white/5 shadow-black/20'}
      `}>
        {/* Background glow when speaking */}
        {isAiSpeaking && (
           <div className="absolute inset-0 bg-indigo-500/5 animate-pulse pointer-events-none" />
        )}

        {question?.category && (
          <span className="relative z-10 mb-3 inline-block rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-400">
            {question.category}
          </span>
        )}
        
        <h2 className="relative z-10 text-xl font-semibold leading-relaxed text-white">
          {question?.question_text || 'Loading question...'}
        </h2>
        
        {/* Speaking Indicator */}
        {isAiSpeaking && (
           <div className="relative z-10 mt-6 flex items-center gap-2 text-sm text-indigo-400 font-medium">
             <span className="flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
             </span>
             AI is speaking...
           </div>
        )}
      </div>

      {/* Control Area */}
      <div className="flex flex-col items-center gap-3 py-4">
          <VoiceRecorder
            onAudioData={onAudioData}
            onRecordingChange={onRecordingChange}
            disabled={isEvaluating} 
            forceStop={isAiSpeaking} // Stop recording if AI starts speaking
          />
      </div>
    </div>
  );
}

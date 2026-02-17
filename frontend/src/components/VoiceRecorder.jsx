import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * VoiceRecorder — Handles microphone input and streaming.
 * 
 * Uses MediaRecorder to capture audio chunks and pass them to parent via `onAudioData`.
 * Can be controlled externally via `forceStop` (e.g. when AI interrupts).
 */
export default function VoiceRecorder({ onAudioData, onRecordingChange, disabled, forceStop }) {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const mediaRecorderRef = useRef(null);
  const timerRef = useRef(null);

  // ── Cleanup on unmount ──
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  // ── Handle external stop (Interruption) ──
  useEffect(() => {
    if (forceStop && isRecording) {
      stopRecording();
    }
  }, [forceStop, isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Deepgram prefers raw audio or opus. WebM/Opus is standard for MediaRecorder.
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && onAudioData) {
          const reader = new FileReader();
          reader.onloadend = () => {
            // Remove "data:audio/webm;base64," prefix
            const base64data = reader.result.split(',')[1];
            onAudioData(base64data);
          };
          reader.readAsDataURL(event.data);
        }
      };

      // Request data every 250ms for low latency streaming
      mediaRecorder.start(250);
      
      setIsRecording(true);
      setDuration(0);
      if (onRecordingChange) onRecordingChange(true);

      timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);

    } catch (err) {
      console.error('Failed to start microphone:', err);
      alert('Microphone access denied or not supported.');
    }
  };

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      if (mediaRecorderRef.current.stream) {
          mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      }
    }
    
    if (timerRef.current) clearInterval(timerRef.current);
    setIsRecording(false);
    if (onRecordingChange) onRecordingChange(false);
  }, [onRecordingChange]);

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Record button */}
      <button
        onClick={toggleRecording}
        disabled={disabled}
        className={`
          relative flex h-20 w-20 items-center justify-center rounded-full
          transition-all duration-300
          ${isRecording
            ? 'bg-red-500 shadow-lg shadow-red-500/30 scale-110'
            : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg hover:shadow-indigo-600/30'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        {/* Pulse ring when recording */}
        {isRecording && (
          <span className="absolute inset-0 rounded-full bg-red-500/40 animate-pulse" />
        )}
        {isRecording ? (
          <svg className="h-8 w-8 text-white" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg className="h-8 w-8 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>

      {/* Timer / Status */}
      <div className="text-center">
        <span className={`font-mono text-lg block ${isRecording ? 'text-red-500' : 'text-gray-500'}`}>
          {formatTime(duration)}
        </span>
        <p className="text-xs text-gray-400 mt-1">
          {isRecording ? 'Listening...' : 'Click to answer'}
        </p>
      </div>

    </div>
  );
}

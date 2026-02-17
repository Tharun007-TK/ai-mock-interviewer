/**
 * InterviewContext — React Context provider for global interview state.
 * Wraps the app so all pages can access the interview hook.
 */

import { createContext, useContext } from 'react';
import { useInterview } from '../hooks/useInterview';

const InterviewContext = createContext(null);

export function InterviewProvider({ children }) {
  const interview = useInterview();
  return (
    <InterviewContext.Provider value={interview}>
      {children}
    </InterviewContext.Provider>
  );
}

export function useInterviewContext() {
  const context = useContext(InterviewContext);
  if (!context) {
    throw new Error('useInterviewContext must be used within an InterviewProvider');
  }
  return context;
}

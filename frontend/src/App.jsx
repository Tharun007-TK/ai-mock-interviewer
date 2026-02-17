/**
 * App — Root component with React Router and InterviewContext provider.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { InterviewProvider } from './context/InterviewContext';
import LandingPage from './pages/LandingPage';
import SetupPage from './pages/SetupPage';
import InterviewPage from './pages/InterviewPage';
import ReportPage from './pages/ReportPage';

export default function App() {
  return (
    <BrowserRouter>
      <InterviewProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/report/:sessionId" element={<ReportPage />} />
        </Routes>
      </InterviewProvider>
    </BrowserRouter>
  );
}

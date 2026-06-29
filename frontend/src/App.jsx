import { Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/HomePage'
import RefinePage from './pages/RefinePage'
import VerifyPage from './pages/VerifyPage'
import ItineraryPage from './pages/ItineraryPage'

/**
 * App — top-level route table.
 *
 * Route structure mirrors the Stitch flow:
 *   /           Onboarding hero + persona picker
 *   /refine     AI profiler clarification form
 *   /verify     Stop review before narration
 *   /itinerary  Split-view map + timeline + audio player
 */
export default function App() {
  return (
    <Routes>
      <Route path="/"           element={<HomePage />} />
      <Route path="/refine"     element={<RefinePage />} />
      <Route path="/verify"     element={<VerifyPage />} />
      <Route path="/itinerary"  element={<ItineraryPage />} />
      {/* Catch-all → home */}
      <Route path="*"           element={<Navigate to="/" replace />} />
    </Routes>
  )
}

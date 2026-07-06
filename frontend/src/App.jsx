import { Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/HomePage'
import RefinePage from './pages/RefinePage'
import VerifyPage from './pages/VerifyPage'
import ItineraryPage from './pages/ItineraryPage'
import TripsPage from './pages/TripsPage'
import SignInPage from './pages/SignInPage'
import { useAuth } from './hooks/useAuth'

/**
 * App — top-level route table, gated behind authentication.
 *
 * Route structure mirrors the Stitch flow:
 *   /           Onboarding hero + persona picker
 *   /refine     AI profiler clarification form
 *   /verify     Stop review before narration
 *   /itinerary  Split-view map + timeline + audio player
 *   /trips      Saved trips library (no agent re-run)
 */
export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <span className="material-symbols-outlined text-5xl text-primary animate-spin">sync</span>
      </div>
    )
  }

  if (!user) {
    return <SignInPage />
  }

  return (
    <Routes>
      <Route path="/"           element={<HomePage />} />
      <Route path="/refine"     element={<RefinePage />} />
      <Route path="/verify"     element={<VerifyPage />} />
      <Route path="/itinerary"  element={<ItineraryPage />} />
      <Route path="/trips"      element={<TripsPage />} />
      {/* Catch-all → home */}
      <Route path="*"           element={<Navigate to="/" replace />} />
    </Routes>
  )
}

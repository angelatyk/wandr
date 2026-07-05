import { Link } from 'react-router-dom'
import TopNav from '../components/TopNav'
import {
  formatTripDate,
  tripDestination,
  tripHref,
  tripStatusLabel,
  useSavedTrips,
} from '../hooks/useSavedTrips'

function StatusBadge({ status }) {
  const styles = {
    complete: 'bg-secondary/15 text-secondary',
    awaiting_selection: 'bg-primary/10 text-primary',
    planning: 'bg-surface-container text-on-surface-muted',
    error: 'bg-red-100 text-red-800',
    started: 'bg-surface-container text-on-surface-muted',
  }

  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider',
        styles[status] || styles.started,
      ].join(' ')}
      style={{ fontFamily: 'var(--font-body)' }}
    >
      {tripStatusLabel(status)}
    </span>
  )
}

function TripCard({ trip }) {
  const href = tripHref(trip)
  const destination = tripDestination(trip)

  return (
    <article className="rounded-2xl border border-outline-variant/30 bg-surface-white shadow-[var(--shadow-card)] overflow-hidden hover:shadow-[var(--shadow-raised)] transition-all duration-300">
      <div className="p-6 md:p-8 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              className="text-2xl font-semibold text-primary leading-tight"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              {destination}
            </h2>
            <p className="text-sm text-on-surface-muted mt-1" style={{ fontFamily: 'var(--font-body)' }}>
              {trip.duration || 'Duration pending'}
              {trip.persona_type ? ` · ${trip.persona_type}` : ''}
            </p>
          </div>
          <StatusBadge status={trip.status} />
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs font-semibold uppercase tracking-wider text-on-surface-muted">
          <span className="inline-flex items-center gap-1">
            <span className="material-symbols-outlined text-[16px]">location_on</span>
            {trip.stop_count || 0} stops
          </span>
          {trip.has_audio && (
            <span className="inline-flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px]">headphones</span>
              Audio ready
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <span className="material-symbols-outlined text-[16px]">schedule</span>
            {formatTripDate(trip.updated_at)}
          </span>
        </div>

        {trip.status === 'error' && trip.error_message && (
          <p className="text-sm text-red-700" style={{ fontFamily: 'var(--font-body)' }}>
            {trip.error_message}
          </p>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-outline-variant/20">
          <span className="text-xs text-on-surface-muted font-mono">{trip.plan_id.slice(0, 8)}…</span>
          <Link
            to={href}
            className="inline-flex items-center gap-2 bg-primary text-white text-xs font-semibold uppercase tracking-widest px-5 py-3 rounded-xl hover:bg-primary-tint transition-colors"
            style={{ fontFamily: 'var(--font-body)' }}
          >
            Open trip
            <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
          </Link>
        </div>
      </div>
    </article>
  )
}

/**
 * TripsPage — saved plans loaded from disk, no agent re-run needed.
 */
export default function TripsPage() {
  const { trips, loading, error, refresh } = useSavedTrips()

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <TopNav />

      <main className="pt-28 md:pt-32 pb-24 px-5 md:px-16 max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
          <div>
            <h1
              className="text-4xl md:text-5xl font-bold text-primary tracking-tight"
              style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
            >
              My Trips
            </h1>
            <p className="text-base text-on-surface-muted mt-2" style={{ fontFamily: 'var(--font-body)' }}>
              Pick up where you left off — saved itineraries, options, and narrations load instantly.
            </p>
          </div>
          <button
            type="button"
            onClick={refresh}
            className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-primary hover:text-primary-tint transition-colors"
            style={{ fontFamily: 'var(--font-body)' }}
          >
            <span className="material-symbols-outlined text-[18px]">refresh</span>
            Refresh
          </button>
        </div>

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <span className="material-symbols-outlined text-5xl text-primary animate-spin">sync</span>
            <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
              Loading your trips…
            </p>
          </div>
        )}

        {!loading && error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-base text-red-800" style={{ fontFamily: 'var(--font-body)' }}>{error}</p>
          </div>
        )}

        {!loading && !error && trips.length === 0 && (
          <div className="rounded-2xl border border-outline-variant/30 bg-surface-white p-10 text-center">
            <span className="material-symbols-outlined text-5xl text-primary mb-4">luggage</span>
            <h2 className="text-2xl font-semibold text-primary mb-2" style={{ fontFamily: 'var(--font-display)' }}>
              No trips yet
            </h2>
            <p className="text-base text-on-surface-muted mb-6" style={{ fontFamily: 'var(--font-body)' }}>
              Start planning and your itineraries will appear here automatically.
            </p>
            <Link
              to="/"
              className="inline-flex items-center gap-2 bg-primary text-white text-xs font-semibold uppercase tracking-widest px-6 py-3 rounded-xl"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              Plan a trip
              <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
            </Link>
          </div>
        )}

        {!loading && !error && trips.length > 0 && (
          <div className="grid grid-cols-1 gap-6">
            {trips.map((trip) => (
              <TripCard key={trip.plan_id} trip={trip} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

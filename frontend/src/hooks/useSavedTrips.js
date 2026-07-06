import { useCallback, useEffect, useState } from 'react'

/**
 * useSavedTrips — fetches and refreshes the user's saved trip records.
 *
 * Calls GET /api/trips on mount and exposes a `refresh` callback so the UI
 * can re-fetch without remounting the component.
 *
 * @returns {{ trips: object[], loading: boolean, error: string|null, refresh: function }}
 */
export function useSavedTrips() {
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/trips')
      if (!res.ok) throw new Error('Could not load saved trips')
      const data = await res.json()
      setTrips(Array.isArray(data.trips) ? data.trips : [])
    } catch (err) {
      console.error(err)
      setError('Could not load your saved trips.')
      setTrips([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { trips, loading, error, refresh }
}

/**
 * tripDestination — returns the human-readable destination name for a trip.
 * Falls back to 'Untitled trip' when the field is absent.
 *
 * @param {object} trip — trip record from the My Trips API
 * @returns {string}
 */
export function tripDestination(trip) {
  return trip?.destination || 'Untitled trip'
}

/**
 * tripHref — resolves the correct resume URL for a trip based on its status.
 * Routes to the appropriate page so the user always lands in the right state:
 *   complete          → /itinerary (view narrated stops)
 *   awaiting_selection → /verify   (confirm stop choices)
 *   anything else     → /refine    (still planning)
 *
 * @param {object} trip — trip record from the My Trips API
 * @returns {string} — relative URL safe to pass to react-router <Link to=>
 */
export function tripHref(trip) {
  const planId = trip?.plan_id
  if (!planId) return '/'

  switch (trip?.status) {
    case 'complete':
      return `/itinerary?planId=${planId}`
    case 'awaiting_selection':
      return `/verify?planId=${planId}`
    case 'error':
    case 'planning':
    case 'started':
    default:
      return `/refine?planId=${planId}`
  }
}

/**
 * tripStatusLabel — converts a backend status code to a user-facing label.
 *
 * @param {string} status — raw status string from the trips API
 * @returns {string}
 */
export function tripStatusLabel(status) {
  switch (status) {
    case 'complete':
      return 'Ready'
    case 'awaiting_selection':
      return 'Review options'
    case 'planning':
      return 'Planning'
    case 'error':
      return 'Needs retry'
    default:
      return 'In progress'
  }
}

/**
 * formatTripDate — formats an ISO timestamp into a locale-friendly short date.
 * Returns an empty string for missing or invalid values rather than throwing.
 *
 * @param {string|null} value — ISO 8601 datetime string (e.g. "2025-08-14T10:30:00Z")
 * @returns {string} — e.g. "Aug 14, 2025" or "" if the value is absent/invalid
 */
export function formatTripDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

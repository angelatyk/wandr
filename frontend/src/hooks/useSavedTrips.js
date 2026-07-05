import { useCallback, useEffect, useState } from 'react'

/**
 * useSavedTrips — loads persisted trips from the backend My Trips store.
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

export function tripDestination(trip) {
  return trip?.destination || 'Untitled trip'
}

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

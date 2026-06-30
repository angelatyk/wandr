import { useState, useEffect, useRef } from 'react'

/**
 * usePlanStream — subscribes to the backend SSE stream for a given plan.
 *
 * Returns live state that updates as pipeline events arrive.
 * The EventSource is closed (and re-opened on action) when an
 * itinerary_options or complete event arrives.
 */
export function usePlanStream(planId) {
  const [stops, setStops] = useState([])
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('initializing')
  const [clarification, setClarification] = useState(null)
  const [itineraryOptions, setItineraryOptions] = useState(null)
  const [itinerary, setItinerary] = useState(null)
  const [route, setRoute] = useState(null)
  const [persona, setPersona] = useState(null)

  // Expose an imperative "reconnect" so VerifyPage can re-open the stream
  // after sending a refine or finalize action.
  const reconnectRef = useRef(null)

  useEffect(() => {
    if (!planId) return

    let es = null

    const connect = () => {
      // Close any existing connection before reopening
      if (es) es.close()

      es = new EventSource(`/api/plan/${planId}/stream`)

      es.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          setProgress(event.progress || 0)

          if (event.type === 'profiler_clarification') {
            setStatus('needs_clarification')
            setClarification(event.data.message)
            es.close()

          } else if (event.type === 'profiler_done') {
            setStatus('planning')
            setPersona(event.data)

          } else if (event.type === 'itinerary_options') {
            // Options are ready — show VerifyPage, stream pauses here
            setStatus('awaiting_selection')
            setItineraryOptions(event.data)
            es.close()

          } else if (event.type === 'itinerary_done') {
            setStatus('finalised')
            setItinerary(event.data)

          } else if (event.type === 'stop_done') {
            setStops((prev) => {
              const exists = prev.some(s => s.place_id === event.data.place_id)
              if (exists) return prev
              return [...prev, event.data]
            })

          } else if (event.type === 'logistics_done') {
            setStatus('routing')
            setRoute(event.data)

          } else if (event.type === 'complete') {
            setStatus('complete')
            es.close()

          } else if (event.type === 'error') {
            setStatus('error')
            es.close()
          }
        } catch (err) {
          console.error('Error parsing SSE event:', err)
        }
      }

      es.onerror = (err) => {
        console.error('SSE Error:', err)
        setStatus('error')
        es.close()
      }
    }

    // Wire the reconnect function so callers can re-open the stream
    reconnectRef.current = connect
    connect()

    return () => {
      if (es) es.close()
    }
  }, [planId])

  const reconnect = () => {
    if (reconnectRef.current) reconnectRef.current()
  }

  return { stops, progress, status, clarification, itineraryOptions, itinerary, route, persona, reconnect }
}

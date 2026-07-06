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
  const [errorMessage, setErrorMessage] = useState(null)
  const [clarification, setClarification] = useState(null)
  const [itineraryOptions, setItineraryOptions] = useState(null)
  const [itinerary, setItinerary] = useState(null)
  const [route, setRoute] = useState(null)
  const [persona, setPersona] = useState(null)

  // Expose an imperative "reconnect" so VerifyPage can re-open the stream
  // after sending a refine or finalize action.
  const reconnectRef = useRef(null)
  const gracefulCloseRef = useRef(false)

  useEffect(() => {
    if (!planId) return

    let es = null

    const closeStream = () => {
      gracefulCloseRef.current = true
      if (es) es.close()
    }

    const connect = (isReconnect = false) => {
      gracefulCloseRef.current = false
      // Close any existing connection before reopening
      if (es) es.close()

      if (isReconnect) {
        setItinerary(null)
        setRoute(null)
        setStops([])
      }

      es = new EventSource(`/api/plan/${planId}/stream`)

      es.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          setProgress(event.progress || 0)

          if (event.type === 'profiler_clarification') {
            setStatus('needs_clarification')
            setClarification(event.data.message)
            setErrorMessage(null)
            closeStream()

          } else if (event.type === 'profiler_done') {
            setStatus('planning')
            setPersona(event.data)
            setErrorMessage(null)

          } else if (event.type === 'itinerary_options') {
            // Options are ready — show VerifyPage, stream pauses here
            const days = event.data?.days
            if (!Array.isArray(days) || days.length === 0) {
              setStatus('error')
              setErrorMessage('Itinerary options arrived without any places. Please retry.')
              closeStream()
              return
            }
            setStatus('awaiting_selection')
            setItineraryOptions(event.data)
            setErrorMessage(null)
            closeStream()

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
            setErrorMessage(null)
            const state = event.data || {}
            if (state.persona) setPersona(state.persona)
            if (state.itinerary) setItinerary(state.itinerary)
            if (state.route) setRoute(state.route)
            if (state.itinerary_options) {
              setItineraryOptions(state.itinerary_options)
            } else if (state.itinerary_options_confirmed) {
              setItineraryOptions({
                days: [{ options: state.itinerary_options_confirmed }]
              })
            }
            if (Array.isArray(state.audio_scripts?.scripts) && state.audio_scripts.scripts.length > 0) {
              setStops(state.audio_scripts.scripts)
            }
            closeStream()

          } else if (event.type === 'error') {
            setStatus('error')
            setErrorMessage(event.data?.message || 'The trip pipeline failed. Please try again.')
            closeStream()
          }
        } catch (err) {
          console.error('Error parsing SSE event:', err)
        }
      }

      es.onerror = () => {
        // EventSource fires onerror when the server closes after a normal pause
        // (e.g. itinerary_options) — do not treat that as a failure.
        if (gracefulCloseRef.current) return
        console.error('SSE connection lost unexpectedly')
        setStatus('error')
        setErrorMessage('Connection lost while streaming trip updates. Please retry.')
        closeStream()
      }
    }

    // Wire the reconnect function so callers can re-open the stream
    reconnectRef.current = () => connect(true)
    connect()

    return () => {
      gracefulCloseRef.current = true
      if (es) es.close()
    }
  }, [planId])

  const reconnect = () => {
    if (reconnectRef.current) reconnectRef.current()
  }

  return { stops, progress, status, errorMessage, clarification, itineraryOptions, itinerary, route, persona, reconnect }
}

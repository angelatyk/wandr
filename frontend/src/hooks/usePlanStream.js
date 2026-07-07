import { useState, useEffect, useRef } from 'react'

/**
 * usePlanStream — subscribes to the backend SSE stream for a given plan.
 *
 * Opens an EventSource on `/api/plan/:planId/stream` and parses the JSON
 * events that the FastAPI pipeline emits. State fields are updated as each
 * event type arrives so components can render incrementally.
 *
 * The stream is deliberately paused (server closes it) after `itinerary_options`
 * so the user can review and select stops. Callers re-open it by calling the
 * returned `reconnect()` function after POSTing to `/api/plan/:id/select`.
 *
 * @param {string|null} planId — UUID from the URL search param `?planId=`
 * @returns {object}
 *   @returns {object[]}     stops           — AudioScript records that arrive via `stop_done` events
 *   @returns {number}       progress        — 0–100 progress value from the latest event
 *   @returns {string}       status          — pipeline phase: 'initializing' | 'planning' | 'needs_clarification' |
 *                                             'awaiting_selection' | 'finalised' | 'routing' | 'complete' | 'error'
 *   @returns {string|null}  errorMessage    — human-readable error; non-null when status === 'error'
 *   @returns {string|null}  clarification   — question text from the profiler; non-null when status === 'needs_clarification'
 *   @returns {object|null}  itineraryOptions — ItineraryOptionsModel payload from the `itinerary_options` event
 *   @returns {object|null}  itinerary       — ItineraryModel payload from the `itinerary_done` event
 *   @returns {object|null}  route           — RouteModel payload from the `logistics_done` event
 *   @returns {object|null}  persona         — PersonaModel payload from the `profiler_done` event
 *   @returns {function}     reconnect       — Imperative fn to re-open the stream (call after finalize/refine POST)
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

  // gracefulCloseRef tracks whether the stream was intentionally closed by us
  // (e.g. after an itinerary_options event) vs. lost unexpectedly. We use a
  // ref instead of state because it must be readable inside the onerror handler
  // synchronously, without a stale closure. A state update would only be
  // visible to the *next* render, too late for the onerror check.
  const reconnectRef = useRef(null)
  const gracefulCloseRef = useRef(false)

  // statusRef mirrors the status state so onerror can read the current value
  // without a stale closure (same reason as gracefulCloseRef).
  const statusRef = useRef('initializing')

  // Silent retry state — judges never see a 'reconnecting' status.
  const MAX_RETRIES = 3
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef(null)

  useEffect(() => {
    if (!planId) return

    let es = null

    // Keep statusRef in sync so onerror can read the live value without a stale closure.
    const updateStatus = (next) => {
      statusRef.current = next
      setStatus(next)
    }

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
        // First successful message — reset the retry counter
        retryCountRef.current = 0
        try {
          const event = JSON.parse(e.data)
          setProgress(event.progress || 0)

          if (event.type === 'profiler_clarification') {
            updateStatus('needs_clarification')
            setClarification(event.data.message)
            setErrorMessage(null)
            closeStream()

          } else if (event.type === 'profiler_done') {
            updateStatus('planning')
            setPersona(event.data)
            setErrorMessage(null)

          } else if (event.type === 'itinerary_options') {
            // Options are ready — show VerifyPage, stream pauses here
            const days = event.data?.days
            if (!Array.isArray(days) || days.length === 0) {
              updateStatus('error')
              setErrorMessage('Itinerary options arrived without any places. Please retry.')
              closeStream()
              return
            }
            updateStatus('awaiting_selection')
            setItineraryOptions(event.data)
            setErrorMessage(null)
            closeStream()

          } else if (event.type === 'itinerary_done') {
            updateStatus('finalised')
            setItinerary(event.data)

          } else if (event.type === 'stop_done') {
            setStops((prev) => {
              const idx = prev.findIndex(s => s.place_id === event.data.place_id)
              if (idx !== -1) {
                const merged = [...prev]
                merged[idx] = { ...merged[idx], ...event.data }
                return merged
              }
              return [...prev, event.data]
            })

          } else if (event.type === 'logistics_done') {
            updateStatus('routing')
            setRoute(event.data)

          } else if (event.type === 'complete') {
            updateStatus('complete')
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
            // Merge audio scripts from the complete payload into existing stops.
            // We do NOT replace outright — stop_done events may have already
            // populated stops correctly. We only fill in gaps (stops not yet
            // received via stop_done) or patch in audio_url if it was missing.
            if (Array.isArray(state.audio_scripts?.scripts) && state.audio_scripts.scripts.length > 0) {
              setStops((prev) => {
                const merged = [...prev]
                for (const script of state.audio_scripts.scripts) {
                  const idx = merged.findIndex(s => s.place_id === script.place_id)
                  if (idx === -1) {
                    // Stop not yet received via stop_done — add it
                    merged.push(script)
                  } else if (!merged[idx].audio_url && script.audio_url) {
                    // Stop arrived via stop_done but without audio — patch it in
                    merged[idx] = { ...merged[idx], ...script }
                  }
                }
                return merged
              })
            }
            closeStream()

          } else if (event.type === 'error') {
            updateStatus('error')
            setErrorMessage(event.data?.message || 'The trip pipeline failed. Please try again.')
            closeStream()
          }
        } catch (err) {
          console.error('Error parsing SSE event:', err)
        }
      }

      es.onerror = () => {
        // Intentional close (e.g. itinerary_options pause, complete) — not a failure.
        if (gracefulCloseRef.current) return

        // Terminal states that close intentionally — don't retry.
        const terminalStatuses = ['complete', 'awaiting_selection']
        if (terminalStatuses.includes(statusRef.current)) return

        if (retryCountRef.current < MAX_RETRIES) {
          const attempt = retryCountRef.current + 1
          const delay = Math.pow(2, retryCountRef.current) * 1000 // 1s → 2s → 4s
          retryCountRef.current = attempt
          console.warn(`[wandr] SSE dropped — silent retry ${attempt}/${MAX_RETRIES} in ${delay}ms`)
          if (es) es.close()
          // No status change — the user sees nothing during a retry.
          retryTimerRef.current = setTimeout(() => connect(), delay)
        } else {
          console.error('[wandr] SSE connection lost after all retries')
          updateStatus('error')
          setErrorMessage('Connection lost while streaming trip updates. Please retry.')
          closeStream()
        }
      }
    }

    // Wire the reconnect function so callers can re-open the stream
    reconnectRef.current = () => connect(true)
    connect()

    return () => {
      gracefulCloseRef.current = true
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      if (es) es.close()
    }
  }, [planId])

  const reconnect = () => {
    if (reconnectRef.current) reconnectRef.current()
  }

  return { stops, progress, status, errorMessage, clarification, itineraryOptions, itinerary, route, persona, reconnect }
}

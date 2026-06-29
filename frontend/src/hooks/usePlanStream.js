import { useState, useEffect } from 'react'

export function usePlanStream(planId) {
  const [stops, setStops] = useState([])
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('initializing')
  const [clarification, setClarification] = useState(null)
  const [itinerary, setItinerary] = useState(null)
  const [route, setRoute] = useState(null)
  const [persona, setPersona] = useState(null)

  useEffect(() => {
    if (!planId) return

    const es = new EventSource(`/api/plan/${planId}/stream`)

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        setProgress(event.progress || 0)

        if (event.type === 'profiler_clarification') {
          setStatus('needs_clarification')
          setClarification(event.data.message)
          es.close() // Close stream while waiting for user input
        } else if (event.type === 'profiler_done') {
          setStatus('planning')
          setPersona(event.data)
        } else if (event.type === 'itinerary_done') {
          setStatus('researching')
          setItinerary(event.data)
        } else if (event.type === 'stop_done') {
          setStops((prev) => {
            // Prevent duplicates if React StrictMode fires multiple times
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

    return () => es.close()
  }, [planId])

  return { stops, progress, status, clarification, itinerary, route, persona }
}

import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import StopCard from '../components/StopCard'
import AudioPlayer from '../components/AudioPlayer'
import { usePlanStream } from '../hooks/usePlanStream'
import MapRoute, { travelModeFromPreference } from '../components/MapRoute'

/**
 * ItineraryPage — split-view narrated itinerary.
 */
export default function ItineraryPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const planId = searchParams.get('planId')
  const { stops: audioStops, itinerary, route, persona, itineraryOptions } = usePlanStream(planId)
  const [nowPlaying, setNowPlaying] = useState(null)
  const [activeStopId, setActiveStopId] = useState(null)

  useEffect(() => {
    if (!planId) navigate('/')
  }, [planId, navigate])

  const handlePinClick = (stopId) => {
    setActiveStopId(stopId)
    // Direct DOM scroll is appropriate here: the timeline is a plain scrollable
    // div, not a virtualised list, so getElementById is reliable and avoids
    // threading a ref callback through every StopCard.
    const el = document.getElementById(`stop-card-${stopId}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const handlePlay = (stop) => {
    if (!stop.hasAudio || !stop.audioUrl) return
    setActiveStopId(stop.id)
    setNowPlaying({
      stopId: stop.id,
      title: `${stop.name} — Narration`,
      image: stop.image,
      audioUrl: stop.audioUrl,
      progressPct: 0,
    })
  }

  const destination = persona?.destination || itinerary?.destination || 'Loading...'

  // optionMap: quick lookup of VerifyPage option data (description, duration)
  // keyed by place_id so we can enrich ItineraryModel stops without a nested
  // loop on every render.
  const optionMap = useMemo(() => {
    const map = {}
    if (itineraryOptions?.days) {
      for (const day of itineraryOptions.days) {
        for (const option of (day.options || [])) {
          map[option.place_id] = option
        }
      }
    }
    return map
  }, [itineraryOptions])

  // imageMap: place_id → photo_url, built from itineraryOptions so that images
  // appear on stop cards even when the final ItineraryModel stop doesn't carry
  // a photo_url directly (the photos come from the Places API during the Verify
  // phase and aren't re-fetched during finalize).
  const imageMap = useMemo(() => {
    const map = {}
    if (itineraryOptions?.days) {
      for (const day of itineraryOptions.days) {
        for (const option of day.options) {
          if (option.photo_url) map[option.place_id] = option.photo_url
        }
      }
    }
    return map
  }, [itineraryOptions])

  // displayDays: maps the raw ItineraryModel to UI-ready objects, joining stop
  // data from the backend route (for travel times) with option data (for images
  // and descriptions) and audio data (for the narration player).
  const displayDays = (itinerary?.days || []).map((day) => ({
    id: `day-${day.day}`,
    label: `Day ${day.day}`,
    stops: day.stops.map((stop, idx) => {
      const audio = audioStops.find((item) => item.place_id === stop.place_id)
      const validRouteStops = (route?.stops ?? []).filter((s) => typeof s.lat === 'number' && typeof s.lng === 'number')
      const routeStop = validRouteStops.find((item) => item.place_id === stop.place_id)
      const globalIdx = validRouteStops.findIndex((s) => s.place_id === stop.place_id)
      const stopNumber = globalIdx !== -1 ? globalIdx + 1 : idx + 1

      let transit = null
      if (routeStop && routeStop.travel_time_from_prev_min > 0) {
        transit = {
          icon: 'directions_walk',
          label: `${routeStop.travel_time_from_prev_min} min walking`,
        }
      }

      const option = optionMap[stop.place_id] || {}
      return {
        id: stop.place_id,
        name: stop.name,
        description: option.description || 'Description unavailable',
        suggestedDuration: option.suggested_duration || null,
        image: stop.photo_url || imageMap[stop.place_id] || null,
        time: `Stop ${stopNumber}`,
        personaIcon: 'park',
        narrationLength: audio ? `${Math.max(1, Math.round(audio.duration_sec / 60))} min` : '...',
        included: true,
        transit,
        audioUrl: audio?.audio_url || null,
        hasAudio: Boolean(
          audio?.audio_url &&
          audio?.audio_source !== 'text_only' &&
          !(audio?.script || '').startsWith('We could not generate narration')
        ),
      }
    }),
  }))

  const totalWalk = route?.total_travel_min || 0

  const totalActivityMin = useMemo(() => {
    if (!itinerary || !itineraryOptions) return 0
    const optionsByPlaceId = {}
    for (const day of itineraryOptions.days || []) {
      for (const opt of day.options || []) {
        optionsByPlaceId[opt.place_id] = opt.suggested_duration
      }
    }
    let min = 0
    for (const day of itinerary.days || []) {
      for (const stop of day.stops || []) {
        const str = optionsByPlaceId[stop.place_id]
        if (str) {
          const hourMatch = str.match(/(\d+(?:\.\d+)?)\s*hour/i)
          if (hourMatch) min += parseFloat(hourMatch[1]) * 60
          const minMatch = str.match(/(\d+)\s*min/i)
          if (minMatch) min += parseInt(minMatch[1], 10)
        }
      }
    }
    return min
  }, [itinerary, itineraryOptions])

  const mapDays = useMemo(
    () =>
      (itinerary?.days || []).map((day) => ({
        dayNumber: day.day,
        stops: day.stops
          .map((stop) => {
            const routeStop = (route?.stops ?? []).find((item) => item.place_id === stop.place_id)
            if (
              !routeStop ||
              typeof routeStop.lat !== 'number' ||
              typeof routeStop.lng !== 'number'
            ) {
              return null
            }
            return {
              id: stop.place_id,
              name: stop.name,
              lat: routeStop.lat,
              lng: routeStop.lng,
              order: stop.order,
            }
          })
          .filter(Boolean),
      })),
    [itinerary, route]
  )

  const mapTravelMode = travelModeFromPreference(persona?.transit_preference)

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <header className="bg-surface/80 backdrop-blur-md text-primary fixed top-0 w-full z-50 flex justify-between items-center px-5 md:px-16 h-20">
        <span
          className="text-3xl md:text-5xl font-bold text-primary tracking-tight cursor-pointer"
          onClick={() => navigate('/')}
          style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
        >
          Wandr
        </span>

        <nav className="hidden md:flex gap-6 h-full items-center">
          {[
            { label: 'Explore', to: '/' },
            { label: 'My Trips', to: '/trips', active: false },
          ].map(({ label, to, active }) => (
            <a
              key={label}
              href={to || '#'}
              className={[
                'text-xs font-semibold uppercase tracking-widest transition-colors duration-300 h-full flex items-center px-2',
                active
                  ? 'text-primary border-b-2 border-secondary-container'
                  : 'text-on-surface-muted hover:text-primary',
              ].join(' ')}
              style={{ fontFamily: 'var(--font-body)' }}
            >
              {label}
            </a>
          ))}
        </nav>

        <div className="flex gap-4">
          <button className="text-on-surface-muted hover:text-primary transition-colors">
            <span className="material-symbols-outlined">notifications</span>
          </button>
          <button className="text-on-surface-muted hover:text-primary transition-colors">
            <span className="material-symbols-outlined">account_circle</span>
          </button>
        </div>
      </header>

      {/* ── Main split layout ── */}
      <main className="flex-1 flex flex-col md:flex-row pt-20 h-screen w-full relative">
        {/* Left — scrollable timeline */}
        <section
          className="w-full md:w-5/12 lg:w-1/3 bg-surface-white overflow-y-auto no-scrollbar px-5 md:px-8 py-6 flex flex-col gap-10 z-10 relative pb-40"
          style={{ height: 'calc(100vh - 5rem)' }}
        >
          {!itinerary ? (
            <div className="flex flex-col items-center justify-center py-24 gap-6 text-center">
              <span className="material-symbols-outlined text-5xl text-primary animate-spin">sync</span>
              <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
                Finalizing your itinerary...
              </p>
            </div>
          ) : (
            displayDays.map((day) => (
              <div key={day.id}>
                <div className="flex flex-col gap-2 mb-6">
                  <h1
                    className="text-3xl md:text-4xl font-bold text-primary"
                    style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
                  >
                    {day.label}
                  </h1>
                  <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
                    Immerse yourself in {destination}&apos;s vibrant neighbourhoods through curated, narrated stops.
                  </p>
                </div>

                <div className="flex flex-col relative w-full">
                  {day.stops
                    .filter((stop) => stop.included)
                    .map((stop, idx, arr) => (
                      <article key={stop.id} id={`stop-card-${stop.id}`} className="timeline-item relative pl-12 pb-10 w-full">
                        {idx < arr.length - 1 && <div className="timeline-connector" />}
                        <div className="absolute left-0 top-0 w-10 h-10 rounded-full bg-secondary text-white flex items-center justify-center z-10 shadow-md">
                          <span className="material-symbols-outlined text-[20px] icon-filled">
                            {stop.personaIcon}
                          </span>
                        </div>

                        <StopCard
                          stop={stop}
                          variant="itinerary"
                          active={nowPlaying?.stopId === stop.id || activeStopId === stop.id}
                          onPlay={() => handlePlay(stop)}
                          onViewMap={() => handlePinClick(stop.id)}
                        />

                        {idx < arr.length - 1 && arr[idx + 1].transit && (
                          <div className="mt-6 flex items-center gap-3 text-on-surface-muted ml-2 relative z-10">
                            <span className="material-symbols-outlined text-[18px]">{arr[idx + 1].transit.icon}</span>
                            <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
                              {arr[idx + 1].transit.label}
                            </span>
                          </div>
                        )}
                      </article>
                    ))}
                </div>
              </div>
            ))
          )}
        </section>

        {/* Right — map */}
        <section
          className="hidden md:block w-7/12 lg:w-2/3 relative bg-surface-container"
          style={{ height: 'calc(100vh - 5rem)' }}
        >
          <div className="absolute inset-0 w-full h-full">
            <MapRoute
              days={mapDays}
              travelMode={mapTravelMode}
              onPinClick={handlePinClick}
              activeStopId={activeStopId}
              totalWalkMin={totalWalk}
              totalActivityMin={totalActivityMin}
              destination={destination}
            />
          </div>
        </section>
      </main>

      {/* ── Audio Player ── */}
      {nowPlaying && (
        <AudioPlayer
          title={nowPlaying.title}
          image={nowPlaying.image}
          audioUrl={nowPlaying.audioUrl}
          onClose={() => setNowPlaying(null)}
        />
      )}
    </div>
  )
}

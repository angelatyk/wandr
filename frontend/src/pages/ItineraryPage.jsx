import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import StopCard from '../components/StopCard'
import AudioPlayer from '../components/AudioPlayer'
import { usePlanStream } from '../hooks/usePlanStream'
import MapRoute from '../components/MapRoute'

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
    const el = document.getElementById(`stop-card-${stopId}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const handlePlay = (stop) => {
    setNowPlaying({
      stopId: stop.id,
      title: `${stop.name} — Narration`,
      image: stop.image,
      audioUrl: stop.audioUrl,
      progressPct: 0,
    })
  }

  const destination = persona?.destination || itinerary?.destination || 'Loading...'

  const imageMap = {}
  if (itineraryOptions?.days) {
    for (const day of itineraryOptions.days) {
      for (const option of day.options) {
        if (option.photo_url) imageMap[option.place_id] = option.photo_url
      }
    }
  }

  const displayDays = (itinerary?.days || []).map((day) => ({
    id: `day-${day.day}`,
    label: `Day ${day.day}`,
    stops: day.stops.map((stop, idx) => {
      const audio = audioStops.find((item) => item.place_id === stop.place_id)
      const routeStop = route?.stops?.find((item) => item.place_id === stop.place_id)

      let transit = null
      if (routeStop && routeStop.travel_time_from_prev_min > 0) {
        transit = {
          icon: 'directions_walk',
          label: `${routeStop.travel_time_from_prev_min} min walking`,
        }
      }

      return {
        id: stop.place_id,
        name: stop.name,
        description: audio ? audio.script : 'Narration is being generated...',
        image: imageMap[stop.place_id] || 'https://via.placeholder.com/800x600?text=Stop',
        time: `Stop ${idx + 1}`,
        personaIcon: 'park',
        narrationLength: audio ? `${Math.max(1, Math.round(audio.duration_sec / 60))} min` : '...',
        included: true,
        transit,
        audioUrl: audio?.audio_url,
      }
    }),
  }))

  const totalWalk = route?.total_travel_min || 0

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
            { label: 'My Trips', active: true },
            { label: 'Saved', to: `/verify?planId=${planId || ''}` },
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
                        />

                        {stop.transit && (
                          <div className="mt-4 flex items-center gap-3 text-on-surface-muted ml-2">
                            <span className="material-symbols-outlined text-[18px]">{stop.transit.icon}</span>
                            <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
                              {stop.transit.label}
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
              route={route}
              stops={displayDays.flatMap((day) => day.stops)}
              onPinClick={handlePinClick}
            />
          </div>

          <div
            className="absolute top-6 right-6 bg-surface/90 backdrop-blur-md rounded-2xl p-4 border border-outline-variant/20 flex flex-col gap-2 max-w-xs"
            style={{ boxShadow: 'var(--shadow-raised)' }}
          >
            <h3
              className="text-lg font-semibold text-primary leading-tight"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Total Route
            </h3>
            {route ? (
              totalWalk > 0 ? (
                <div className="flex items-center gap-2 text-on-surface-muted text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
                  <span className="material-symbols-outlined text-[16px]">directions_walk</span>
                  {totalWalk} min walking total
                </div>
              ) : (
                <div className="text-xs text-on-surface-muted font-semibold uppercase tracking-wider">
                  Calculating route...
                </div>
              )
            ) : (
              <div className="text-xs text-on-surface-muted font-semibold uppercase tracking-wider">
                Calculating route...
              </div>
            )}
          </div>
        </section>
      </main>

      {/* ── Audio Player ── */}
      {nowPlaying && (
        <AudioPlayer
          title={nowPlaying.title}
          image={nowPlaying.image}
          progressPct={nowPlaying.progressPct}
        />
      )}
    </div>
  )
}

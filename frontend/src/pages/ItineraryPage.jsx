import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import StopCard from '../components/StopCard'
import AudioPlayer from '../components/AudioPlayer'
import { MOCK_ITINERARY, NOW_PLAYING } from '../data/mockItinerary'

const MAP_IMAGE =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBHbFZBLd1wDgYmp71bMLKTdqpRI4KetQU6AvxAJDD4AwsmicAxaIX-L7RvNtGxelxvCtP9V5YLFfrNzwAAJKN7xtMpwkbM_WpFQOlzFaNtAlPCGrRVy4lpTDMKpHmEAbleCnSKsjhjG9TxCTp8tbGkFRYRrxNXtYIXGUgmh3pUMKnhZ9XE9erYw6KtCZVz3-O_objRZr0NxDzE6_2e4dMaaS2I7nwurj6kVPfbSR5L9FshrfqYUeMkhQGWJAmI0dgUJ93cuhG1yjZV'

/**
 * ItineraryPage — split-view narrated itinerary.
 *
 * Layout:
 *  Left  1/3  — scrollable timeline of stop cards
 *  Right 2/3  — map (mock image) + floating route summary
 *  Bottom     — glassmorphic AudioPlayer bar
 */
export default function ItineraryPage() {
  const navigate = useNavigate()
  const [nowPlaying, setNowPlaying] = useState(NOW_PLAYING)

  // Flatten all stops for easy lookup
  const allStops = MOCK_ITINERARY.flatMap((d) => d.stops)

  const handlePlay = (stop) => {
    setNowPlaying({
      stopId: stop.id,
      title: `${stop.name} — Narration`,
      image: stop.image,
      progressPct: 0,
    })
  }

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
            { label: 'Saved', to: '/verify' },
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
        <section className="w-full md:w-5/12 lg:w-1/3 bg-surface-white h-full overflow-y-auto no-scrollbar px-5 md:px-8 py-6 flex flex-col gap-10 z-10 relative pb-40">

          {MOCK_ITINERARY.map((day) => (
            <div key={day.id}>
              {/* Day heading */}
              <div className="flex flex-col gap-2 mb-6">
                <h1
                  className="text-3xl md:text-4xl font-bold text-primary"
                  style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
                >
                  {day.label}
                </h1>
                <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
                  Immerse yourself in Tokyo's vibrant neighbourhoods through curated, narrated stops.
                </p>
              </div>

              {/* Timeline stops */}
              <div className="flex flex-col relative w-full">
                {day.stops
                  .filter((s) => s.included)
                  .map((stop, idx, arr) => (
                    <article key={stop.id} className="timeline-item relative pl-12 pb-10 w-full">
                      {idx < arr.length - 1 && <div className="timeline-connector" />}

                      {/* Marker */}
                      <div className="absolute left-0 top-0 w-10 h-10 rounded-full bg-secondary text-white flex items-center justify-center z-10 shadow-md">
                        <span className="material-symbols-outlined text-[20px] icon-filled">
                          {stop.personaIcon}
                        </span>
                      </div>

                      {/* Card */}
                      <StopCard
                        stop={stop}
                        variant="itinerary"
                        active={nowPlaying?.stopId === stop.id}
                        onPlay={() => handlePlay(stop)}
                      />

                      {/* Transit info */}
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
          ))}
        </section>

        {/* Right — map */}
        <section className="hidden md:block w-7/12 lg:w-2/3 h-full relative bg-surface-container">
          <div
            className="bg-cover bg-center w-full h-full"
            style={{ backgroundImage: `url('${MAP_IMAGE}')` }}
          />

          {/* Route summary overlay */}
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
            <div className="flex items-center gap-2 text-on-surface-muted text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
              <span className="material-symbols-outlined text-[16px]">directions_walk</span>
              45 min walking total
            </div>
            <div className="flex items-center gap-2 text-on-surface-muted text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
              <span className="material-symbols-outlined text-[16px]">train</span>
              25 min transit total
            </div>
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

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import StopCard from '../components/StopCard'
import { MOCK_ITINERARY } from '../data/mockItinerary'

/**
 * VerifyPage — review and curate itinerary stops before narration begins.
 *
 * Users toggle stops on/off. Finalize navigates to /itinerary.
 */
export default function VerifyPage() {
  const navigate = useNavigate()

  // Track included state for each stop keyed by stop id
  const [included, setIncluded] = useState(() => {
    const init = {}
    MOCK_ITINERARY.forEach((day) =>
      day.stops.forEach((stop) => {
        init[stop.id] = stop.included
      })
    )
    return init
  })

  const toggle = (id) => setIncluded((prev) => ({ ...prev, [id]: !prev[id] }))

  const includedCount = Object.values(included).filter(Boolean).length

  return (
    <div className="min-h-screen bg-surface text-on-surface antialiased pb-32">
      {/* Transactional header — no global nav, just back + logo */}
      <header className="w-full px-5 md:px-16 py-5 flex items-center justify-between sticky top-0 z-40 glass">
        <button
          onClick={() => navigate('/refine')}
          className="flex items-center text-primary hover:text-primary-tint transition-colors"
          aria-label="Back to setup"
        >
          <span className="material-symbols-outlined mr-2">arrow_back</span>
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
            Back to setup
          </span>
        </button>

        <h1
          className="text-3xl md:text-5xl font-bold text-primary tracking-tight"
          style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
        >
          Wandr
        </h1>

        {/* Spacer for visual balance */}
        <div className="w-28" />
      </header>

      {/* Main */}
      <main className="max-w-4xl mx-auto px-5 md:px-16 pt-6 pb-12">
        {/* Page heading */}
        <div className="mb-10 text-center md:text-left">
          <h2
            className="text-2xl font-semibold text-primary mb-2"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Review Your Itinerary
          </h2>
          <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
            We've curated these stops based on your "Foodie" persona for 2 days in Tokyo.{' '}
            <span className="font-semibold text-on-surface">{includedCount} stops selected.</span>
          </p>
        </div>

        {/* Timeline container */}
        <div className="relative pl-8 md:pl-12">
          {/* Vertical timeline line */}
          <div
            className="absolute left-0 md:left-4 top-4 bottom-0 w-0.5"
            style={{ background: 'linear-gradient(to bottom, var(--wandr-primary), transparent)' }}
          />

          {MOCK_ITINERARY.map((day) => (
            <div key={day.id} className="mb-6">
              {/* Day label */}
              <div className="relative mb-6">
                <div className="absolute -left-10 md:-left-6 top-1 w-4 h-4 rounded-full bg-secondary-container border-2 border-surface" />
                <h3
                  className="text-2xl font-semibold text-primary"
                  style={{ fontFamily: 'var(--font-display)' }}
                >
                  {day.label}
                </h3>
              </div>

              {/* Stop cards */}
              <div className="flex flex-col gap-6">
                {day.stops.map((stop) => (
                  <div key={stop.id} className="relative">
                    {/* Timeline dot */}
                    <div
                      className={[
                        'absolute -left-10 md:-left-6 top-8 w-3 h-3 rounded-full border-2 border-surface z-10',
                        included[stop.id] ? 'bg-surface-variant' : 'bg-outline-variant',
                      ].join(' ')}
                    />
                    <StopCard
                      stop={stop}
                      variant="verify"
                      included={included[stop.id]}
                      onToggle={() => toggle(stop.id)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Floating finalize button & Refine input */}
      <div className="fixed bottom-0 left-0 w-full p-4 md:p-8 bg-gradient-to-t from-surface via-surface/90 to-transparent z-50 flex flex-col items-center pointer-events-none">
        <div className="pointer-events-auto w-full max-w-4xl mx-auto mb-4 px-5 md:px-0">
          <div className="glass rounded-2xl p-4 shadow-[0px_4px_20px_rgba(10,25,47,0.05)] border border-outline-variant/30 bg-surface/80">
            <label
              className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-3"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              Refine Your Itinerary
            </label>
            <div className="relative flex items-center">
              <textarea
                rows={1}
                className="w-full bg-surface-container-low border-none rounded-xl py-3 pl-4 pr-12 text-base focus:ring-1 focus:ring-primary resize-none"
                placeholder="Add a coffee stop near Ginza..."
              />
              <button className="absolute right-2 p-2 text-primary hover:text-primary-tint transition-colors flex items-center justify-center">
                <span className="material-symbols-outlined">auto_awesome</span>
              </button>
            </div>
          </div>
        </div>
        <button
          onClick={() => navigate('/itinerary')}
          className="pointer-events-auto bg-primary text-white font-semibold text-xs uppercase tracking-widest px-8 py-4 rounded-2xl flex items-center justify-center min-w-[280px] gap-2 active:scale-95 transition-all hover:bg-primary-tint shadow-[0px_8px_32px_rgba(10,25,47,0.2)]"
          style={{ fontFamily: 'var(--font-body)' }}
        >
          Finalize Itinerary
          <span className="material-symbols-outlined text-[18px]">check_circle</span>
        </button>
      </div>
    </div>
  )
}

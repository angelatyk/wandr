import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { usePlanStream } from '../hooks/usePlanStream'

function parseDurationString(str) {
  if (!str) return 0;
  const s = str.toLowerCase();
  const num = parseFloat(s.match(/(\d+(?:\.\d+)?)/)?.[1] || '0');
  if (s.includes('hour') || s.includes('hr')) return num;
  if (s.includes('day')) return num * 24;
  if (s.includes('week')) return num * 24 * 7;
  return num;
}

function parseSuggestedDuration(str) {
  if (!str) return 1.0;
  const s = str.toLowerCase();
  let multiplier = 1.0;
  if (s.includes('min')) multiplier = 1 / 60;
  
  const matches = s.match(/(\d+(?:\.\d+)?)/g);
  if (matches) {
    if (matches.length > 1) {
      return ((parseFloat(matches[0]) + parseFloat(matches[1])) / 2) * multiplier;
    }
    return parseFloat(matches[0]) * multiplier;
  }
  return 1.0;
}

/**
 * VerifyPage — review and curate itinerary options before finalising.
 *
 * Data flow:
 *  1. planId comes from URL ?planId=<uuid>
 *  2. usePlanStream() delivers itineraryOptions via the itinerary_options SSE event
 *  3. User toggles places on/off (confirmed state lives in local React state)
 *  4. "Refine" textarea → POST /api/plan/:id/select { action:"refine", ... }
 *     → agent reruns keeping confirmed places + adds refinement
 *  5. "Finalize Itinerary" → POST /api/plan/:id/select { action:"finalize", ... }
 *     → agent outputs final JSON → navigate to /itinerary
 */
export default function VerifyPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const planId = searchParams.get('planId')

  const { itineraryOptions, itinerary, route, status, errorMessage, persona, reconnect } = usePlanStream(planId)

  // confirmed: Set of place_ids the user has toggled ON
  const [confirmed, setConfirmed] = useState(new Set())
  const [refineText, setRefineText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [actionStatus, setActionStatus] = useState(null) // 'refining' | 'finalizing' | null
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [exceededData, setExceededData] = useState(null)

  // Redirect if no planId
  useEffect(() => {
    if (!planId) navigate('/')
  }, [planId, navigate])

  // When new options arrive (initial load or after a refine), default-select
  // all must_see places so users start with a reasonable selection.
  useEffect(() => {
    if (!itineraryOptions) return
    const mustSeeIds = new Set()
    for (const day of itineraryOptions.days ?? []) {
      for (const place of day.options ?? []) {
        if (place.must_see) mustSeeIds.add(place.place_id)
      }
    }
    setConfirmed(mustSeeIds)
    setActionStatus(null)
  }, [itineraryOptions])

  // Navigate to /itinerary only once BOTH the finalized itinerary AND the route
  // are ready. Checking both values (not just status) prevents navigating on a
  // stale 'routing'/'complete' replay before the finalize pipeline finishes.
  useEffect(() => {
    if (itinerary && route) {
      navigate(`/itinerary?planId=${planId}`)
    }
  }, [itinerary, route, navigate, planId])

  // If the pipeline errors while we're waiting for finalize/refine, clear the
  // loading state so the error UI is visible and the user can retry or go back.
  useEffect(() => {
    if (status === 'error') {
      setActionStatus(null)
      setSubmitting(false)
    }
  }, [status])

  // Safety timeout — if we've been finalizing for more than 90 seconds without
  // the route arriving, something went wrong server-side. Clear the stuck state.
  useEffect(() => {
    if (actionStatus !== 'finalizing') return
    const timer = setTimeout(() => {
      setActionStatus(null)
      setSubmitting(false)
    }, 90_000)
    return () => clearTimeout(timer)
  }, [actionStatus])

  const togglePlace = (placeId) => {
    setConfirmed((prev) => {
      const next = new Set(prev)
      if (next.has(placeId)) next.delete(placeId)
      else next.add(placeId)
      return next
    })
  }

  const callSelect = async (action) => {
    setSubmitting(true)
    setActionStatus(action === 'refine' ? 'refining' : 'finalizing')
    try {
      const res = await fetch(`/api/plan/${planId}/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confirmed_place_ids: Array.from(confirmed),
          refinement_text: refineText || null,
          action,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setRefineText('')
      // Re-open the SSE stream to receive the updated itinerary_options
      // (refine) or the itinerary_done event (finalize).
      reconnect()
    } catch (err) {
      console.error('select error:', err)
      setActionStatus(null)
    } finally {
      setSubmitting(false)
    }
  }

  const handleRefine = (e) => {
    e.preventDefault()
    if (!refineText.trim() || submitting) return
    callSelect('refine')
  }

  const handleFinalize = () => {
    if (submitting) return

    let totalSuggested = 0
    let placesList = []
    
    for (const day of itineraryOptions?.days ?? []) {
      for (const place of day.options ?? []) {
        if (confirmed.has(place.place_id)) {
          totalSuggested += parseSuggestedDuration(place.suggested_duration)
          placesList.push(place.name)
        }
      }
    }
    
    const totalWithOverhead = totalSuggested * 1.2
    const maxDuration = parseDurationString(duration)
    
    if (maxDuration > 0 && totalWithOverhead > maxDuration + 0.5 && maxDuration < 24) {
      setExceededData({
        places: placesList,
        calculated: Math.round(totalWithOverhead * 10) / 10
      })
      setShowConfirmModal(true)
      return
    }

    callSelect('finalize')
  }

  // ── Loading state ──────────────────────────────────────────────────────────
  const hasError = status === 'error'
  const optionDays = Array.isArray(itineraryOptions?.days) ? itineraryOptions.days : []
  const hasOptions = optionDays.length > 0
  const isLoading = (!hasOptions && !hasError) || actionStatus !== null

  const loadingMessage = (() => {
    if (actionStatus === 'refining') return 'Refining your itinerary…'
    if (actionStatus === 'finalizing') return 'Finalizing your itinerary…'
    return 'Curating your options…'
  })()

  // ── Derived counts ─────────────────────────────────────────────────────────
  const totalOptions = optionDays.reduce(
    (acc, d) => acc + (d.options?.length ?? 0), 0
  )
  const confirmedCount = confirmed.size

  const destination = itineraryOptions?.destination ?? persona?.destination ?? ''
  const personaType = persona?.type ?? ''
  const duration = persona?.duration ?? ''

  return (
    <div className="min-h-screen bg-surface text-on-surface antialiased pb-56">

      {/* ── Header ── */}
      <header className="w-full px-5 md:px-16 py-5 flex items-center justify-between sticky top-0 z-40 glass">
        <button
          onClick={() => navigate('/refine?' + (planId ? `planId=${planId}` : ''))}
          className="flex items-center text-primary hover:text-primary-tint transition-colors"
          aria-label="Back to setup"
        >
          <span className="material-symbols-outlined mr-2">arrow_back</span>
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
            Back
          </span>
        </button>

        <h1
          className="text-3xl md:text-5xl font-bold text-primary tracking-tight"
          style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
        >
          Wandr
        </h1>

        {/* Spacer */}
        <div className="w-28" />
      </header>

      {/* ── Main ── */}
      <main className="max-w-4xl mx-auto pt-24 pb-48 md:pb-56 md:pt-32 px-5 md:px-0 relative z-10">

        {/* Page heading */}
        <div className="mb-10 text-center md:text-left">
          <h2
            className="text-2xl font-semibold text-primary mb-2"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            {isLoading ? loadingMessage : 'Review Your Options'}
          </h2>
          {!isLoading && (
            <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
              {destination && personaType && duration
                ? `Curated for a "${personaType}" persona — ${duration} in ${destination}. `
                : ''}
              <span className="font-semibold text-on-surface">
                {confirmedCount} of {totalOptions} places selected.
              </span>
            </p>
          )}
        </div>

        {/* Loading spinner */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-6">
            <span className="material-symbols-outlined text-5xl text-primary animate-spin">sync</span>
            <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
              {loadingMessage}
            </p>
          </div>
        )}

        {hasError && (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
            <span className="material-symbols-outlined text-5xl text-primary">warning</span>
            <p className="text-base text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
              {errorMessage || 'A temporary issue interrupted itinerary generation.'}
            </p>
            <button
              type="button"
              onClick={() => navigate('/')}
              className="bg-primary text-white font-semibold text-xs uppercase tracking-widest px-6 py-3 rounded-xl"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              Start Over
            </button>
          </div>
        )}

        {/* Options list */}
        {!isLoading && (
          <div className="relative pl-8 md:pl-12">
            {/* Timeline line */}
            <div
              className="absolute left-0 md:left-4 top-4 bottom-0 w-0.5"
              style={{ background: 'linear-gradient(to bottom, var(--wandr-primary), transparent)' }}
            />

            {optionDays.map((day) => (
              <div key={day.day} className="mb-6">
                {/* Day label */}
                {optionDays.length > 1 && (
                  <div className="relative mb-6">
                    <div className="absolute -left-10 md:-left-6 top-1 w-4 h-4 rounded-full bg-secondary-container border-2 border-surface" />
                    <h3
                      className="text-2xl font-semibold text-primary"
                      style={{ fontFamily: 'var(--font-display)' }}
                    >
                      Day {day.day}
                    </h3>
                  </div>
                )}

                {/* Place option cards */}
                <div className="flex flex-col gap-6">
                  {(day.options ?? []).map((place) => {
                    const isConfirmed = confirmed.has(place.place_id)
                    return (
                      <div key={place.place_id} className="relative">
                        {/* Timeline dot */}
                        <div
                          className={[
                            'absolute -left-10 md:-left-6 top-8 w-3 h-3 rounded-full border-2 border-surface z-10',
                            isConfirmed ? 'bg-secondary' : 'bg-outline-variant',
                          ].join(' ')}
                        />

                        {/* Card */}
                        <div
                          className={[
                            'rounded-2xl overflow-hidden border transition-all duration-300',
                            isConfirmed
                              ? 'border-outline-variant/30 shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-raised)] hover:-translate-y-1 bg-surface-white'
                              : 'border-outline-variant/20 bg-surface-white',
                          ].join(' ')}
                        >
                          <div className="flex flex-col md:flex-row">
                            {/* Image */}
                            <div className="w-full md:w-1/3 h-48 md:h-auto relative flex-shrink-0 bg-surface-container-low">
                              {place.photo_url ? (
                                <img
                                  src={place.photo_url}
                                  alt={place.name}
                                  className="absolute inset-0 w-full h-full object-cover"
                                  onError={(e) => { e.target.style.display = 'none' }}
                                />
                              ) : (
                                <div className="absolute inset-0 flex items-center justify-center">
                                  <span className="material-symbols-outlined text-4xl text-on-surface-muted">
                                    image_not_supported
                                  </span>
                                </div>
                              )}

                              {/* Must-see badge */}
                              {place.must_see && (
                                <div className="absolute top-4 left-4 bg-primary/80 backdrop-blur-md rounded-full px-3 py-1 flex items-center gap-1">
                                  <span className="material-symbols-outlined text-secondary-container text-[14px] icon-filled">
                                    star
                                  </span>
                                  <span className="text-xs font-semibold text-white" style={{ fontFamily: 'var(--font-body)' }}>
                                    Must See
                                  </span>
                                </div>
                              )}
                            </div>

                            {/* Content */}
                            <div className="p-6 md:p-8 flex-1 flex flex-col justify-between">
                              <div>
                                <div className="flex justify-between items-start mb-2">
                                  <h4
                                    className={[
                                      'text-2xl font-semibold leading-8',
                                      !isConfirmed ? 'text-on-surface-muted line-through decoration-1' : 'text-primary',
                                    ].join(' ')}
                                    style={{ fontFamily: 'var(--font-display)' }}
                                  >
                                    {place.name}
                                  </h4>
                                  <span
                                    className="text-xs font-semibold text-on-surface-muted bg-surface-container py-1 px-3 rounded-full flex-shrink-0 ml-2"
                                    style={{ fontFamily: 'var(--font-body)' }}
                                  >
                                    {place.suggested_duration}
                                  </span>
                                </div>

                                <p className="text-sm text-on-surface-muted mb-1" style={{ fontFamily: 'var(--font-body)' }}>
                                  <span className="material-symbols-outlined text-[14px] align-text-bottom mr-1">location_on</span>
                                  {place.address}
                                </p>
                                <p className="text-sm text-on-surface-muted mb-3" style={{ fontFamily: 'var(--font-body)' }}>
                                  <span className="material-symbols-outlined text-[14px] align-text-bottom mr-1">schedule</span>
                                  {place.hours_of_operation}
                                </p>

                                <p className="text-base text-on-surface-muted mb-3" style={{ fontFamily: 'var(--font-body)' }}>
                                  {place.description}
                                </p>

                                {place.persona_note && (
                                  <div className="bg-secondary/10 rounded-r-lg py-2 px-3 border-l-[3px] border-secondary">
                                    <p
                                      className="text-xs italic font-semibold text-secondary"
                                      style={{ fontFamily: 'var(--font-body)' }}
                                    >
                                      {place.persona_note}
                                    </p>
                                  </div>
                                )}
                              </div>

                              {/* Toggle */}
                              <div className="flex items-center justify-between border-t border-outline-variant/30 pt-4 mt-4">
                                <div className={['flex items-center gap-2', isConfirmed ? 'text-secondary font-bold drop-shadow-sm' : 'text-outline'].join(' ')}>
                                  <span className="material-symbols-outlined text-[18px] icon-filled">
                                    {isConfirmed ? 'check_circle' : 'cancel'}
                                  </span>
                                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
                                    {isConfirmed ? 'Selected' : 'Not selected'}
                                  </span>
                                </div>

                                <button
                                  type="button"
                                  onClick={() => togglePlace(place.place_id)}
                                  className="relative inline-flex items-center cursor-pointer gap-3"
                                >
                                  <div className={['w-11 h-6 rounded-full relative transition-colors', isConfirmed ? 'bg-primary' : 'bg-surface-high'].join(' ')}>
                                    <div className={['absolute top-[2px] left-[2px] bg-white border border-outline-variant rounded-full h-5 w-5 transition-transform duration-200', isConfirmed ? 'translate-x-full' : ''].join(' ')} />
                                  </div>
                                  <span className="text-xs font-semibold text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
                                    {isConfirmed ? 'Keep' : 'Add back'}
                                  </span>
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ── Floating bottom bar: Refine textarea + Finalize button ── */}
      <div className="fixed bottom-0 left-0 w-full p-4 md:p-8 bg-gradient-to-t from-surface via-surface/90 to-transparent z-50 flex flex-col items-center pointer-events-none">

        {/* Refine textarea */}
        <div className="pointer-events-auto w-full max-w-4xl mx-auto mb-4 px-5 md:px-0">
          <div className="glass rounded-2xl p-4 shadow-[0px_4px_20px_rgba(10,25,47,0.05)] border border-outline-variant/30 bg-surface/80">
            <label
              className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-3"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              Refine Your Itinerary
            </label>
            <form onSubmit={handleRefine} className="relative flex items-center">
              <textarea
                id="refine-input"
                rows={1}
                className="w-full bg-surface-container-low border-none rounded-xl py-3 pl-4 pr-12 text-base focus:ring-1 focus:ring-primary resize-none"
                placeholder={isLoading || hasError ? 'Please wait…' : 'Tell me how else I can make your trip better…'}
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                disabled={isLoading || hasError}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleRefine(e)
                  }
                }}
              />
              <button
                type="submit"
                disabled={!refineText.trim() || isLoading || hasError}
                className="absolute right-2 p-2 text-primary hover:text-primary-tint transition-colors flex items-center justify-center disabled:opacity-40"
                aria-label="Submit refinement"
              >
                <span className="material-symbols-outlined">auto_awesome</span>
              </button>
            </form>
          </div>
        </div>

        {/* Finalize button */}
        <button
          id="finalize-itinerary-btn"
          onClick={handleFinalize}
          disabled={isLoading || hasError || confirmedCount === 0}
          className="pointer-events-auto bg-primary text-white font-semibold text-xs uppercase tracking-widest px-8 py-4 rounded-2xl flex items-center justify-center min-w-[280px] gap-2 active:scale-95 transition-all hover:bg-primary-tint shadow-[0px_8px_32px_rgba(10,25,47,0.2)] disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ fontFamily: 'var(--font-body)' }}
        >
          {actionStatus === 'finalizing' ? 'Finalizing…' : 'Finalize Itinerary'}
          <span className="material-symbols-outlined text-[18px]">
            {actionStatus === 'finalizing' ? 'sync' : 'check_circle'}
          </span>
        </button>
      </div>

      {/* Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-surface/80 backdrop-blur-sm">
          <div 
            className="bg-surface-white border border-outline-variant/30 shadow-[var(--shadow-raised)] rounded-3xl p-8 relative"
            style={{ width: '100%', maxWidth: '28rem' }}
          >
            <h3 className="text-2xl font-semibold text-primary mb-4" style={{ fontFamily: 'var(--font-display)' }}>
              Are you sure?
            </h3>
            <p className="text-base text-on-surface-muted mb-6" style={{ fontFamily: 'var(--font-body)' }}>
              You have selected to visit the following places:
              <br /><br />
              <strong className="text-on-surface block mb-4 break-words">{exceededData?.places.join(', ')}</strong>
              But the total time needed is ~{exceededData?.calculated} hours, which exceeds the time you specified ({duration}). Would you like to proceed anyway?
            </p>
            <div className="flex gap-4">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="flex-1 bg-surface-container-low text-on-surface font-semibold text-xs uppercase tracking-widest px-6 py-3 rounded-xl transition-colors hover:bg-surface-container"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowConfirmModal(false)
                  callSelect('finalize')
                }}
                className="flex-1 bg-primary text-white font-semibold text-xs uppercase tracking-widest px-6 py-3 rounded-xl transition-all hover:bg-primary-tint active:scale-95"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                Proceed
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

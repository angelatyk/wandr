import { useEffect, useState } from 'react'

function normalizeImageSrc(src) {
  if (typeof src !== 'string') return null
  const trimmed = src.trim()
  return trimmed.length > 0 ? trimmed : null
}

function StopImageFallback({ alt, className }) {
  return (
    <div className={[className, 'bg-surface-container text-on-surface-muted flex items-center justify-center'].join(' ')}>
      <div className="flex flex-col items-center gap-1">
        <span className="material-symbols-outlined text-[28px]">image</span>
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
          {alt ? `${alt} image unavailable` : 'Image unavailable'}
        </span>
      </div>
    </div>
  )
}

function StopImage({ src, alt, className }) {
  const [resolvedSrc, setResolvedSrc] = useState(() => normalizeImageSrc(src))

  useEffect(() => {
    setResolvedSrc(normalizeImageSrc(src))
  }, [src])

  if (!resolvedSrc) {
    return <StopImageFallback alt={alt} className={className} />
  }

  return (
    <img
      src={resolvedSrc}
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => {
        setResolvedSrc(null)
      }}
    />
  )
}

/**
 * StopCard — a single itinerary stop card used in the timeline.
 *
 * Supports two layout variants controlled by the `variant` prop:
 *
 *  - 'itinerary' (default): vertical card with a play button for audio narration.
 *    Actively used by ItineraryPage inside the scrollable timeline.
 *
 *  - 'verify': horizontal card with a keep/remove toggle.
 *    This variant is available for future use; VerifyPage currently renders
 *    its own inline card markup for finer control over the confirm flow.
 *
 * @param {object}   props
 * @param {object}   props.stop          — stop data object (name, image, description, etc.)
 * @param {string}   [props.variant]     — 'itinerary' | 'verify' (default: 'itinerary')
 * @param {boolean}  [props.included]    — verify variant: whether the stop is toggled on
 * @param {function} [props.onToggle]    — verify variant: called when the toggle changes
 * @param {function} [props.onPlay]      — itinerary variant: called when the play button is clicked
 * @param {boolean}  [props.active]      — itinerary variant: highlights the card when its audio is playing
 * @param {function} [props.onViewMap]   — itinerary variant: scrolls the map to this stop
 */
export default function StopCard({ stop, variant = 'itinerary', included = true, onToggle, onPlay, active = false, onViewMap }) {
  const isVerify = variant === 'verify'
  const removed = isVerify && !included

  return (
    <div
      className={[
        'rounded-2xl overflow-hidden transition-all duration-300 border',
        removed
          ? 'opacity-60 border-outline-variant/30'
          : active
          ? 'border-secondary shadow-[var(--shadow-raised)]'
          : 'border-outline-variant/30 shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-raised)] hover:-translate-y-1',
        'bg-surface-white',
      ].join(' ')}
    >
      {isVerify ? (
        /* ── Verify layout: horizontal card with image left, content right ── */
        <div className="flex flex-col md:flex-row">
          {/* Image */}
          <div className="w-full md:w-1/3 h-48 md:h-auto relative flex-shrink-0">
            <StopImage
              src={stop.image}
              alt={stop.name}
              className={['absolute inset-0 w-full h-full object-cover', removed ? 'grayscale-[40%]' : ''].join(' ')}
            />
            <div className="absolute top-4 left-4 bg-primary/80 backdrop-blur-md rounded-full px-3 py-1 flex items-center gap-1">
              <span
                className="material-symbols-outlined text-secondary-container text-[14px] icon-filled"
              >
                {stop.personaIcon}
              </span>
              <span className="text-xs font-semibold text-white capitalize" style={{ fontFamily: 'var(--font-body)' }}>
                {stop.persona}
              </span>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 md:p-8 flex-1 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start mb-2">
                <h4
                  className={[
                    'text-2xl font-semibold leading-8',
                    removed ? 'text-on-surface-muted line-through decoration-1' : 'text-primary',
                  ].join(' ')}
                  style={{ fontFamily: 'var(--font-display)' }}
                >
                  {stop.name}
                </h4>
                <span
                  className="text-xs font-semibold text-on-surface-muted bg-surface-container py-1 px-3 rounded-full flex-shrink-0 ml-2"
                  style={{ fontFamily: 'var(--font-body)' }}
                >
                  {stop.time}
                </span>
              </div>
              <p className="text-base text-on-surface-muted mb-4" style={{ fontFamily: 'var(--font-body)' }}>
                {stop.description}
              </p>
            </div>

            {/* Action row */}
            <div className="flex items-center justify-between border-t border-outline-variant/30 pt-4 mt-2">
              <div className={['flex items-center gap-2', removed ? 'text-outline' : 'text-secondary'].join(' ')}>
                <span className="material-symbols-outlined text-[18px] icon-filled">
                  {removed ? 'cancel' : 'verified'}
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
                  {removed ? 'Marked for removal' : stop.badge}
                </span>
              </div>

              {/* Keep/remove toggle */}
              <label className="relative inline-flex items-center cursor-pointer gap-3">
                <input
                  type="checkbox"
                  checked={included}
                  onChange={onToggle}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-high rounded-full peer peer-checked:bg-primary peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:border-outline-variant after:rounded-full after:h-5 after:w-5 after:transition-all relative" />
                <span className="text-xs font-semibold text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
                  {included ? 'Keep' : 'Add back'}
                </span>
              </label>
            </div>
          </div>
        </div>
      ) : (
        /* ── Itinerary layout: vertical card with full-width image and play button ── */
        <>
          {/* Image */}
          <div className="relative w-full h-48">
            <StopImage src={stop.image} alt={stop.name} className="w-full h-full object-cover" />
            <div className="absolute top-4 right-4 bg-surface/80 backdrop-blur-md rounded-full px-3 py-1 flex items-center gap-2 border border-outline-variant/20">
              <span className="material-symbols-outlined text-secondary text-[16px]">schedule</span>
              <span className="text-xs font-semibold text-on-surface" style={{ fontFamily: 'var(--font-body)' }}>
                {stop.time}
              </span>
            </div>
          </div>

          {/* Body */}
          <div className="p-6 flex flex-col gap-3">
            <div className="flex justify-between items-start">
              <h2
                className="text-2xl font-semibold text-primary leading-8"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {stop.name}
              </h2>
              <button
                aria-label={
                  stop.hasAudio
                    ? `Play narration for ${stop.name}`
                    : `Narration audio not ready for ${stop.name}`
                }
                onClick={onPlay}
                disabled={!stop.hasAudio}
                className={[
                  'w-10 h-10 rounded-full flex items-center justify-center transition-colors flex-shrink-0',
                  stop.hasAudio
                    ? 'bg-primary-container text-white hover:bg-primary'
                    : 'bg-surface-container text-on-surface-muted cursor-not-allowed opacity-60',
                ].join(' ')}
              >
                <span className="material-symbols-outlined icon-filled text-[20px]">
                  {stop.hasAudio ? 'play_arrow' : 'hourglass_empty'}
                </span>
              </button>
            </div>

            <p className="text-base text-on-surface-muted line-clamp-2" style={{ fontFamily: 'var(--font-body)' }}>
              {stop.description}
            </p>

            <div className="flex items-center gap-4 mt-1">
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  if (onViewMap) onViewMap()
                }}
                className="text-xs font-semibold uppercase tracking-widest text-secondary hover:text-primary transition-colors flex items-center gap-1"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                <span className="material-symbols-outlined text-[16px]">map</span>
                View on map
              </a>
              <span className="text-outline-variant">|</span>
              <span
                className="text-xs font-semibold text-on-surface-muted flex items-center gap-1"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                <span className="material-symbols-outlined text-[16px]">
                  {stop.hasAudio ? 'headphones' : 'article'}
                </span>
                {stop.hasAudio ? `${stop.narrationLength} narration` : 'Text only — audio pending'}
              </span>
              {stop.suggestedDuration && (
                <>
                  <span className="text-outline-variant">|</span>
                  <span
                    className="text-xs font-semibold text-on-surface-muted flex items-center gap-1 capitalize"
                    style={{ fontFamily: 'var(--font-body)' }}
                  >
                    <span className="material-symbols-outlined text-[16px]">schedule</span>
                    {stop.suggestedDuration}
                  </span>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

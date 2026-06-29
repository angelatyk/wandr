/**
 * StopCard — a single itinerary stop displayed in the timeline.
 *
 * Used on both the Verify page (with a keep/remove toggle)
 * and the Itinerary page (with a play button).
 *
 * Props:
 *   stop         — stop data object from mockItinerary
 *   variant      — 'verify' | 'itinerary'
 *   included     — controlled toggle state (verify variant)
 *   onToggle     — () => void (verify variant)
 *   onPlay       — () => void (itinerary variant)
 *   active       — boolean, highlights the card when its audio is playing
 */
export default function StopCard({ stop, variant = 'itinerary', included = true, onToggle, onPlay, active = false }) {
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
        /* ── Verify layout: horizontal card ── */
        <div className="flex flex-col md:flex-row">
          {/* Image */}
          <div className="w-full md:w-1/3 h-48 md:h-auto relative flex-shrink-0">
            <img
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
        /* ── Itinerary layout: vertical card ── */
        <>
          {/* Image */}
          <div className="relative w-full h-48">
            <img src={stop.image} alt={stop.name} className="w-full h-full object-cover" />
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
                aria-label={`Play narration for ${stop.name}`}
                onClick={onPlay}
                className="w-10 h-10 rounded-full bg-primary-container text-white flex items-center justify-center hover:bg-primary transition-colors flex-shrink-0"
              >
                <span className="material-symbols-outlined icon-filled text-[20px]">play_arrow</span>
              </button>
            </div>

            <p className="text-base text-on-surface-muted line-clamp-2" style={{ fontFamily: 'var(--font-body)' }}>
              {stop.description}
            </p>

            <div className="flex items-center gap-4 mt-1">
              <a
                href="#"
                className="text-xs font-semibold uppercase tracking-widest text-secondary hover:text-primary transition-colors flex items-center gap-1"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                <span className="material-symbols-outlined text-[16px]">map</span>
                View Map
              </a>
              <span className="text-outline-variant">|</span>
              <span
                className="text-xs font-semibold text-on-surface-muted flex items-center gap-1"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                <span className="material-symbols-outlined text-[16px]">headphones</span>
                {stop.narrationLength} narration
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

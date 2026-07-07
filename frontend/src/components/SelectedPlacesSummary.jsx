import React from 'react'

/**
 * Displays a fixed-position summary list of selected places (desktop only).
 * 
 * @param {Object} props
 * @param {Set<string>} props.confirmed - Set of confirmed place IDs
 * @param {Map<string, string>} props.placeNames - Map of place ID to place name
 * @param {Function} props.onRemoveAll - Callback to clear all selected places
 */
export default function SelectedPlacesSummary({ confirmed, placeNames, onRemoveAll }) {
  if (confirmed.size === 0) return null

  const handleScrollToCard = (id) => {
    const el = document.getElementById(`place-card-${id}`)
    if (el) {
      // Offset scrolling slightly to account for the sticky header
      const y = el.getBoundingClientRect().top + window.scrollY - 100
      window.scrollTo({ top: y, behavior: 'smooth' })
      
      // Add a brief highlight
      const cardInner = el.querySelector('.place-card-inner')
      if (cardInner) {
        cardInner.classList.add('ring-2', 'ring-primary', 'shadow-[var(--shadow-raised)]')
        setTimeout(() => {
          cardInner.classList.remove('ring-2', 'ring-primary', 'shadow-[var(--shadow-raised)]')
        }, 1500)
      }
    }
  }

  return (
    <div className="hidden xl:block fixed top-32 right-4 2xl:right-12 w-64 glass rounded-2xl p-5 shadow-[0px_4px_20px_rgba(10,25,47,0.05)] border border-outline-variant/30 bg-surface-white/80 backdrop-blur-md max-h-[60vh] overflow-y-auto z-40">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest" style={{ fontFamily: 'var(--font-body)' }}>
          Selected ({confirmed.size})
        </h3>
        <button
          onClick={onRemoveAll}
          className="text-xs font-semibold text-primary hover:text-primary-tint transition-colors"
          style={{ fontFamily: 'var(--font-body)' }}
        >
          Remove All
        </button>
      </div>
      <ul className="flex flex-col gap-3">
        {Array.from(confirmed).map(id => (
          <li 
            key={id} 
            className="flex items-start gap-2 text-sm text-on-surface font-medium leading-tight cursor-pointer hover:text-primary transition-colors group"
            onClick={() => handleScrollToCard(id)}
          >
            <span className="material-symbols-outlined text-[16px] text-secondary mt-0.5 icon-filled shrink-0 group-hover:scale-110 transition-transform">check_circle</span>
            <span style={{ fontFamily: 'var(--font-body)' }}>{placeNames.get(id)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

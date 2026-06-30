import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

/**
 * PersonaCard — a single selectable explorer persona.
 *
 * When selected it gains a gold border and scales up slightly,
 * per the Stitch design spec.
 */
function PersonaCard({ persona, selected, onClick }) {
  return (
    <button
      onClick={() => onClick(persona.id)}
      aria-pressed={selected}
      className={[
        'group text-left rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1 relative overflow-hidden cursor-pointer',
        'bg-surface-white border',
        selected
          ? 'border-secondary shadow-[0px_8px_30px_rgba(212,175,55,0.18)] scale-[1.02]'
          : 'border-outline-variant hover:border-secondary hover:shadow-[0px_8px_30px_rgba(116,92,0,0.10)]',
      ].join(' ')}
      style={{ boxShadow: selected ? undefined : 'var(--shadow-card)' }}
    >
      {/* Hover gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary-fixed/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

      <div className="relative z-10 flex flex-col h-full justify-between gap-3">
        {/* Icon */}
        <div
          className={[
            'w-12 h-12 rounded-full flex items-center justify-center transition-colors',
            selected
              ? 'bg-secondary/20 text-secondary'
              : 'bg-surface-low text-on-surface-muted group-hover:text-secondary group-hover:bg-secondary/10',
          ].join(' ')}
        >
          <span
            className="material-symbols-outlined text-[22px]"
            style={{ fontVariationSettings: selected ? "'FILL' 1" : "'FILL' 0" }}
          >
            {persona.icon}
          </span>
        </div>

        {/* Text */}
        <div>
          <h3
            className="text-[20px] leading-7 font-semibold text-on-surface mb-1"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            {persona.label}
          </h3>
          <p className="text-sm leading-5 text-on-surface-muted" style={{ fontFamily: 'var(--font-body)' }}>
            {persona.description}
          </p>
        </div>

        {/* Selected indicator */}
        {selected && (
          <div className="flex items-center gap-1 text-secondary">
            <span className="material-symbols-outlined text-[16px] icon-filled">check_circle</span>
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-body)' }}>
              Selected
            </span>
          </div>
        )}
      </div>
    </button>
  )
}

/**
 * PersonaGrid — renders all persona cards and tracks selection.
 * Navigates to /refine on CTA click.
 */
export default function PersonaGrid({ personas }) {
  const [selected, setSelected] = useState(null)
  const navigate = useNavigate()

  const handleSelect = (id) => setSelected((prev) => (prev === id ? null : id))

  return (
    <section className="py-6">
      <div className="mb-6 flex justify-between items-end">
        <div>
          <h2
            className="text-2xl font-semibold text-on-surface mb-2"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Choose Your Persona
          </h2>
          <p className="text-base text-on-surface-muted max-w-2xl" style={{ fontFamily: 'var(--font-body)' }}>
            Tailor your exploration narrative. Select a lens through which to experience your next destination.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        {personas.map((p) => (
          <PersonaCard
            key={p.id}
            persona={p}
            selected={selected === p.id}
            onClick={handleSelect}
          />
        ))}
      </div>

      {/* Continue CTA — only enabled when a persona is picked */}
      {selected && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={() => navigate('/refine')}
            className="bg-primary text-white font-semibold text-xs uppercase tracking-widest py-4 px-10 rounded-2xl hover:bg-primary-tint transition-all duration-300 active:scale-95 shadow-[var(--shadow-fab)] flex items-center gap-2"
            style={{ fontFamily: 'var(--font-body)' }}
          >
            Continue
            <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
          </button>
        </div>
      )}
    </section>
  )
}

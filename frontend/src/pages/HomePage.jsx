import { useNavigate } from 'react-router-dom'
import TopNav from '../components/TopNav'
import Footer from '../components/Footer'
import PersonaGrid from '../components/PersonaGrid'
import { PERSONAS } from '../data/mockItinerary'

const HERO_IMAGE =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBVUu8lE_xcx-lNUsttk-9gL5EVt8-wsulBwD6IImFRtCAUGpoYk2iPspkG8AcwCa9iT0quF69HvlbU6MNjY9Kcw9UXCgJZxnu9FqYFxlgblD-h1CoEKbJFp9Nm782sYjSiMia3yY4h8Jdu2ppQ8PjxxiKJ1jf8rHeZ98VDJffaNAxy3eZ9-Dc2VUJ8EpCNTuQvJm3TDOjOLvxkCxtaRpP7Y1biyvBWgMMPVlShNF4tMLJL5TzHz-V_GsASkzMlIgXYTw9Gor6mp_fx'

/**
 * HomePage — Wandr onboarding.
 *
 * Screens covered:
 *   1. Hero section with cinematic travel image + quick-wander input
 *   2. Persona selection grid
 */
export default function HomePage() {
  const navigate = useNavigate()

  const handleQuickWander = (e) => {
    e.preventDefault()
    navigate('/refine')
  }

  return (
    <div className="min-h-screen flex flex-col">
      <TopNav />

      <main className="flex-1 pt-20 md:pt-32 pb-12 px-5 md:px-16 max-w-screen-2xl mx-auto w-full">

        {/* ── Hero ── */}
        <section className="relative min-h-[614px] md:min-h-[700px] rounded-2xl overflow-hidden mb-12 flex flex-col justify-end p-6 md:p-16">
          {/* Background image */}
          <div
            className="absolute inset-0 bg-cover bg-center"
            style={{ backgroundImage: `url("${HERO_IMAGE}")` }}
          />
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-primary/80 via-primary/20 to-transparent" />

          {/* Content */}
          <div className="relative z-10 max-w-3xl">
            <h1
              className="text-4xl md:text-6xl font-bold text-white mb-3 drop-shadow-md"
              style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em', lineHeight: '1.1' }}
            >
              Your AI Travel Guide, Narrated.
            </h1>
            <p
              className="text-lg text-white/90 mb-6 max-w-xl"
              style={{ fontFamily: 'var(--font-body)', lineHeight: '1.7' }}
            >
              Curated experiences for the sophisticated explorer. Discover the hidden stories of every city through immersive, personalized audio journeys.
            </p>

            {/* Quick Wander form */}
            <form
              onSubmit={handleQuickWander}
              className="glass rounded-2xl p-6 flex flex-col gap-4 max-w-2xl shadow-[var(--shadow-overlay)]"
            >
              {/* Natural language input */}
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="vibe"
                  className="text-xs font-semibold uppercase tracking-widest text-on-surface-muted"
                  style={{ fontFamily: 'var(--font-body)' }}
                >
                  Tell us your vibe
                </label>
                <div className="relative flex items-start bg-surface-white rounded-xl px-3 border border-transparent focus-within:border-outline-variant transition-colors overflow-hidden">
                  <span className="material-symbols-outlined text-outline ml-2 mt-4 flex-shrink-0 text-[20px]">auto_awesome</span>
                  <textarea
                    id="vibe"
                    rows={3}
                    placeholder="Describe your perfect afternoon… or use the fields below."
                    className="w-full bg-transparent border-none focus:outline-none text-base text-on-surface placeholder:text-outline py-4 px-3 resize-none"
                    style={{ fontFamily: 'var(--font-body)' }}
                  />
                </div>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3 px-2">
                <div className="h-px flex-1 bg-outline-variant/30" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-outline" style={{ fontFamily: 'var(--font-body)' }}>
                  OR
                </span>
                <div className="h-px flex-1 bg-outline-variant/30" />
              </div>

              {/* Structured fields */}
              <div className="flex flex-col md:flex-row gap-3">
                <div className="flex-1 flex items-center bg-surface-white/70 rounded-xl px-3 border border-transparent focus-within:border-outline-variant transition-colors">
                  <span className="material-symbols-outlined text-outline ml-2 flex-shrink-0 text-[20px]">location_on</span>
                  <input
                    type="text"
                    placeholder="Current location"
                    className="w-full bg-transparent border-none focus:outline-none text-base text-on-surface placeholder:text-outline py-3 px-3"
                    style={{ fontFamily: 'var(--font-body)' }}
                  />
                </div>
                <div className="flex-1 flex items-center bg-surface-white/70 rounded-xl px-3 border border-transparent focus-within:border-outline-variant transition-colors">
                  <span className="material-symbols-outlined text-outline ml-2 flex-shrink-0 text-[20px]">schedule</span>
                  <select
                    className="w-full bg-transparent border-none focus:outline-none text-base text-on-surface py-3 px-3 appearance-none"
                    style={{ fontFamily: 'var(--font-body)' }}
                    defaultValue=""
                  >
                    <option value="" disabled>Time available?</option>
                    <option value="1h">1 Hour</option>
                    <option value="2h">2 Hours</option>
                    <option value="half-day">Half Day</option>
                  </select>
                </div>
              </div>

              {/* CTA */}
              <button
                type="submit"
                className="bg-primary text-white font-semibold text-xs uppercase tracking-widest py-4 px-8 rounded-xl hover:bg-primary-tint transition-colors duration-300 active:scale-95 w-full md:w-auto md:self-end"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                Quick Wander
              </button>
            </form>
          </div>
        </section>

        {/* ── Persona Grid ── */}
        <PersonaGrid personas={PERSONAS} />

      </main>

      <Footer />

      {/* Bottom nav spacer on mobile */}
      <div className="md:hidden h-20" />
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { usePlanStream } from '../hooks/usePlanStream'

const BG_IMAGE =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBp84ZOjCpvluLOY7ZPL2dz4sa1qgsmt9eva8l3TOOkZCNgxmEySmGTNDs1NmbmIA1wE8M7h7b1ssWWtlH3MYdME3K5VGDNH0nry6dmayVzYPyhFpHZHVVBka7hqRTqZLFr-q2dz3upp95oO4fXrmOhIwyzzqLanl-Xxs2xIDFPiMAUFTpcUrlvGwVW3-sbqbSQKqllFxsMWYDujsb6CHXydtsPm4kUvnE5PEiFYqW6T72EGcVd9umT9Y9z_w-4mmBiOYYNPPP9JrjF'

/**
 * RefinePage — AI profiler clarification form.
 *
 * Step 2 of 3 in the onboarding flow.
 * Background: full-bleed travel photo fading to surface colour.
 *
 * Gradient overlays use inline rgba() values because Tailwind v4 does not
 * support the `color/opacity` shorthand for CSS-variable-based colours.
 */
export default function RefinePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const planId = searchParams.get('planId')

  // Subscribe to the backend SSE stream to monitor pipeline progress
  const { status, clarification } = usePlanStream(planId)
  
  const [reply, setReply] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!planId) {
      navigate('/')
      return
    }
    // Auto-advance once the profiler hands off — the itinerary agent will fire next.
    // awaiting_selection = itinerary options ready for user to review on VerifyPage.
    // If the profiler had no clarifying questions, this skips the refine page entirely.
    if (
      status === 'planning' ||
      status === 'awaiting_selection' ||
      status === 'finalised' ||
      status === 'routing' ||
      status === 'complete'
    ) {
      navigate(`/verify?planId=${planId}`)
    }
  }, [status, navigate, planId])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!reply) return
    
    setSubmitting(true)
    try {
      await fetch(`/api/plan/${planId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vibe: reply }) // We send the reply as vibe/context
      })
      // Reload page to re-establish SSE stream connection
      window.location.reload()
    } catch (err) {
      console.error(err)
      setSubmitting(false)
    }
  }

  const isLoading = status === 'initializing' || submitting

  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-x-hidden">
      {/* ── Background ── */}
      <div className="absolute inset-0 z-0">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('${BG_IMAGE}')`, opacity: 0.55 }}
        />
        <div
          className="absolute inset-0 z-10"
          style={{
            background:
              'linear-gradient(to bottom, rgba(248,249,250,0.3) 0%, rgba(248,249,250,0.75) 40%, rgba(248,249,250,1) 80%)',
          }}
        />
      </div>

      {/* ── Content ── */}
      <main
        className="relative z-20 w-full px-5 py-12 flex flex-col gap-10"
        style={{ maxWidth: '640px' }}
      >
        {/* ── Header ── */}
        <header className="text-center flex flex-col items-center gap-4">
          <a
            href="/"
            className="cursor-pointer"
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: 'clamp(2rem, 6vw, 3.5rem)',
              letterSpacing: '-0.02em',
              color: 'var(--wandr-primary)',
              lineHeight: 1.1,
            }}
          >
            Wandr
          </a>

          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: 'clamp(1.75rem, 5vw, 3rem)',
              letterSpacing: '-0.01em',
              lineHeight: 1.15,
              color: 'var(--wandr-primary)',
            }}
          >
            {isLoading ? 'Consulting the Oracle...' : 'Just a few more details.'}
          </h1>

          <p
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: '1.0625rem',
              lineHeight: 1.7,
              color: 'var(--wandr-on-surface-muted)',
              maxWidth: '26rem',
              textAlign: 'center',
            }}
          >
            {isLoading 
              ? 'Our AI travel guide is analyzing your request to craft the perfect itinerary.' 
              : 'To curate the perfect itinerary, I need a little more direction on your upcoming journey.'}
          </p>
          
          {isLoading && (
            <div className="mt-8">
               <span className="material-symbols-outlined text-4xl text-primary animate-spin">sync</span>
            </div>
          )}
        </header>

        {/* ── Form card ── */}
        {!isLoading && status === 'needs_clarification' && (
          <form
            onSubmit={handleSubmit}
            className="relative overflow-hidden flex flex-col gap-7"
            style={{
              background: 'rgba(255,255,255,0.75)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(255,255,255,0.4)',
              borderRadius: '1.25rem',
              padding: 'clamp(1.5rem, 4vw, 2.5rem)',
              boxShadow: '0 8px 40px rgba(10,25,47,0.08)',
            }}
          >
            <div
              className="absolute top-0 left-0 w-full"
              style={{
                height: '3px',
                background:
                  'linear-gradient(to right, transparent, var(--wandr-secondary), transparent)',
                opacity: 0.7,
              }}
            />

            <div className="flex flex-col gap-2">
              <label
                htmlFor="reply"
                className="flex items-center gap-3 cursor-pointer"
                style={{
                  fontFamily: 'var(--font-display)',
                  fontWeight: 600,
                  fontSize: '1.3rem',
                  color: 'var(--wandr-primary)',
                }}
              >
                <span
                  className="material-symbols-outlined icon-filled"
                  style={{ fontSize: '1.5rem', color: 'var(--wandr-secondary)' }}
                >
                  psychology_alt
                </span>
                {clarification || 'Could you provide a bit more context?'}
              </label>
              <textarea
                id="reply"
                rows={3}
                placeholder="Type your answer here..."
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: '1.0625rem',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: '2px solid var(--wandr-outline-variant)',
                  padding: '0.6rem 0',
                  color: 'var(--wandr-on-surface)',
                  outline: 'none',
                  transition: 'border-color 0.2s',
                  width: '100%',
                  resize: 'none'
                }}
                onFocus={(e) => (e.target.style.borderBottomColor = 'var(--wandr-primary)')}
                onBlur={(e) => (e.target.style.borderBottomColor = 'var(--wandr-outline-variant)')}
              />
            </div>

            <div className="flex justify-end mt-2">
              <button
                type="submit"
                disabled={submitting}
                className="group flex items-center gap-2 cursor-pointer active:scale-95 transition-all duration-300 disabled:opacity-50"
                style={{
                  fontFamily: 'var(--font-body)',
                  fontWeight: 600,
                  fontSize: '0.7rem',
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#ffffff',
                  background: 'var(--wandr-primary-container)',
                  padding: '1rem 2rem',
                  borderRadius: '1rem',
                  boxShadow: '0px 4px 20px rgba(13,28,50,0.18)',
                  border: 'none',
                  transition: 'background 0.3s, transform 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--wandr-primary)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--wandr-primary-container)')}
              >
                {submitting ? 'Sending...' : 'Continue'}
                <span
                  className="material-symbols-outlined group-hover:translate-x-1 transition-transform"
                  style={{ fontSize: '1.2rem' }}
                >
                  arrow_forward
                </span>
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  )
}

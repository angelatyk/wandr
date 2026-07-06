import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../hooks/useAuth'

const GIS_SRC = 'https://accounts.google.com/gsi/client'

function loadGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve()
    const existing = document.querySelector(`script[src="${GIS_SRC}"]`)
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', reject)
      return
    }
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = reject
    document.head.appendChild(script)
  })
}

/**
 * SignInPage — shown when there is no active session.
 * Supports Google Sign-In (when configured) and a local dev login fallback.
 */
export default function SignInPage() {
  const { config, loginWithGoogle, devLogin } = useAuth()
  const googleButtonRef = useRef(null)
  const [error, setError] = useState(null)
  const [devEmail, setDevEmail] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const clientId = config.google_client_id
    if (!clientId || !googleButtonRef.current) return

    let cancelled = false
    loadGoogleScript()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id) return
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response) => {
            try {
              await loginWithGoogle(response.credential)
            } catch {
              setError('Google sign-in failed. Please try again.')
            }
          },
        })
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
        })
      })
      .catch(() => setError('Could not load Google sign-in.'))

    return () => {
      cancelled = true
    }
  }, [config.google_client_id, loginWithGoogle])

  const handleDevLogin = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await devLogin(devEmail.trim())
    } catch {
      setError('Dev login failed.')
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-6">
      <div className="w-full max-w-md rounded-2xl bg-surface-white border border-outline-variant/30 shadow-[var(--shadow-card)] p-8 md:p-10">
        <h1
          className="text-4xl font-bold text-primary tracking-tight mb-2"
          style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em' }}
        >
          Wandr
        </h1>
        <p className="text-base text-on-surface-muted mb-8" style={{ fontFamily: 'var(--font-body)' }}>
          Sign in to plan and save your narrated trips.
        </p>

        {config.google_client_id ? (
          <div className="flex justify-center mb-6">
            <div ref={googleButtonRef} />
          </div>
        ) : (
          <p className="text-sm text-on-surface-muted mb-6" style={{ fontFamily: 'var(--font-body)' }}>
            Google sign-in isn’t configured on this server.
          </p>
        )}

        {config.dev_login_available && (
          <form onSubmit={handleDevLogin} className="border-t border-outline-variant/20 pt-6">
            <label
              className="block text-xs font-semibold uppercase tracking-widest text-on-surface-muted mb-2"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              Local dev login
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                value={devEmail}
                onChange={(e) => setDevEmail(e.target.value)}
                placeholder="dev@wandr.local"
                className="flex-1 rounded-xl border border-outline-variant/40 px-4 py-3 text-sm bg-surface focus:outline-none focus:border-secondary"
                style={{ fontFamily: 'var(--font-body)' }}
              />
              <button
                type="submit"
                disabled={busy}
                className="bg-primary text-white text-xs font-semibold uppercase tracking-widest px-5 py-3 rounded-xl hover:bg-primary-tint transition-colors disabled:opacity-50"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                {busy ? '…' : 'Enter'}
              </button>
            </div>
            <p className="text-xs text-on-surface-muted mt-2" style={{ fontFamily: 'var(--font-body)' }}>
              Development only — disabled automatically in production.
            </p>
          </form>
        )}

        {error && (
          <p className="text-sm text-red-700 mt-4" style={{ fontFamily: 'var(--font-body)' }}>
            {error}
          </p>
        )}
      </div>
    </div>
  )
}

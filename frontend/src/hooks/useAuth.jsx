import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const AuthContext = createContext(null)

async function apiJson(url, options = {}) {
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    const err = new Error(`Request failed: ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

/**
 * AuthProvider — holds the current user session and exposes sign-in/out.
 * Session lives in an httpOnly cookie set by the backend; we never see the token.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [config, setConfig] = useState({ google_client_id: '', dev_login_available: false })
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const cfg = await apiJson('/api/auth/config')
      setConfig(cfg)
    } catch {
      // Config is best-effort; sign-in screen can still show what it knows.
    }
    try {
      const me = await apiJson('/api/auth/me')
      setUser(me.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const loginWithGoogle = useCallback(async (credential) => {
    const data = await apiJson('/api/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    })
    setUser(data.user)
    return data.user
  }, [])

  const devLogin = useCallback(async (email) => {
    const data = await apiJson('/api/auth/dev-login', {
      method: 'POST',
      body: JSON.stringify({ email: email || null }),
    })
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiJson('/api/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
    }
  }, [])

  const value = { user, config, loading, loginWithGoogle, devLogin, logout, refresh }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const authApi = {
  // Real login — backend expects { email, password }
  login: async (email, password) => {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }))
      const message = err?.detail?.error?.message || err?.detail || 'Invalid email or password'
      throw new Error(message)
    }
    return res.json() // { access_token, token_type }
  },

  // DEV ONLY — issues a real JWT by role, no password required.
  // Disable by setting ALLOW_MOCK_LOGIN=false in backend .env before production.
  mockLogin: async (role) => {
    const res = await fetch(`${BASE_URL}/auth/mock-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Mock login failed' }))
      const detail = err?.detail?.error?.message || err?.detail || 'Mock login failed'
      throw new Error(detail)
    }
    return res.json() // { access_token, token_type }
  },

  me: async (token) => {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new Error('Failed to fetch user')
    return res.json()
  },
}
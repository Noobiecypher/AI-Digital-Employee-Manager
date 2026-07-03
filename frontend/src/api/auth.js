const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const authApi = {
  login: async (username, password) => {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(error.detail || 'Invalid credentials')
    }

    return res.json()
  },

  // DEV ONLY — calls POST /auth/mock-login which issues a real JWT by role.
  // No password required. Works as long as ALLOW_MOCK_LOGIN=true in backend .env.
  // To switch to real credentials later: remove the mock buttons in Login.jsx
  // and delete this method.
  mockLogin: async (role) => {
    const res = await fetch(`${BASE_URL}/auth/mock-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Mock login failed' }))
      // Surface the backend error message (e.g. "No active user found with role X")
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
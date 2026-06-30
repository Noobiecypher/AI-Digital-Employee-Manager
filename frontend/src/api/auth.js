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

  me: async (token) => {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new Error('Failed to fetch user')
    return res.json()
  },
}
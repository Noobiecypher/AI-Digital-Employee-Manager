const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getToken() {
  return localStorage.getItem('auth_token')
}

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const token = getToken()

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const config = { headers, ...options }

  let res
  try {
    res = await fetch(url, config)
  } catch (err) {
    throw new Error('Backend offline — start the FastAPI server')
  }

  if (res.status === 401) {
    // Token expired or invalid — force logout
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    window.location.href = '/login'
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `Request failed: ${res.status}`)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get:    (path)       => request(path),
  post:   (path, body) => request(path, { method: 'POST',   body: JSON.stringify(body) }),
  put:    (path, body) => request(path, { method: 'PUT',    body: JSON.stringify(body) }),
  patch:  (path, body) => request(path, { method: 'PATCH',  body: JSON.stringify(body) }),
  delete: (path)       => request(path, { method: 'DELETE' }),
}
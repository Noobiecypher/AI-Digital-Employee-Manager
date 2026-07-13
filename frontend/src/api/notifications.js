import { api } from './client'

const BASE = '/api/notifications'

export const notificationsApi = {
  getAll:   ()   => api.get(BASE),
  markRead: (id) => api.patch(`${BASE}/${id}/read`),
  markAllRead: () => api.patch(`${BASE}/read-all`),
}
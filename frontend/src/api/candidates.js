import { api } from './client'

const BASE = '/api/candidates'

export const candidatesApi = {
  getAll:  ()         => api.get(BASE),
  getOne:  (id)       => api.get(`${BASE}/${id}`),
  create:  (data)     => api.post(BASE, data),
  update:  (id, data) => api.put(`${BASE}/${id}`, data),
  delete:  (id)       => api.delete(`${BASE}/${id}`),
}
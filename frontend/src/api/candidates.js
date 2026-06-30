import { api } from './client'
import { mockCandidates } from '../mock/mockData'

const BASE = '/api/candidates'

export const candidatesApi = {
  getAll:  ()         => api.get(BASE).catch(() => mockCandidates),
  getOne:  (id)       => api.get(`${BASE}/${id}`).catch(() => mockCandidates.find(c => c._id === id) || mockCandidates[0]),
  create:  (data)     => api.post(BASE, data).catch(() => ({ ...data, _id: Date.now().toString() })),
  update:  (id, data) => api.put(`${BASE}/${id}`, data).catch(() => data),
  delete:  (id)       => api.delete(`${BASE}/${id}`).catch(() => null),
}
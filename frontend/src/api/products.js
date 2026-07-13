import { api } from './client'

const BASE = '/api/products'

export const productsApi = {
  getAll:  ()           => api.get(BASE),
  getOne:  (name)       => api.get(`${BASE}/${encodeURIComponent(name)}`),
  create:  (data)       => api.post(BASE, data),
  update:  (name, data) => api.put(`${BASE}/${encodeURIComponent(name)}`, data),
  delete:  (name)       => api.delete(`${BASE}/${encodeURIComponent(name)}`),
}
import { api } from './client'
import { mockProducts } from '../mock/mockData'

const BASE = '/api/products'

export const productsApi = {
  getAll:  ()              => api.get(BASE).catch(() => mockProducts),
  getOne:  (name)          => api.get(`${BASE}/${name}`).catch(() => mockProducts[0]),
  create:  (data)          => api.post(BASE, data).catch(() => ({ ...data })),
  update:  (name, data)    => api.put(`${BASE}/${name}`, data).catch(() => data),
  delete:  (name)          => api.delete(`${BASE}/${name}`).catch(() => null),
}
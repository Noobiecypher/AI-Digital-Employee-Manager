import { api } from './client'
import { mockEmployees } from '../mock/mockData'

const BASE = '/api/employees'

export const employeesApi = {
  getAll:  ()         => api.get(BASE).catch(() => mockEmployees),
  getOne:  (id)       => api.get(`${BASE}/${id}`).catch(() => mockEmployees.find(e => e._id === id) || mockEmployees[0]),
  create:  (data)     => api.post(BASE, data).catch(() => ({ ...data, _id: Date.now().toString() })),
  update:  (id, data) => api.put(`${BASE}/${id}`, data).catch(() => data),
  delete:  (id)       => api.delete(`${BASE}/${id}`).catch(() => null),
}
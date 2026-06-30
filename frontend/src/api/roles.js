import { api } from './client'
import { mockRoles } from '../mock/mockData'

const BASE = '/api/roles'

export const rolesApi = {
  getAll:  ()           => api.get(BASE).catch(() => mockRoles),
  getOne:  (role)       => api.get(`${BASE}/${role}`).catch(() => mockRoles[0]),
  create:  (data)       => api.post(BASE, data).catch(() => ({ ...data })),
  update:  (role, data) => api.put(`${BASE}/${role}`, data).catch(() => data),
  delete:  (role)       => api.delete(`${BASE}/${role}`).catch(() => null),
}
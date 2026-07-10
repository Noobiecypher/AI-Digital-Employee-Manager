import { api } from './client'

// Multipart upload — cannot use api.post() since it uses JSON
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getToken() {
  return localStorage.getItem('auth_token')
}

export const documentsApi = {
  // GET /documents/types
  getTypes: () => api.get('/documents/types'),

  // POST /documents/upload  (multipart)
  upload: async (file, expectedDocumentType, targetContext = null) => {
    const form = new FormData()
    form.append('file', file)
    form.append('expected_document_type', expectedDocumentType)
    if (targetContext && Object.keys(targetContext).length > 0) {
      form.append('target_context', JSON.stringify(targetContext))
    }
    const token = getToken()
    const res = await fetch(`${BASE_URL}/documents/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err?.detail?.error?.message || err?.detail || 'Upload failed')
    }
    return res.json()
  },

  // POST /documents/{document_id}/process
  process: (documentId) => api.post(`/documents/${documentId}/process`),

  // GET /documents
  list: (params = {}) => {
    const q = new URLSearchParams()
    if (params.status)           q.set('status', params.status)
    if (params.document_type)    q.set('document_type', params.document_type)
    if (params.business_domain)  q.set('business_domain', params.business_domain)
    if (params.limit)            q.set('limit', params.limit)
    if (params.offset)           q.set('offset', params.offset)
    return api.get(`/documents${q.toString() ? '?' + q.toString() : ''}`)
  },

  // GET /documents/{document_id}
  getOne: (documentId) => api.get(`/documents/${documentId}`),

  // GET /documents/{document_id}/status
  getStatus: (documentId) => api.get(`/documents/${documentId}/status`),

  // DELETE /documents/{document_id}
  delete: (documentId) => api.delete(`/documents/${documentId}`),

  // GET /documents/eligible?workflow_slot=...
  getEligible: (workflowSlot) => api.get(`/documents/eligible?workflow_slot=${workflowSlot}`),

  // GET /documents/drafts
  listDrafts: (params = {}) => {
    const q = new URLSearchParams()
    if (params.status)                q.set('status', params.status)
    if (params.document_id)           q.set('document_id', params.document_id)
    if (params.target_business_entity) q.set('target_business_entity', params.target_business_entity)
    return api.get(`/documents/drafts${q.toString() ? '?' + q.toString() : ''}`)
  },

  // GET /documents/drafts/{draft_id}
  getDraft: (draftId) => api.get(`/documents/drafts/${draftId}`),

  // GET /documents/drafts/{draft_id}/requirements
  getDraftRequirements: (draftId) => api.get(`/documents/drafts/${draftId}/requirements`),

  // PATCH /documents/drafts/{draft_id}
  updateDraft: (draftId, extractedData) =>
    api.patch(`/documents/drafts/${draftId}`, { extracted_data: extractedData }),

  // POST /documents/drafts/{draft_id}/review
  reviewDraft: (draftId, decision, reviewerNotes = null) =>
    api.post(`/documents/drafts/${draftId}/review`, { decision, reviewer_notes: reviewerNotes }),

  // POST /documents/drafts/{draft_id}/import
  importDraft: (draftId) => api.post(`/documents/drafts/${draftId}/import`),
}
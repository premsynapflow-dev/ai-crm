import api from '../api'

export interface Complaint {
  id: string
  customerName: string
  customerEmail: string
  customerPhone: string
  subject: string
  message: string
  category: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  sentiment: 'positive' | 'neutral' | 'negative'
  aiConfidence: number
  status: 'new' | 'in-progress' | 'resolved' | 'escalated'
  createdAt: string
  updatedAt: string
  suggestedResponse?: string
}

export interface ComplaintFilters {
  category?: string
  priority?: string
  status?: string
  search?: string
  page?: number
  pageSize?: number
}

interface ComplaintApiPayload {
  id: string
  customer_name?: string
  customer_email?: string
  customer_phone?: string
  subject?: string
  complaint_text?: string
  category?: string
  priority?: string
  sentiment?: string
  status?: string
  created_at?: string
  updated_at?: string
  ai_confidence?: number
  ai_reply?: string
}

function normalizeComplaint(complaint: ComplaintApiPayload): Complaint {
  return {
    id: complaint.id,
    customerName: complaint.customer_name ?? 'Customer',
    customerEmail: complaint.customer_email ?? '',
    customerPhone: complaint.customer_phone ?? '',
    subject: complaint.subject ?? 'Complaint',
    message: complaint.complaint_text ?? complaint.subject ?? '',
    category: complaint.category ?? 'general',
    priority: (complaint.priority ?? 'medium') as Complaint['priority'],
    sentiment: (complaint.sentiment ?? 'neutral') as Complaint['sentiment'],
    aiConfidence: Math.round(complaint.ai_confidence ?? 0),
    status: (complaint.status ?? 'new') as Complaint['status'],
    createdAt: complaint.created_at ?? new Date().toISOString(),
    updatedAt: complaint.updated_at ?? complaint.created_at ?? new Date().toISOString(),
    suggestedResponse: complaint.ai_reply,
  }
}

export const complaintsAPI = {
  getAll: async (filters?: ComplaintFilters): Promise<Complaint[]> => {
    const params = new URLSearchParams()
    if (filters?.category) params.append('category', filters.category)
    if (filters?.priority) params.append('priority', filters.priority)
    if (filters?.status) params.append('status', filters.status)
    if (filters?.search) params.append('search', filters.search)
    if (filters?.page) params.append('page', String(filters.page))
    if (filters?.pageSize) params.append('page_size', String(filters.pageSize))

    const response = await api.get(`/api/v1/complaints${params.toString() ? `?${params.toString()}` : ''}`)
    const items = Array.isArray(response.data) ? response.data : response.data.items ?? []
    return items.map(normalizeComplaint)
  },

  getById: async (id: string): Promise<Complaint> => {
    const response = await api.get(`/api/v1/complaints/${id}`)
    return normalizeComplaint(response.data)
  },

  reply: async (id: string, replyText: string) => {
    const response = await api.post(`/api/v1/complaints/${id}/reply`, {
      reply_text: replyText,
    })
    return response.data
  },

  markResolved: async (id: string) => {
    const response = await api.patch(`/api/v1/complaints/${id}`, {
      status: 'resolved',
    })
    return response.data
  },
}

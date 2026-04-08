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
  ticketId?: string
  resolutionStatus?: string
  firstResponseAt?: string | null
  resolvedAt?: string | null
  sentimentScore?: number | null
  sentimentLabel?: string | null
  sentimentIndicators: string[]
  assignedTo?: string | null
  satisfactionScore?: number | null
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
  ticket_id?: string
  resolution_status?: string
  first_response_at?: string | null
  resolved_at?: string | null
  sentiment_score?: number | null
  sentiment_label?: string | null
  sentiment_indicators?: string[]
  assigned_to?: string | null
  satisfaction_score?: number | null
}

interface ComplaintReplyApiResponse extends ComplaintApiPayload {
  complaint?: ComplaintApiPayload
  sent?: boolean
}

export interface SuggestedResponseResult {
  suggestedResponse: string
  confidence: number
  basedOnSimilarCases: number
}

export interface ComplaintListResponse {
  items: Complaint[]
  total: number
  page: number
  pageSize: number
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
    ticketId: complaint.ticket_id,
    resolutionStatus: complaint.resolution_status,
    firstResponseAt: complaint.first_response_at ?? null,
    resolvedAt: complaint.resolved_at ?? null,
    sentimentScore: complaint.sentiment_score ?? null,
    sentimentLabel: complaint.sentiment_label ?? null,
    sentimentIndicators: complaint.sentiment_indicators ?? [],
    assignedTo: complaint.assigned_to ?? null,
    satisfactionScore: complaint.satisfaction_score ?? null,
  }
}

export const complaintsAPI = {
  list: async (filters?: ComplaintFilters): Promise<ComplaintListResponse> => {
    const params = new URLSearchParams()
    if (filters?.category) params.append('category', filters.category)
    if (filters?.priority) params.append('priority', filters.priority)
    if (filters?.status) params.append('status', filters.status)
    if (filters?.search) params.append('search', filters.search)
    if (filters?.page) params.append('page', String(filters.page))
    if (filters?.pageSize) params.append('page_size', String(filters.pageSize))

    const response = await api.get(`/api/v1/complaints${params.toString() ? `?${params.toString()}` : ''}`)
    const items = Array.isArray(response.data) ? response.data : response.data.items ?? []
    return {
      items: items.map(normalizeComplaint),
      total: Number(response.data?.total ?? items.length),
      page: Number(response.data?.page ?? filters?.page ?? 1),
      pageSize: Number(response.data?.page_size ?? filters?.pageSize ?? items.length),
    }
  },

  getAll: async (filters?: ComplaintFilters): Promise<Complaint[]> => {
    const response = await complaintsAPI.list({
      ...filters,
      page: 1,
      pageSize: filters?.pageSize ?? 500,
    })
    return response.items
  },

  getById: async (id: string): Promise<Complaint> => {
    const response = await api.get(`/api/v1/complaints/${id}`)
    return normalizeComplaint(response.data)
  },

  reply: async (id: string, replyText: string) => {
    const response = await api.post(`/api/v1/complaints/${id}/reply`, {
      reply_text: replyText,
    })
    const data = response.data as ComplaintReplyApiResponse
    if (data.sent === false) {
      throw new Error('Reply could not be delivered')
    }
    return normalizeComplaint(data.complaint ?? data)
  },

  markResolved: async (id: string) => {
    const response = await api.patch(`/api/v1/complaints/${id}`, {
      status: 'resolved',
    })
    return normalizeComplaint(response.data)
  },

  suggestReply: async (id: string): Promise<SuggestedResponseResult> => {
    const response = await api.get(`/api/v1/complaints/${id}/suggest-response`)
    return {
      suggestedResponse: String(response.data?.suggested_response ?? ''),
      confidence: Number(response.data?.confidence ?? 0),
      basedOnSimilarCases: Number(response.data?.based_on_similar_cases ?? 0),
    }
  },

  escalate: async (id: string) => {
    const response = await api.post(`/api/v1/complaints/${id}/escalate`)
    return normalizeComplaint(response.data)
  },

  delete: async (id: string) => {
    const response = await api.delete(`/api/v1/complaints/${id}`)
    return response.data as { ok: boolean; id: string }
  },
}

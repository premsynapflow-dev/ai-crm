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
  threadId?: string
  conversationId?: string | null
}

export interface ComplaintThreadAttachment {
  filename?: string
  content_type?: string
  size?: number
}

export interface ComplaintThreadMessage {
  id: string
  direction: 'inbound' | 'outbound' | string
  channel: string
  senderName: string
  senderId?: string | null
  messageText: string
  timestamp?: string | null
  status?: string
  attachments: ComplaintThreadAttachment[]
}

export interface ComplaintConversationSummary {
  headline: string
  waitingOn: 'support' | 'customer' | string
  messageCount: number
  customerMessageCount: number
  supportMessageCount: number
  lastUpdatedAt?: string | null
  attachments: string[]
  keyPoints: string[]
}

export interface ComplaintDetail extends Complaint {
  threadMessages: ComplaintThreadMessage[]
  conversationSummary?: ComplaintConversationSummary
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
  ticket_number?: string
  resolution_status?: string
  first_response_at?: string | null
  resolved_at?: string | null
  sentiment_score?: number | null
  sentiment_label?: string | null
  sentiment_indicators?: string[]
  assigned_to?: string | null
  satisfaction_score?: number | null
  thread_id?: string
  conversation_id?: string | null
  thread_messages?: Array<{
    id: string
    direction?: string
    channel?: string
    sender_name?: string
    sender_id?: string | null
    message_text?: string
    timestamp?: string | null
    status?: string
    attachments?: ComplaintThreadAttachment[]
  }>
  conversation_summary?: {
    headline?: string
    waiting_on?: string
    message_count?: number
    customer_message_count?: number
    support_message_count?: number
    last_updated_at?: string | null
    attachments?: string[]
    key_points?: string[]
  }
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

function normalizeComplaint(complaint: ComplaintApiPayload): ComplaintDetail {
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
    ticketId: complaint.ticket_id ?? complaint.ticket_number,
    resolutionStatus: complaint.resolution_status,
    firstResponseAt: complaint.first_response_at ?? null,
    resolvedAt: complaint.resolved_at ?? null,
    sentimentScore: complaint.sentiment_score ?? null,
    sentimentLabel: complaint.sentiment_label ?? null,
    sentimentIndicators: complaint.sentiment_indicators ?? [],
    assignedTo: complaint.assigned_to ?? null,
    satisfactionScore: complaint.satisfaction_score ?? null,
    threadId: complaint.thread_id,
    conversationId: complaint.conversation_id ?? null,
    threadMessages: (complaint.thread_messages ?? []).map((message) => ({
      id: message.id,
      direction: message.direction ?? 'inbound',
      channel: message.channel ?? 'email',
      senderName: message.sender_name ?? 'Customer',
      senderId: message.sender_id ?? null,
      messageText: message.message_text ?? '',
      timestamp: message.timestamp ?? null,
      status: message.status ?? 'received',
      attachments: message.attachments ?? [],
    })),
    conversationSummary: complaint.conversation_summary ? {
      headline: complaint.conversation_summary.headline ?? complaint.subject ?? 'Conversation summary',
      waitingOn: complaint.conversation_summary.waiting_on ?? 'support',
      messageCount: Number(complaint.conversation_summary.message_count ?? 0),
      customerMessageCount: Number(complaint.conversation_summary.customer_message_count ?? 0),
      supportMessageCount: Number(complaint.conversation_summary.support_message_count ?? 0),
      lastUpdatedAt: complaint.conversation_summary.last_updated_at ?? null,
      attachments: complaint.conversation_summary.attachments ?? [],
      keyPoints: complaint.conversation_summary.key_points ?? [],
    } : undefined,
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

  getById: async (id: string): Promise<ComplaintDetail> => {
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

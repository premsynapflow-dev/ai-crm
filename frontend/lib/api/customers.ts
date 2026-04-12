import api from '../api'

export interface CustomerSummary {
  id: string
  client_id: string
  name: string | null
  primary_email: string | null
  primary_phone: string | null
  full_name: string | null
  company_name: string | null
  merged_emails?: string[]
  notes?: string | null
  total_messages?: number
  total_tickets: number
  open_tickets?: number
  total_interactions: number
  last_contacted_at?: string | null
  avg_response_time?: number | null
  sentiment_score?: number | null
  sentiment_label?: string | null
  churn_risk?: string
  avg_satisfaction_score: number | null
  churn_risk_score: number
  last_interaction_at: string | null
  created_at: string | null
}

export interface CustomerTicket {
  id: string
  ticket_id: string
  ticket_number: string
  summary: string
  source: string
  category: string
  priority: number | null
  state: string
  sla_status: string
  resolution_status: string
  assigned_to: string | null
  created_at: string | null
  resolved_at: string | null
}

export interface CustomerInteraction {
  id: string
  interaction_type: string
  interaction_channel: string | null
  summary: string | null
  sentiment_score: number | null
  duration_seconds: number | null
  metadata: Record<string, unknown>
  created_at: string | null
}

export interface CustomerMessage {
  id: string
  customer_id: string | null
  channel: string
  direction: string
  status: string
  sender_id: string | null
  sender_name: string | null
  message_text: string | null
  complaint_id: string | null
  timestamp: string | null
  created_at: string | null
}

export interface CustomerNote {
  id: string
  customer_id: string
  author_email: string
  note_type: string
  content: string
  pinned: boolean
  created_at: string | null
  updated_at: string | null
}

export interface CustomerRelationship {
  id: string
  client_id: string
  parent_customer_id: string
  child_customer_id: string
  relationship_type: string
  role_title: string | null
  is_primary_contact: boolean
  created_at: string | null
}

export interface CustomerDuplicateCandidate {
  customer: CustomerSummary
  confidence_score: number
}

export interface CustomerDetailResponse {
  profile: CustomerSummary
  recent_tickets: CustomerTicket[]
  recent_messages: CustomerMessage[]
  active_tickets: CustomerTicket[]
  interaction_timeline: CustomerInteraction[]
  timeline: CustomerTimelineItem[]
  notes: CustomerNote[]
  relationships: CustomerRelationship[]
  satisfaction_trend: Array<{ week: string; avg_score: number | null }>
  churn_indicators: Record<string, unknown>
  sentiment?: {
    score: number | null
    label: string
    sample_size: number
  }
  insights?: string[]
  stats: {
    total_messages?: number
    total_tickets: number
    open_tickets?: number
    total_interactions: number
    last_contacted_at?: string | null
    avg_response_time?: number | null
    avg_satisfaction: number | null
    churn_risk: number
    lifetime_value: number
  }
}

export interface CustomerTimelineItem {
  id: string
  type: 'message' | 'ticket' | 'action'
  title: string
  body: string
  channel?: string
  direction?: string
  status?: string
  timestamp: string | null
  sort_at?: string | null
  data: Record<string, unknown>
}

export interface Customer360Response {
  identity: {
    id: string
    client_id: string
    name: string | null
    primary_email: string | null
    merged_emails: string[]
    tags: string[]
    notes: string | null
    created_at: string | null
    updated_at: string | null
  }
  metrics: {
    total_messages: number
    total_tickets: number
    open_tickets: number
    last_contacted_at: string | null
    avg_response_time: number | null
  }
  sentiment: {
    score: number | null
    label: string
    sample_size: number
  }
  churn_risk: 'low' | 'medium' | 'high'
  recent_messages: CustomerMessage[]
  recent_tickets: CustomerTicket[]
  active_tickets: CustomerTicket[]
  timeline: CustomerTimelineItem[]
  insights: string[]
}

export const customersAPI = {
  list: async (params?: { search?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/api/v1/customers', { params })
    return response.data as { total: number; items: CustomerSummary[] }
  },

  getById: async (customerId: string) => {
    const response = await api.get(`/api/v1/customers/${customerId}`)
    return response.data as CustomerDetailResponse
  },

  get360: async (customerId: string) => {
    const response = await api.get(`/api/v1/customers/${customerId}/360`)
    return response.data as Customer360Response
  },

  getDuplicates: async (customerId: string) => {
    const response = await api.get(`/api/v1/customers/${customerId}/duplicates`)
    return response.data as { customer_id: string; potential_duplicates: CustomerDuplicateCandidate[] }
  },

  addNote: async (customerId: string, payload: { content: string; note_type?: string; pinned?: boolean }) => {
    const response = await api.post(`/api/v1/customers/${customerId}/notes`, payload)
    return response.data as { success: boolean; note: CustomerNote }
  },

  update: async (customerId: string, payload: { name?: string; notes?: string; tags?: string[] }) => {
    const response = await api.patch(`/api/v1/customers/${customerId}`, payload)
    return response.data as { success: boolean; customer: CustomerSummary }
  },
}

import api from '../api'

export interface CustomerSummary {
  id: string
  client_id: string
  primary_email: string | null
  primary_phone: string | null
  full_name: string | null
  company_name: string | null
  total_tickets: number
  total_interactions: number
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
  interaction_timeline: CustomerInteraction[]
  notes: CustomerNote[]
  relationships: CustomerRelationship[]
  satisfaction_trend: Array<{ period: string; score: number | null; tickets: number }>
  churn_indicators: Record<string, unknown>
  stats: {
    total_tickets: number
    total_interactions: number
    avg_satisfaction: number | null
    churn_risk: number
    lifetime_value: number
  }
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

  getDuplicates: async (customerId: string) => {
    const response = await api.get(`/api/v1/customers/${customerId}/duplicates`)
    return response.data as { customer_id: string; potential_duplicates: CustomerDuplicateCandidate[] }
  },

  addNote: async (customerId: string, payload: { content: string; note_type?: string; pinned?: boolean }) => {
    const response = await api.post(`/api/v1/customers/${customerId}/notes`, payload)
    return response.data as { success: boolean; note: CustomerNote }
  },
}

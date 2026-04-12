import api from '../api'

export interface RBIComplaintCategory {
  id: string
  category_code: string
  category_name: string
  subcategory_code: string
  subcategory_name: string
  tat_days: number
}

export interface RBIComplaintDetail {
  complaint_id: string
  ticket_id?: string
  rbi_reference_number: string
  category_code: string
  category_name?: string
  subcategory_code: string
  subcategory_name?: string
  tat_due_date: string | null
  tat_due_at?: string | null
  tat_status: string
  tat_breached_at?: string | null
  breached?: boolean
  classifier_confidence?: number
  escalation_level?: number
  escalated_to_rbi?: boolean
  escalation_status?: string
  escalation_history: Array<{
    id: string
    level: number
    escalated_to: string
    reason: string | null
    created_at: string | null
  }>
  resolution_date?: string | null
  audit_log: Array<{
    id: string | null
    entity_type: string
    entity_id: string
    action: string
    performed_by: string | null
    old_value: Record<string, unknown>
    new_value: Record<string, unknown>
    timestamp: string | null
  }>
}

export interface RBIMisReport {
  total_complaints: number
  resolved_within_tat: number
  tat_breach_count: number
  breached_complaints?: number
  pending_complaints: number
  complaints_by_category: Record<string, number>
  category_distribution?: Record<string, number>
  escalations_count?: number
  escalated_to_regional: number
  escalated_to_nodal: number
  escalated_to_ombudsman: number
  avg_resolution_days: number | null
  satisfaction_rate: number | null
}

export const complianceAPI = {
  getCategories: async () => {
    const response = await api.get('/api/v1/rbi-compliance/categories')
    return response.data as { items: RBIComplaintCategory[] }
  },

  getComplaint: async (complaintId: string) => {
    const response = await api.get(`/api/v1/rbi-compliance/complaints/${complaintId}`)
    return response.data as RBIComplaintDetail
  },

  getMisReport: async (year: number, month: number) => {
    const response = await api.get(`/api/v1/rbi-compliance/mis-report/${year}/${month}`)
    return response.data as RBIMisReport
  },

  escalateToRBI: async (complaintId: string) => {
    const response = await api.post(`/api/v1/rbi-compliance/complaints/${complaintId}/escalate-rbi`)
    return response.data as { success: boolean; rbi_reference?: string; escalated_to?: string }
  },

  escalateInternally: async (complaintId: string) => {
    const response = await api.post(`/api/v1/rbi-compliance/complaints/${complaintId}/escalate-internal`)
    return response.data as { success: boolean; escalated_to: string }
  },
}

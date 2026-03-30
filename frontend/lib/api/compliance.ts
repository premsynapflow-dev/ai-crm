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
  rbi_reference_number: string
  category_code: string
  subcategory_code: string
  tat_due_date: string | null
  tat_status: string
  classifier_confidence?: number
  escalation_level?: number
  escalated_to_rbi?: boolean
  resolution_date?: string | null
  audit_log: Array<Record<string, unknown>>
}

export interface RBIMisReport {
  total_complaints: number
  resolved_within_tat: number
  tat_breach_count: number
  pending_complaints: number
  complaints_by_category: Record<string, number>
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
    return response.data as { success: boolean; rbi_reference: string }
  },
}

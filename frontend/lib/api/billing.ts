import api from '../api'

export interface Plan {
  id: string
  name: string
  price: number
  monthly_tickets: number
  overage_rate?: number
  features: string[]
}

export interface Invoice {
  id: string
  invoice_number: string
  status: string
  total: number
  paid_at: string | null
}

export interface Usage {
  client_id: string
  plan_id: string
  monthly_limit: number
  tickets_processed: number
  overage: number
  overage_cost: number
  trial_ends_at: string | null
  trial_active: boolean
  period_start: string
  period_end: string
}

export const billingAPI = {
  getPlans: async (): Promise<Record<string, Plan>> => {
    const response = await api.get('/api/plans')
    return response.data
  },

  getCurrentPlan: async () => {
    const response = await api.get('/api/v1/me')
    return response.data
  },

  upgradePlan: async (planId: string) => {
    const response = await api.post('/api/upgrade', {
      plan_id: planId,
    })
    return response.data
  },

  getInvoices: async (): Promise<Invoice[]> => {
    const response = await api.get('/api/invoices')
    return response.data
  },

  getUsage: async (): Promise<Usage> => {
    const response = await api.get('/api/usage')
    return response.data
  },
}

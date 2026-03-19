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
  subtotal: number
  tax: number
  invoice_date: string | null
  paid_at: string | null
  payment_method: string | null
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
  current_usage: number
  remaining_tickets: number
  usage_percentage: number
  projected_usage: number
  days_remaining: number
  days_total: number
  elapsed_days: number
  daily_average: number
  peak_day: string | null
  peak_day_count: number
  history: Array<{ date: string; tickets: number }>
  category_breakdown: Array<{ category: string; tickets: number }>
  overage_rate: number
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

import api from '../api'
import type { PlanId } from '../plan-features'

export interface PlanFeatureFlags {
  ai_classification: boolean
  ai_auto_reply: boolean
  sentiment_analysis: boolean
  pattern_detection: boolean
  churn_risk_scoring: boolean
  analytics_level: string
  sla_tracking: boolean
  api_access: boolean
  custom_branding: boolean
  root_cause_analysis: boolean
  team_performance: boolean
  audit_log: boolean
  ai_suggested_responses: boolean
  multi_channel: string[]
  integrations_count: number
  webhooks: boolean
}

export interface Plan {
  id: PlanId | string
  name: string
  monthly_price: number | null
  annual_price: number | null
  annual_savings: number | null
  price: number
  tickets_per_month: number
  monthly_tickets: number
  team_seats: number
  overage_rate: number
  trial_days: number | null
  trial_requires_card: boolean
  features: string[]
  feature_flags: PlanFeatureFlags
  razorpay_plan_ids?: Partial<Record<'monthly' | 'annual', string>>
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

  upgradePlan: async (planId: string, billingCycle: 'monthly' | 'annual' = 'monthly') => {
    const response = await api.post('/api/upgrade', {
      plan_id: planId,
      billing_cycle: billingCycle,
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

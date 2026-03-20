import api from '../api'

export interface TrendSummary {
  window_days: number
  current: number
  previous: number
  direction: 'up' | 'down' | 'flat'
}

export interface AnalyticsOverview {
  days: number
  total_complaints: number
  resolved_today: number
  avg_response_time: number
  customer_satisfaction: number
  resolution_rate: number
  average_ai_confidence: number
  trend: TrendSummary
  sentiment_distribution: Array<{ sentiment: string; count: number }>
  category_breakdown: Array<{ category: string; count: number }>
  priority_breakdown: Array<{ priority: string; count: number }>
  status_distribution: Array<{ status: string; count: number }>
  volume_trend: Array<{ date: string; count: number }>
  response_time_trend: Array<{ date: string; average_seconds: number; average_minutes: number }>
  complaints_by_hour: Array<{ hour: string; count: number }>
  sources: Array<{ source: string; count: number }>
  ai_resolution: { ai_resolution_rate: number }
  escalation: { escalation_rate: number }
}

export interface AnalyticsCategoryBreakdownItem {
  category: string
  count: number
}

export interface AnalyticsSentimentDistributionItem {
  sentiment: string
  count: number
}

export const analyticsAPI = {
  getOverview: async (days = 30): Promise<AnalyticsOverview> => {
    const response = await api.get('/api/analytics/overview', { params: { days } })
    return response.data
  },

  getCategoryBreakdown: async (): Promise<AnalyticsCategoryBreakdownItem[]> => {
    const response = await api.get('/api/analytics/category-breakdown')
    return response.data
  },

  getSentimentDistribution: async (): Promise<AnalyticsSentimentDistributionItem[]> => {
    const response = await api.get('/api/analytics/sentiment-distribution')
    return response.data
  },
}

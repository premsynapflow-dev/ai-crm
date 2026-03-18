import api from '../api'

export interface TrendSummary {
  window_days: number
  current: number
  previous: number
  direction: 'up' | 'down' | 'flat'
}

export interface AnalyticsOverview {
  total_complaints: number
  resolved_today: number
  avg_response_time: number
  customer_satisfaction: number
  trend: TrendSummary
  sentiment_distribution: Array<{ sentiment: string; count: number }>
  category_breakdown: Array<{ category: string; count: number }>
}

export const analyticsAPI = {
  getOverview: async (): Promise<AnalyticsOverview> => {
    const response = await api.get('/api/analytics/overview')
    return response.data
  },

  getCategoryBreakdown: async () => {
    const response = await api.get('/api/analytics/category-breakdown')
    return response.data
  },

  getSentimentDistribution: async () => {
    const response = await api.get('/api/analytics/sentiment-distribution')
    return response.data
  },
}

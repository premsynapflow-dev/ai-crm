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
  total_leads: number
  open_tickets: number
  resolved_tickets: number
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

export interface SentimentDistributionResponse {
  distribution: Record<string, number>
  labels: Record<string, string>
}

export interface ChurnRiskCustomer {
  customer_email: string
  risk_score: number
  risk_level: 'low' | 'medium' | 'high' | 'critical' | 'none'
  complaint_count: number
  unresolved_count: number
  avg_sentiment: number
  recommendation: string
}

export interface RootCauseIssue {
  category: string
  current_count: number
  previous_count: number
  change_percentage: number
  percentage_of_total: number
}

export interface RootCauseAnalysisResponse {
  period: string
  start_date: string
  end_date: string
  total_complaints: number
  previous_period_total: number
  overall_change_percentage: number
  top_issues: RootCauseIssue[]
  trending_up: RootCauseIssue[]
  resolution_rates: Record<string, number>
  insights: string[]
  generated_at: string
}

export interface TeamPerformanceMember {
  agent_name: string
  total_tickets: number
  resolved_tickets: number
  resolution_rate: number
  avg_response_time_hours: number
  avg_handle_time_hours: number
  avg_satisfaction: number
}

export interface TeamPerformanceResponse {
  period_days: number
  team_performance: TeamPerformanceMember[]
  team_totals: {
    total_tickets: number
    total_resolved: number
    avg_team_resolution_rate: number
  }
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

  getSentimentDistribution: async (): Promise<SentimentDistributionResponse> => {
    const response = await api.get('/api/analytics/sentiment-distribution')
    return response.data
  },

  getChurnRisk: async (): Promise<ChurnRiskCustomer[]> => {
    const response = await api.get('/api/analytics/churn-risk')
    return response.data
  },

  getRootCauseAnalysis: async (periodDays = 30): Promise<RootCauseAnalysisResponse> => {
    const response = await api.get('/api/analytics/root-cause-analysis', { params: { period_days: periodDays } })
    return response.data
  },

  getTeamPerformance: async (periodDays = 30): Promise<TeamPerformanceResponse> => {
    const response = await api.get('/api/analytics/team-performance', { params: { period_days: periodDays } })
    return response.data
  },
}

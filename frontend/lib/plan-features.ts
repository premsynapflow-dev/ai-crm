export const PLAN_ORDER = ['free', 'starter', 'pro', 'max', 'scale', 'enterprise'] as const

export type PlanId = (typeof PLAN_ORDER)[number]

export type FeatureKey =
  | 'sentiment_analysis'
  | 'ai_suggested_responses'
  | 'churn_risk_scoring'
  | 'root_cause_analysis'
  | 'team_performance'
  | 'api_access'
  | 'custom_branding'
  | 'webhooks'

const FEATURE_MINIMUM_PLAN: Record<FeatureKey, PlanId> = {
  sentiment_analysis: 'pro',
  ai_suggested_responses: 'pro',
  churn_risk_scoring: 'max',
  root_cause_analysis: 'max',
  team_performance: 'max',
  api_access: 'max',
  custom_branding: 'scale',
  webhooks: 'scale',
}

export function isPlanId(value: string | undefined | null): value is PlanId {
  return PLAN_ORDER.includes((value ?? '') as PlanId)
}

export function getPlanRank(planId: string | undefined | null): number {
  const normalized = isPlanId(planId) ? planId : 'free'
  return PLAN_ORDER.indexOf(normalized)
}

export function minimumPlanForFeature(feature: FeatureKey): PlanId {
  return FEATURE_MINIMUM_PLAN[feature]
}

export function planIncludesFeature(planId: string | undefined | null, feature: FeatureKey): boolean {
  return getPlanRank(planId) >= getPlanRank(minimumPlanForFeature(feature))
}

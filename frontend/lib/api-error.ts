export interface FeatureGateErrorDetail {
  message: string
  required_plan?: string
  feature_flag?: string
  current_plan?: string
}

export function getFeatureGateDetail(error: unknown): FeatureGateErrorDetail | null {
  const detail = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response?.data?.detail
  const status = (error as { response?: { status?: number } })?.response?.status

  if (status !== 403) {
    return null
  }

  if (typeof detail === 'string') {
    return { message: detail }
  }

  if (detail && typeof detail === 'object') {
    const data = detail as Record<string, unknown>
    return {
      message: String(data.message ?? 'This feature is not available on your current plan'),
      required_plan: data.required_plan ? String(data.required_plan) : undefined,
      feature_flag: data.feature_flag ? String(data.feature_flag) : undefined,
      current_plan: data.current_plan ? String(data.current_plan) : undefined,
    }
  }

  return { message: 'This feature is not available on your current plan' }
}

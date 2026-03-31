import Cookies from 'js-cookie'

import api from '../api'
import type { PlanId } from '../plan-features'

export type { PlanId } from '../plan-features'

export interface LoginCredentials {
  email: string
  password: string
}

export interface User {
  id: string
  email: string
  name: string
  plan_id: PlanId
  plan: PlanId
  company: string
  company_phone?: string | null
  business_sector?: string | null
  is_rbi_regulated?: boolean
  created_at?: string | null
}

function normalizeUser(payload: unknown): User {
  const raw = (payload ?? {}) as Record<string, unknown>
  const plan = String(raw.plan_id ?? raw.plan ?? 'starter') as PlanId

  return {
    id: String(raw.id ?? ''),
    email: String(raw.email ?? ''),
    name: String(raw.name ?? 'SynapFlow User'),
    plan_id: plan,
    plan: plan,
    company: String(raw.company ?? raw.client_name ?? 'SynapFlow'),
    company_phone: raw.company_phone ? String(raw.company_phone) : null,
    business_sector: raw.business_sector ? String(raw.business_sector) : null,
    is_rbi_regulated: Boolean(raw.is_rbi_regulated),
    created_at: raw.created_at ? String(raw.created_at) : null,
  }
}

export const authAPI = {
  login: async (credentials: LoginCredentials): Promise<User> => {
    const formData = new FormData()
    formData.append('username', credentials.email)
    formData.append('password', credentials.password)

    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    return normalizeUser(response.data.user ?? response.data)
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      Cookies.remove('session_token')
      Cookies.remove('portal_session')
    }
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/api/v1/me')
    return normalizeUser(response.data)
  },
}

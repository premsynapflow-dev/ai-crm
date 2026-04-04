import Cookies from 'js-cookie'

import api, { ACCESS_TOKEN_STORAGE_KEY } from '../api'
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

interface LoginResponse {
  access_token?: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
}

function normalizeUser(payload: unknown): User {
  const raw = (payload ?? {}) as Record<string, unknown>
  const plan = String(raw.plan_id ?? raw.plan ?? 'free') as PlanId

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
    const response = await api.post<LoginResponse>('/api/v1/auth/login', {
      email: credentials.email,
      password: credentials.password,
    })

    console.log('[auth] Login response:', response.data)

    const accessToken = response.data?.access_token
    if (!accessToken) {
      throw new Error('Login response did not include an access token')
    }

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)
      console.log('[auth] Token after storing:', window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY))
    }

    return authAPI.getCurrentUser()
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
      }
      Cookies.remove('session_token')
      Cookies.remove('portal_session')
    }
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/api/v1/me')
    return normalizeUser(response.data)
  },
}

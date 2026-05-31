import Cookies from 'js-cookie'

import api from '../api'
import { setToken, clearToken } from '../auth'
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

interface SessionLoginResponse {
  access_token?: string
  user?: unknown & { access_token?: string }
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
    const payload = new URLSearchParams({
      username: credentials.email,
      password: credentials.password,
    })

    try {
      const response = await api.post<SessionLoginResponse>('/api/v1/auth/login', payload, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })

      console.log('[auth] Login response:', {
        hasAccessToken: !!response.data?.access_token,
        accessTokenLength: response.data?.access_token?.length || 0,
        fullResponse: JSON.stringify(response.data).substring(0, 200),
      })

      // Store token immediately
      if (response.data?.access_token) {
        setToken(response.data.access_token)
        console.log('[auth] Token stored in localStorage')
        const storedToken = localStorage.getItem('access_token')
        console.log('[auth] Verification - token in localStorage:', !!storedToken, 'length:', storedToken?.length)
      } else if (response.data?.user?.access_token) {
        setToken(response.data.user.access_token)
        console.log('[auth] Token stored in localStorage (nested)')
      } else {
        console.warn('[auth] No access_token in response:', JSON.stringify(response.data).substring(0, 200))
      }

      // Fetch current user with the new token
      try {
        const userResponse = await api.get<User>('/api/v1/me')
        console.log('[auth] Got user data after login:', userResponse.data)
        return normalizeUser(userResponse.data)
      } catch (userError) {
        console.warn('[auth] Failed to fetch user after login, using response data:', userError instanceof Error ? userError.message : String(userError))
        return normalizeUser(response.data?.user || response.data)
      }
    } catch (error) {
      console.error('[auth] Login failed:', error instanceof Error ? error.message : String(error))
      throw error
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      clearToken()
      Cookies.remove('session_token')
      Cookies.remove('portal_session')
    }
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/api/v1/me')
    return normalizeUser(response.data)
  },
}

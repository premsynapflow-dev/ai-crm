"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'

import { ACCESS_TOKEN_STORAGE_KEY } from '@/lib/api'
import { authAPI, type PlanId, type User } from '@/lib/api/auth'
import { billingAPI } from '@/lib/api/billing'

interface AuthUser extends User {
  avatar?: string
}

interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  updatePlan: (plan: PlanId) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    let active = true

    const loadCurrentUser = async () => {
      const accessToken = typeof window === 'undefined'
        ? null
        : window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)

      if (!accessToken) {
        if (active) {
          setUser(null)
          setIsLoading(false)
        }
        return
      }

      try {
        const currentUser = await authAPI.getCurrentUser()
        if (active) {
          setUser(currentUser)
        }
      } catch (error) {
        if (active) {
          setUser(null)
        }
        console.error('Failed to fetch user', error)
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadCurrentUser()

    return () => {
      active = false
    }
  }, [])

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const loggedInUser = await authAPI.login({ email, password })
      setUser(loggedInUser)
      return true
    } catch {
      setUser(null)
      return false
    }
  }

  const logout = () => {
    setUser(null)
    void authAPI.logout()
    router.push('/login')
  }

  const updatePlan = async (plan: PlanId) => {
    const previousUser = user
    if (!previousUser) {
      return
    }

    setUser({ ...previousUser, plan, plan_id: plan })
    try {
      await billingAPI.upgradePlan(plan)
    } catch {
      setUser(previousUser)
      throw new Error('Failed to update plan')
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        updatePlan,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

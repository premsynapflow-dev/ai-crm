"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'

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
  refreshUser: () => Promise<AuthUser | null>
  updatePlan: (plan: PlanId) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  const refreshUser = async (): Promise<AuthUser | null> => {
    try {
      const currentUser = await authAPI.getCurrentUser()
      setUser(currentUser)
      return currentUser
    } catch {
      setUser(null)
      return null
    }
  }

  useEffect(() => {
    let active = true

    const loadCurrentUser = async () => {
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
        const currentPath = typeof window !== 'undefined' ? window.location.pathname.replace(/\/$/, '') : ''
        if (currentPath && currentPath !== '/login' && currentPath !== '') {
          // Let components handle their own unauthorized states (e.g. rendering LoginForm)
          // instead of forcing a full page reload here.
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

    try {
      const result = await billingAPI.upgradePlan(plan)
      if (result.plan_applied) {
        await refreshUser()
        return
      }
      setUser(previousUser)
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
        refreshUser,
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

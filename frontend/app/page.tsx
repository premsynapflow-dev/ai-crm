"use client"

import { useAuth, AuthProvider } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { DashboardContent } from '@/components/dashboard-content'

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <DashboardContent />
    </DashboardLayout>
  )
}

export default function Home() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

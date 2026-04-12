"use client"

import { useAuth, AuthProvider } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { SettingsContent } from '@/components/settings-content'

function SettingsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <SettingsContent />
    </DashboardLayout>
  )
}

export default function SettingsPage() {
  return (
    <AuthProvider>
      <SettingsPageContent />
    </AuthProvider>
  )
}

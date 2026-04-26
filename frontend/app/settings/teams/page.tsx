"use client"

import { useAuth } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { TeamsSettingsContent } from '@/components/teams-settings-content'

function TeamsSettingsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <TeamsSettingsContent />
    </DashboardLayout>
  )
}

export default function TeamsSettingsPage() {
  return (
    <>
      <TeamsSettingsPageContent />
    </>
  )
}

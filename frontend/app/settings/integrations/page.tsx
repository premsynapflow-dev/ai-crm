"use client"

import { useAuth } from '@/lib/auth-context'
import { DashboardLayout } from '@/components/dashboard-layout'
import { IntegrationsSettingsContent } from '@/components/integrations-settings-content'
import { LoginForm } from '@/components/login-form'

function IntegrationsSettingsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <IntegrationsSettingsContent />
    </DashboardLayout>
  )
}

export default function IntegrationsSettingsPage() {
  return (
    <>
      <IntegrationsSettingsPageContent />
    </>
  )
}

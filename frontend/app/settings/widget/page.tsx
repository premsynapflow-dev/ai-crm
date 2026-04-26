"use client"

import { useAuth } from '@/lib/auth-context'
import { DashboardLayout } from '@/components/dashboard-layout'
import { WidgetSettingsContent } from '@/components/widget-settings-content'
import { LoginForm } from '@/components/login-form'

function WidgetSettingsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <WidgetSettingsContent />
    </DashboardLayout>
  )
}

export default function WidgetSettingsPage() {
  return (
    <>
      <WidgetSettingsPageContent />
    </>
  )
}

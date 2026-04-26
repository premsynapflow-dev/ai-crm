"use client"

import { useAuth } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { AnalyticsContent } from '@/components/analytics-content'

function AnalyticsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <AnalyticsContent />
    </DashboardLayout>
  )
}

export default function AnalyticsPage() {
  return (
    <>
      <AnalyticsPageContent />
    </>
  )
}

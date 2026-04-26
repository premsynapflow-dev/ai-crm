"use client"

import { useAuth } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { UsageContent } from '@/components/usage-content'

function UsagePageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <UsageContent />
    </DashboardLayout>
  )
}

export default function UsagePage() {
  return (
    <>
      <UsagePageContent />
    </>
  )
}

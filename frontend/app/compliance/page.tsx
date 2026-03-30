"use client"

import { AuthProvider, useAuth } from '@/lib/auth-context'
import { ComplianceContent } from '@/components/compliance-content'
import { DashboardLayout } from '@/components/dashboard-layout'
import { LoginForm } from '@/components/login-form'

function CompliancePageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <ComplianceContent />
    </DashboardLayout>
  )
}

export default function CompliancePage() {
  return (
    <AuthProvider>
      <CompliancePageContent />
    </AuthProvider>
  )
}

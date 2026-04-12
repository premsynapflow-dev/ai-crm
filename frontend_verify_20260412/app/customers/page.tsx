"use client"

import { AuthProvider, useAuth } from '@/lib/auth-context'
import { CustomersContent } from '@/components/customers-content'
import { DashboardLayout } from '@/components/dashboard-layout'
import { LoginForm } from '@/components/login-form'

function CustomersPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <CustomersContent />
    </DashboardLayout>
  )
}

export default function CustomersPage() {
  return (
    <AuthProvider>
      <CustomersPageContent />
    </AuthProvider>
  )
}

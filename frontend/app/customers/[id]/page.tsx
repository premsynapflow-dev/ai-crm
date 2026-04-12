"use client"

import { Customer360Page } from '@/components/customer-360-page'
import { DashboardLayout } from '@/components/dashboard-layout'
import { LoginForm } from '@/components/login-form'
import { AuthProvider, useAuth } from '@/lib/auth-context'

function Customer360PageContent({ customerId }: { customerId: string }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <Customer360Page customerId={customerId} />
    </DashboardLayout>
  )
}

export default function CustomerPage({ params }: { params: { id: string } }) {
  return (
    <AuthProvider>
      <Customer360PageContent customerId={params.id} />
    </AuthProvider>
  )
}

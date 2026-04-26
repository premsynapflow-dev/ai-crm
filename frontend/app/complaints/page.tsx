"use client"

import { useAuth } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { ComplaintsInbox } from '@/components/complaints-inbox'

function ComplaintsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <ComplaintsInbox />
    </DashboardLayout>
  )
}

export default function ComplaintsPage() {
  return (
    <>
      <ComplaintsPageContent />
    </>
  )
}

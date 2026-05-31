"use client"

import { useAuth } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { WorkflowsContent } from '@/components/workflows-content'

function WorkflowsPageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <WorkflowsContent />
    </DashboardLayout>
  )
}

export default function WorkflowsPage() {
  return <WorkflowsPageContent />
}

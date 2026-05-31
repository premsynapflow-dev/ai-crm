"use client"

import { useAuth } from '@/lib/auth-context'
import { LoginForm } from '@/components/login-form'
import { DashboardLayout } from '@/components/dashboard-layout'
import { KnowledgeBaseContent } from '@/components/knowledge-base-content'

function KnowledgeBasePageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <KnowledgeBaseContent />
    </DashboardLayout>
  )
}

export default function KnowledgeBasePage() {
  return <KnowledgeBasePageContent />
}

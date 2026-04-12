"use client"

import { AuthProvider, useAuth } from '@/lib/auth-context'
import { DashboardLayout } from '@/components/dashboard-layout'
import { LoginForm } from '@/components/login-form'
import { ReplyQueueContent } from '@/components/reply-queue-content'

function ReplyQueuePageContent() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  return (
    <DashboardLayout>
      <ReplyQueueContent />
    </DashboardLayout>
  )
}

export default function ReplyQueuePage() {
  return (
    <AuthProvider>
      <ReplyQueuePageContent />
    </AuthProvider>
  )
}

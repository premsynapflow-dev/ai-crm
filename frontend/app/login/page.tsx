"use client"

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import { LoginForm } from '@/components/login-form'
import { useAuth } from '@/lib/auth-context'

function LoginPageContent() {
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuth()

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/dashboard')
    }
  }, [isAuthenticated, isLoading, router])

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (isAuthenticated) {
    return <div className="flex min-h-screen items-center justify-center">Redirecting to dashboard...</div>
  }

  return <LoginForm />
}

export default function LoginPage() {
  return (
    <>
      <LoginPageContent />
    </>
  )
}

"use client"

import Link from 'next/link'
import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'

import { Customer360Page } from '@/components/customer-360-page'
import { DashboardLayout } from '@/components/dashboard-layout'
import { LoginForm } from '@/components/login-form'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/lib/auth-context'

function CustomerPageContent() {
  const { isAuthenticated, isLoading } = useAuth()
  const searchParams = useSearchParams()
  const customerId = searchParams.get('id')?.trim() ?? ''

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  if (!customerId) {
    return (
      <DashboardLayout>
        <Card>
          <CardHeader>
            <CardTitle>Customer not selected</CardTitle>
            <CardDescription>Choose a customer from the directory to open their 360 view.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link href="/customers">Back to customers</Link>
            </Button>
          </CardContent>
        </Card>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <Customer360Page customerId={customerId} />
    </DashboardLayout>
  )
}

function CustomerPageFallback() {
  return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
}

export default function CustomerPage() {
  return (
    <>
      <Suspense fallback={<CustomerPageFallback />}>
        <CustomerPageContent />
      </Suspense>
    </>
  )
}

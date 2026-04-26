"use client"

import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { ComplianceContent } from '@/components/compliance-content'
import { DashboardLayout } from '@/components/dashboard-layout'
import { LoginForm } from '@/components/login-form'
import { isRbiEligibleCompany } from '@/lib/company-profile'
import { planIncludesFeature } from '@/lib/plan-features'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ShieldCheck } from 'lucide-react'

function CompliancePageContent() {
  const { isAuthenticated, isLoading, user } = useAuth()

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading SynapFlow...</div>
  }

  if (!isAuthenticated) {
    return <LoginForm />
  }

  if (!isRbiEligibleCompany(user?.business_sector, user?.is_rbi_regulated)) {
    return (
      <DashboardLayout>
        <div className="mx-auto max-w-3xl py-8">
          <Card>
            <CardHeader>
              <div className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <CardTitle>RBI compliance is not enabled for this workspace</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>
                This workspace is currently marked as a non-RBI-regulated company. RBI compliance tools are shown only for eligible RBI-regulated financial institutions selected during signup.
              </p>
              <Link href="/dashboard">
                <Button>Back to dashboard</Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    )
  }

  if (!planIncludesFeature(user?.plan_id, 'rbi_compliance')) {
    return (
      <DashboardLayout>
        <div className="mx-auto max-w-3xl py-8">
          <Card>
            <CardHeader>
              <div className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <CardTitle>RBI compliance requires Scale or Enterprise</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>
                This workspace is eligible for RBI-regulated workflows, but the compliance suite is only available on the Scale and Enterprise plans.
              </p>
              <Link href="/pricing">
                <Button>View plans</Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <ComplianceContent />
    </DashboardLayout>
  )
}

export default function CompliancePage() {
  return (
    <>
      <CompliancePageContent />
    </>
  )
}

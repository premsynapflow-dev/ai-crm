"use client"

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  Loader2,
  LogOut,
  ShieldCheck,
  Ticket,
  TrendingUp,
  Users,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface AdminDashboardData {
  overview: {
    total_tenants: number
    active_tenants: number
    total_tickets: number
    tickets_this_month: number
    total_customers: number
    active_subscriptions: number
  }
  auto_reply_metrics: {
    total_generated: number
    auto_approved: number
    approval_rate: number
  }
  sla_metrics: {
    compliance_rate: number
    total_tracked: number
  }
  tenants_by_plan: Record<string, number>
  recent_signups: Array<{
    id: string
    name: string
    plan: string
    created_at: string
  }>
  top_tenants: Array<{
    name: string
    plan: string
    ticket_count: number
  }>
}

const ADMIN_TOKEN_KEY = 'admin_token'

const planAccent: Record<string, string> = {
  starter: 'bg-sky-500',
  growth: 'bg-emerald-500',
  enterprise: 'bg-amber-500',
}

export default function AdminDashboardPage() {
  const router = useRouter()
  const [data, setData] = useState<AdminDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const adminToken = window.localStorage.getItem(ADMIN_TOKEN_KEY)
    if (!adminToken) {
      router.replace('/admin/login')
      return
    }

    const fetchAdminData = async () => {
      try {
        const response = await fetch('/api/admin/dashboard/overview', {
          headers: {
            Authorization: `Bearer ${adminToken}`,
          },
        })

        if (response.status === 401) {
          window.localStorage.removeItem(ADMIN_TOKEN_KEY)
          router.replace('/admin/login')
          return
        }

        if (!response.ok) {
          throw new Error('Failed to fetch admin data')
        }

        const payload = (await response.json()) as AdminDashboardData
        setData(payload)
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : 'Failed to fetch admin data')
      } finally {
        setLoading(false)
      }
    }

    void fetchAdminData()
  }, [router])

  const statCards = useMemo(() => {
    if (!data) {
      return []
    }

    return [
      {
        label: 'Total tenants',
        value: data.overview.total_tenants.toLocaleString(),
        hint: `${data.overview.active_tenants.toLocaleString()} active in the last 30 days`,
        icon: Users,
      },
      {
        label: 'Tickets processed',
        value: data.overview.total_tickets.toLocaleString(),
        hint: `${data.overview.tickets_this_month.toLocaleString()} this month`,
        icon: Ticket,
      },
      {
        label: 'Auto-approval rate',
        value: `${data.auto_reply_metrics.approval_rate}%`,
        hint: `${data.auto_reply_metrics.auto_approved.toLocaleString()} drafts auto-approved`,
        icon: CheckCircle2,
      },
      {
        label: 'SLA compliance',
        value: `${data.sla_metrics.compliance_rate}%`,
        hint: `${data.sla_metrics.total_tracked.toLocaleString()} tracked tickets`,
        icon: TrendingUp,
      },
    ]
  }, [data])

  const handleLogout = () => {
    window.localStorage.removeItem(ADMIN_TOKEN_KEY)
    router.push('/admin/login')
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#f8fafc_0%,#eef4ff_100%)]">
        <div className="text-center">
          <Loader2 className="mx-auto h-12 w-12 animate-spin text-slate-700" />
          <p className="mt-4 text-slate-600">Loading platform admin dashboard...</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#f8fafc_0%,#eef4ff_100%)] px-4">
        <Card className="w-full max-w-lg rounded-[1.75rem] border-rose-200">
          <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle className="h-12 w-12 text-rose-600" />
            <div>
              <h1 className="text-2xl font-semibold text-slate-950">Unable to load admin data</h1>
              <p className="mt-2 text-slate-600">{error || 'Please sign in again and retry.'}</p>
            </div>
            <Button onClick={() => router.push('/admin/login')} className="bg-slate-950 text-white hover:bg-slate-800">
              Back to admin login
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef4ff_100%)] text-slate-950">
      <section className="border-b border-slate-200 bg-[linear-gradient(135deg,#0f172a_0%,#1d4ed8_100%)] text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:flex-row lg:items-end lg:justify-between lg:px-8">
          <div>
            <Badge className="mb-4 rounded-full border-0 bg-white/15 px-4 py-1 text-white hover:bg-white/15">
              Platform administration
            </Badge>
            <h1 className="text-4xl font-semibold tracking-tight">SynapFlow Admin</h1>
            <p className="mt-2 max-w-2xl text-blue-100">
              Monitor tenant growth, platform complaint volume, AI reply quality, and SLA health across the entire SynapFlow deployment.
            </p>
          </div>
          <div className="flex items-center gap-3 self-start lg:self-auto">
            <div className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm">
              <p className="text-blue-100">Logged in as</p>
              <p className="font-medium">Platform Admin</p>
            </div>
            <Button variant="outline" onClick={handleLogout} className="border-white/25 bg-transparent text-white hover:bg-white/10">
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </Button>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {statCards.map((card) => {
            const Icon = card.icon
            return (
              <Card key={card.label} className="rounded-[1.5rem] border-slate-200 bg-white shadow-sm">
                <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
                  <div>
                    <CardTitle className="text-sm font-medium text-slate-500">{card.label}</CardTitle>
                    <div className="mt-3 text-3xl font-semibold text-slate-950">{card.value}</div>
                  </div>
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-950 text-white">
                    <Icon className="h-5 w-5" />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-500">{card.hint}</p>
                </CardContent>
              </Card>
            )
          })}
        </div>

        <Tabs defaultValue="overview" className="mt-8 space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="tenants">Tenants</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
              <Card className="rounded-[1.6rem] border-slate-200">
                <CardHeader>
                  <CardTitle>Tenant mix by plan</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.entries(data.tenants_by_plan).map(([plan, count]) => (
                    <div key={plan} className="flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className={`h-3 w-3 rounded-full ${planAccent[plan] || 'bg-slate-400'}`} />
                        <span className="font-medium capitalize text-slate-800">{plan}</span>
                      </div>
                      <span className="text-slate-600">{count}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="rounded-[1.6rem] border-slate-200">
                <CardHeader>
                  <CardTitle>Top tenants by complaint volume</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {data.top_tenants.length ? (
                    data.top_tenants.map((tenant) => (
                      <div key={`${tenant.name}-${tenant.plan}`} className="flex items-center justify-between rounded-2xl border border-slate-200 px-4 py-3">
                        <div>
                          <p className="font-medium text-slate-900">{tenant.name}</p>
                          <p className="text-sm capitalize text-slate-500">{tenant.plan}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-semibold text-slate-950">{tenant.ticket_count}</p>
                          <p className="text-sm text-slate-500">tickets</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500">No tenant complaint data available yet.</p>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <Card className="rounded-[1.6rem] border-slate-200">
                <CardHeader>
                  <CardTitle>Recent tenant signups</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {data.recent_signups.length ? (
                    data.recent_signups.map((signup) => (
                      <div key={signup.id} className="flex items-center justify-between rounded-2xl border border-slate-200 px-4 py-3">
                        <div>
                          <p className="font-medium text-slate-900">{signup.name}</p>
                          <p className="text-sm text-slate-500">
                            Joined {new Date(signup.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <Badge variant="outline" className="capitalize">
                          {signup.plan}
                        </Badge>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500">No recent signups found.</p>
                  )}
                </CardContent>
              </Card>

              <Card className="rounded-[1.6rem] border-slate-200">
                <CardHeader>
                  <CardTitle>Platform health snapshot</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center gap-3">
                      <ShieldCheck className="h-5 w-5 text-emerald-600" />
                      <div>
                        <p className="font-medium text-slate-900">SLA compliance</p>
                        <p className="text-sm text-slate-500">
                          {data.sla_metrics.compliance_rate}% across tracked complaints
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center gap-3">
                      <Building2 className="h-5 w-5 text-blue-600" />
                      <div>
                        <p className="font-medium text-slate-900">Active subscriptions</p>
                        <p className="text-sm text-slate-500">
                          {data.overview.active_subscriptions.toLocaleString()} paying or active accounts
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center gap-3">
                      <Users className="h-5 w-5 text-amber-600" />
                      <div>
                        <p className="font-medium text-slate-900">Customer profiles</p>
                        <p className="text-sm text-slate-500">
                          {data.overview.total_customers.toLocaleString()} master customer records stored
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="tenants">
            <Card className="rounded-[1.6rem] border-slate-200">
              <CardHeader>
                <CardTitle>Tenant management</CardTitle>
              </CardHeader>
              <CardContent className="text-slate-600">
                Tenant-level controls are wired on the backend and ready for deeper CRUD actions next. This view is set up for plan upgrades, search, and lifecycle controls as the next admin iteration.
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics">
            <Card className="rounded-[1.6rem] border-slate-200">
              <CardHeader>
                <CardTitle>Analytics and insights</CardTitle>
              </CardHeader>
              <CardContent className="text-slate-600">
                The platform overview already exposes the key aggregate metrics. We can expand this tab next with usage trends, billing metrics, and queue health charts once you want a fuller admin analytics surface.
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </section>
    </main>
  )
}

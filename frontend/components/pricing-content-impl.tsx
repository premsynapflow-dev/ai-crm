"use client"

import { useEffect, useState } from 'react'
import { Building2, Check, Crown, Loader2, Sparkles, TrendingUp, Zap } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuth } from '@/lib/auth-context'
import { billingAPI, type Invoice, type Plan } from '@/lib/api/billing'
import { PLAN_ORDER } from '@/lib/plan-features'

const planIcons = {
  free: Sparkles,
  starter: Zap,
  pro: TrendingUp,
  max: Sparkles,
  scale: Building2,
  enterprise: Crown,
} as const

const planColors = {
  free: 'from-slate-700 via-slate-600 to-slate-400',
  starter: 'from-sky-500 via-cyan-500 to-emerald-400',
  pro: 'from-violet-500 via-fuchsia-500 to-rose-400',
  max: 'from-orange-500 via-amber-500 to-yellow-400',
  scale: 'from-emerald-500 via-green-500 to-lime-400',
  enterprise: 'from-slate-900 via-slate-700 to-slate-500',
} as const

function visibleFeatures(features: string[]) {
  return features.filter((feature) => !feature.toLowerCase().includes('zapier'))
}

function formatPrice(price: number | null, cycle: 'monthly' | 'annual') {
  if (price === 0) {
    return 'Free forever'
  }
  if (!price) {
    return 'Custom quote'
  }
  return `INR ${price.toLocaleString('en-IN')}/${cycle === 'annual' ? 'yr' : 'mo'}`
}

function formatLimit(value: number) {
  return value >= 999999 ? 'Unlimited' : value.toLocaleString('en-IN')
}

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as Record<string, unknown>).message)
  }
  return fallback
}

export function PricingContentImpl() {
  const { user } = useAuth()
  const [plans, setPlans] = useState<Record<string, Plan>>({})
  const [currentPlanId, setCurrentPlanId] = useState<string>(user?.plan_id ?? 'free')
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [isAnnual, setIsAnnual] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isUpgrading, setIsUpgrading] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadBilling() {
      try {
        const [plansResponse, usageResponse, invoicesResponse] = await Promise.all([
          billingAPI.getPlans(),
          billingAPI.getUsage(),
          billingAPI.getInvoices(),
        ])
        if (!active) {
          return
        }
        setPlans(plansResponse)
        setCurrentPlanId(usageResponse.plan_id ?? user?.plan_id ?? 'free')
        setInvoices(invoicesResponse)
      } catch {
        if (active) {
          toast.error('Failed to load pricing plans')
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadBilling()

    return () => {
      active = false
    }
  }, [user?.plan_id])

  const featureRows = [
    { label: 'AI classification', value: (plan: Plan) => (plan.feature_flags.ai_classification ? 'Included' : '-') },
    { label: 'Sentiment analysis', value: (plan: Plan) => (plan.feature_flags.sentiment_analysis ? 'Included' : '-') },
    { label: 'AI suggested responses', value: (plan: Plan) => (plan.feature_flags.ai_suggested_responses ? 'Included' : '-') },
    { label: 'AI auto-reply', value: (plan: Plan) => (plan.feature_flags.ai_auto_reply ? 'Included' : '-') },
    { label: 'Churn risk scoring', value: (plan: Plan) => (plan.feature_flags.churn_risk_scoring ? 'Included' : '-') },
    { label: 'Root cause analysis', value: (plan: Plan) => (plan.feature_flags.root_cause_analysis ? 'Included' : '-') },
    { label: 'Team performance', value: (plan: Plan) => (plan.feature_flags.team_performance ? 'Included' : '-') },
    { label: 'API access', value: (plan: Plan) => (plan.feature_flags.api_access ? 'Included' : '-') },
    { label: 'Webhooks', value: (plan: Plan) => (plan.feature_flags.webhooks ? 'Included' : '-') },
    { label: 'Channels', value: (plan: Plan) => plan.feature_flags.multi_channel.join(', ') },
  ]

  const handleUpgrade = async (planId: string) => {
    if (planId === 'enterprise') {
      window.location.href = 'mailto:sales@synapflow.com?subject=SynapFlow%20Enterprise'
      return
    }

    setIsUpgrading(planId)
    try {
      const result = await billingAPI.upgradePlan(planId, isAnnual ? 'annual' : 'monthly')
      if (result.payment_url) {
        toast.success('Redirecting to Razorpay checkout...')
        window.location.href = result.payment_url
        return
      }
      setCurrentPlanId(planId)
      toast.success(`Plan updated to ${plans[planId]?.name ?? planId}`)
    } catch (error) {
      toast.error(getErrorMessage(error, 'Unable to start upgrade flow'))
    } finally {
      setIsUpgrading(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[65vh] items-center justify-center gap-3">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm text-muted-foreground">Loading pricing plans...</span>
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <section className="overflow-hidden rounded-[32px] border border-white/60 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.18),_transparent_34%),radial-gradient(circle_at_top_right,_rgba(168,85,247,0.16),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(241,245,249,0.92))] p-8 shadow-[0_35px_100px_-55px_rgba(15,23,42,0.65)]">
        <div className="mx-auto max-w-3xl text-center">
          <Badge className="bg-slate-900 text-white hover:bg-slate-900">SynapFlow Pricing</Badge>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950">Choose the right growth lane</h1>
          <p className="mt-3 text-base text-slate-600">
            Start with complaint intelligence, then unlock sentiment, churn risk, root cause analysis, and team performance as you scale.
          </p>
          <div className="mt-6 inline-flex items-center gap-3 rounded-full border bg-white px-5 py-3 shadow-sm">
            <Label htmlFor="billing-toggle" className={!isAnnual ? 'font-semibold text-slate-900' : 'text-slate-500'}>
              Monthly
            </Label>
            <Switch id="billing-toggle" checked={isAnnual} onCheckedChange={setIsAnnual} />
            <Label htmlFor="billing-toggle" className={isAnnual ? 'font-semibold text-slate-900' : 'text-slate-500'}>
              Annual
            </Label>
            <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">Save 2 months</Badge>
          </div>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-6">
        {PLAN_ORDER.map((planId) => {
          const plan = plans[planId]
          if (!plan) {
            return null
          }

          const Icon = planIcons[planId]
          const isCurrent = currentPlanId === planId
          const isFeatured = planId === 'max'
          const price = isAnnual ? plan.annual_price : plan.monthly_price

          return (
            <Card
              key={planId}
              className={`relative overflow-hidden border-white/70 bg-white/90 shadow-[0_22px_80px_-54px_rgba(15,23,42,0.55)] ${
                isFeatured ? 'ring-2 ring-orange-300' : ''
              }`}
            >
              {isFeatured && (
                <div className="absolute right-4 top-4 rounded-full bg-orange-500 px-3 py-1 text-xs font-semibold text-white">
                  Most recommended
                </div>
              )}
              <CardHeader>
                <div className={`mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br ${planColors[planId]} text-white shadow-lg`}>
                  <Icon className="h-6 w-6" />
                </div>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>
                  {planId === 'free'
                    ? 'Free forever for solo teams getting started'
                    : plan.trial_days
                      ? `${plan.trial_days} day trial${plan.trial_requires_card ? ', card required' : ', no card required'}`
                      : 'Sales-assisted onboarding'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <p className="text-3xl font-semibold tracking-tight text-slate-950">{formatPrice(price, isAnnual ? 'annual' : 'monthly')}</p>
                  {isAnnual && plan.annual_savings ? (
                    <p className="mt-1 text-sm font-medium text-emerald-600">Save ₹{plan.annual_savings.toLocaleString('en-IN')}</p>
                  ) : null}
                </div>

                <div className="space-y-2 rounded-2xl border bg-slate-50/80 p-4 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Tickets/month</span>
                    <span className="font-medium">{formatLimit(plan.tickets_per_month)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Team seats</span>
                    <span className="font-medium">{formatLimit(plan.team_seats)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Overage</span>
                    <span className="font-medium">{plan.overage_rate > 0 ? `₹${plan.overage_rate}/ticket` : 'Included'}</span>
                  </div>
                </div>

                <div className="space-y-3">
                  {visibleFeatures(plan.features).map((feature) => (
                    <div key={feature} className="flex gap-2 text-sm">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
              <CardFooter>
                <Button
                  className="w-full"
                  variant={isFeatured || isCurrent ? 'default' : 'outline'}
                  disabled={isCurrent || isUpgrading === planId}
                  onClick={() => void handleUpgrade(planId)}
                >
                  {isUpgrading === planId ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Processing
                    </>
                  ) : isCurrent ? (
                    'Current plan'
                  ) : planId === 'enterprise' ? (
                    'Contact sales'
                  ) : (
                    'Get started'
                  )}
                </Button>
              </CardFooter>
            </Card>
          )
        })}
      </section>

      <section>
        <Card className="border-white/70 bg-white/90 shadow-[0_22px_80px_-54px_rgba(15,23,42,0.55)]">
          <CardHeader>
            <CardTitle>Feature comparison</CardTitle>
            <CardDescription>Compare the core capability unlocks across all six SynapFlow plans.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[220px]">Capability</TableHead>
                    {PLAN_ORDER.map((planId) => (
                      <TableHead key={planId}>{plans[planId]?.name ?? planId}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {featureRows.map((row) => (
                    <TableRow key={row.label}>
                      <TableCell className="font-medium">{row.label}</TableCell>
                      {PLAN_ORDER.map((planId) => (
                        <TableCell key={`${row.label}-${planId}`}>{plans[planId] ? row.value(plans[planId]) : '-'}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card className="border-white/70 bg-white/90 shadow-[0_22px_80px_-54px_rgba(15,23,42,0.55)]">
          <CardHeader>
            <CardTitle>Invoices</CardTitle>
            <CardDescription>Billing records currently stored for this client account.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Issued</TableHead>
                  <TableHead>Paid</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      No invoices have been generated yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  invoices.map((invoice) => (
                    <TableRow key={invoice.id}>
                      <TableCell className="font-medium">{invoice.invoice_number}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{invoice.status}</Badge>
                      </TableCell>
                      <TableCell>INR {invoice.total.toLocaleString('en-IN')}</TableCell>
                      <TableCell>{invoice.invoice_date ? new Date(invoice.invoice_date).toLocaleDateString('en-IN') : '-'}</TableCell>
                      <TableCell>{invoice.paid_at ? new Date(invoice.paid_at).toLocaleDateString('en-IN') : '-'}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

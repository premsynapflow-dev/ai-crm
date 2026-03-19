"use client"

import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/lib/auth-context'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Progress } from '@/components/ui/progress'
import { Check, X, CreditCard, Zap, Building2, Sparkles, Download, FileText, Loader2 } from 'lucide-react'
import { billingAPI, type Invoice, type Plan, type Usage } from '@/lib/api/billing'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

const planOrder = ['trial', 'pro', 'business']
const fallbackPlanFeatures: Record<string, string[]> = {
  trial: ['Email widget', 'Slack'],
  pro: ['All channels', 'Slack', 'Automation', '7 day support'],
  business: ['API access', 'Advanced automation', 'Analytics', 'Priority support'],
}

export function PricingContent() {
  const { user, updatePlan } = useAuth()
  const [plans, setPlans] = useState<Record<string, Plan>>({})
  const [usage, setUsage] = useState<Usage | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null)
  const [paymentModalOpen, setPaymentModalOpen] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

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
        setUsage(usageResponse)
        setInvoices(invoicesResponse)
      } catch {
        if (active) {
          toast.error('Failed to load billing data')
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
  }, [])

  const orderedPlans = useMemo(() => {
    return planOrder
      .map((planId) => plans[planId])
      .filter((plan): plan is Plan => Boolean(plan))
  }, [plans])

  const currentPlanId = user?.plan ?? usage?.plan_id ?? 'trial'
  const currentPlanData = orderedPlans.find((plan) => plan.id === currentPlanId)
  const usagePercentage = usage?.usage_percentage ?? 0
  const latestPaymentMethod = invoices.find((invoice) => invoice.payment_method)?.payment_method ?? null

  const handleUpgrade = (plan: Plan) => {
    if (plan.id === currentPlanId) {
      return
    }
    setSelectedPlan(plan)
    setPaymentModalOpen(true)
  }

  const handleConfirmPlanChange = async () => {
    if (!selectedPlan) {
      return
    }

    setIsProcessing(true)
    try {
      await updatePlan(selectedPlan.id as 'trial' | 'pro' | 'business')
      const refreshedUsage = await billingAPI.getUsage()
      setUsage(refreshedUsage)
      setPaymentModalOpen(false)
      toast.success(`Plan updated to ${selectedPlan.name}`)
    } catch {
      toast.error('Failed to update plan')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleDownloadInvoice = (invoiceId: string) => {
    const downloadUrl = `/portal/invoice/${invoiceId}`
    window.open(downloadUrl, '_blank', 'noopener,noreferrer')
  }

  if (isLoading) {
    return <div className="flex h-96 items-center justify-center">Loading billing data...</div>
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Billing & Plans</h1>
        <p className="mt-1 text-muted-foreground">Manage your subscription and billing information</p>
      </div>

      <Card className="border-blue-100 bg-gradient-to-br from-blue-50 to-purple-50">
        <CardContent className="p-6">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold">Current Plan: {currentPlanData?.name ?? currentPlanId}</h2>
                <Badge className="bg-gradient-to-r from-blue-600 to-purple-600">Active</Badge>
              </div>
              <p className="text-muted-foreground">
                {currentPlanId === 'trial'
                  ? 'You are on the free trial plan'
                  : `Billed monthly at INR ${(currentPlanData?.price ?? 0).toLocaleString()}`}
              </p>
              <p className="text-sm text-muted-foreground">
                Next billing date:{' '}
                {usage?.period_end
                  ? new Date(usage.period_end).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })
                  : 'Not available'}
              </p>
            </div>
            <div className="max-w-md flex-1">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium">Usage this month</span>
                <span className="text-sm text-muted-foreground">
                  {usage?.current_usage ?? 0} / {usage?.monthly_limit ?? 0} tickets
                </span>
              </div>
              <Progress value={usagePercentage} className="h-3" />
              {usagePercentage > 80 && (
                <p className="mt-2 text-sm text-orange-600">
                  You&apos;re approaching your monthly limit. Consider upgrading.
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-6 text-2xl font-bold">Choose Your Plan</h2>
        <div className="grid gap-6 lg:grid-cols-3">
          {orderedPlans.map((plan) => {
            const features = plan.features.length > 0 ? plan.features : fallbackPlanFeatures[plan.id] ?? []
            const isPopular = plan.id === 'pro'
            return (
              <Card
                key={plan.id}
                className={cn(
                  'relative transition-all hover:shadow-lg',
                  isPopular && 'border-2 border-primary shadow-lg',
                  currentPlanId === plan.id && 'ring-2 ring-green-500',
                )}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-gradient-to-r from-blue-600 to-purple-600 px-4 text-white">
                      <Sparkles className="mr-1 h-3 w-3" />
                      Most Popular
                    </Badge>
                  </div>
                )}
                {currentPlanId === plan.id && (
                  <div className="absolute -top-3 right-4">
                    <Badge className="bg-green-600 text-white">Current Plan</Badge>
                  </div>
                )}

                <CardHeader className="pb-2 pt-8 text-center">
                  <div className="mx-auto mb-4 w-fit rounded-xl bg-gradient-to-br from-blue-100 to-purple-100 p-3">
                    {plan.id === 'trial' ? (
                      <Zap className="h-8 w-8 text-primary" />
                    ) : plan.id === 'pro' ? (
                      <CreditCard className="h-8 w-8 text-primary" />
                    ) : (
                      <Building2 className="h-8 w-8 text-primary" />
                    )}
                  </div>
                  <CardTitle className="text-2xl">{plan.name}</CardTitle>
                  <CardDescription>
                    {plan.id === 'trial'
                      ? 'Perfect for getting started'
                      : plan.id === 'pro'
                        ? 'Best for growing businesses'
                        : 'For large organizations'}
                  </CardDescription>
                </CardHeader>

                <CardContent className="text-center">
                  <div className="mb-6">
                    <span className="text-4xl font-bold">INR {plan.price.toLocaleString()}</span>
                    <span className="text-muted-foreground">/month</span>
                  </div>

                  <div className="space-y-3 text-left">
                    <div className="flex items-center gap-2">
                      <Check className="h-5 w-5 shrink-0 text-green-600" />
                      <span className="text-sm">{plan.monthly_tickets.toLocaleString()} tickets/month</span>
                    </div>
                    {features.map((feature) => (
                      <div key={feature} className="flex items-center gap-2">
                        <Check className="h-5 w-5 shrink-0 text-green-600" />
                        <span className="text-sm">{feature}</span>
                      </div>
                    ))}
                    {plan.id === 'trial' && (
                      <div className="flex items-center gap-2">
                        <X className="h-5 w-5 shrink-0 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">API access</span>
                      </div>
                    )}
                  </div>

                  {plan.overage_rate ? (
                    <p className="mt-4 text-sm text-muted-foreground">
                      INR {plan.overage_rate} per ticket overage
                    </p>
                  ) : (
                    <p className="mt-4 text-sm text-muted-foreground">No overage charges</p>
                  )}
                </CardContent>

                <CardFooter>
                  <Button
                    className={cn(
                      'w-full',
                      currentPlanId === plan.id
                        ? 'bg-green-600 hover:bg-green-600'
                        : isPopular
                          ? 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700'
                          : '',
                    )}
                    variant={currentPlanId === plan.id ? 'default' : isPopular ? 'default' : 'outline'}
                    disabled={currentPlanId === plan.id}
                    onClick={() => handleUpgrade(plan)}
                  >
                    {currentPlanId === plan.id ? 'Current Plan' : 'Switch Plan'}
                  </Button>
                </CardFooter>
              </Card>
            )
          })}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Feature Comparison</CardTitle>
          <CardDescription>Live plan details from your configured billing catalog</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[300px]">Plan</TableHead>
                  <TableHead>Monthly Tickets</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Overage</TableHead>
                  <TableHead>Features</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orderedPlans.map((plan) => (
                  <TableRow key={plan.id}>
                    <TableCell className="font-medium">{plan.name}</TableCell>
                    <TableCell>{plan.monthly_tickets.toLocaleString()}</TableCell>
                    <TableCell>INR {plan.price.toLocaleString()}</TableCell>
                    <TableCell>{plan.overage_rate ? `INR ${plan.overage_rate}/ticket` : 'None'}</TableCell>
                    <TableCell>{(plan.features.length > 0 ? plan.features : fallbackPlanFeatures[plan.id] ?? []).join(', ')}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Payment History</CardTitle>
            <CardDescription>Your recent invoices and payments</CardDescription>
          </div>
          <Button variant="outline" className="gap-2" disabled>
            <FileText className="h-4 w-4" />
            Export All
          </Button>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Payment Method</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      No invoices available yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  invoices.map((invoice) => (
                    <TableRow key={invoice.id}>
                      <TableCell className="font-mono text-sm">{invoice.invoice_number}</TableCell>
                      <TableCell>
                        {new Date(invoice.invoice_date ?? invoice.paid_at ?? Date.now()).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                        })}
                      </TableCell>
                      <TableCell>INR {invoice.total.toLocaleString()}</TableCell>
                      <TableCell>{invoice.payment_method || 'Not recorded'}</TableCell>
                      <TableCell>
                        <Badge className={cn(
                          invoice.status === 'paid' && 'bg-green-100 text-green-700',
                          invoice.status === 'pending' && 'bg-yellow-100 text-yellow-700',
                          invoice.status === 'failed' && 'bg-red-100 text-red-700',
                        )}>
                          {invoice.status.charAt(0).toUpperCase() + invoice.status.slice(1)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadInvoice(invoice.id)}
                          className="gap-2"
                        >
                          <Download className="h-4 w-4" />
                          Invoice
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
          <CardDescription>Latest payment method observed on your invoices</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-gradient-to-br from-blue-600 to-purple-600 p-3">
                <CreditCard className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="font-medium">{latestPaymentMethod || 'No payment method on file yet'}</p>
                <p className="text-sm text-muted-foreground">
                  {latestPaymentMethod ? 'Captured from your latest invoice' : 'A payment method will appear here after your first processed invoice'}
                </p>
              </div>
            </div>
            <Button variant="outline" disabled>
              Update Billing
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={paymentModalOpen} onOpenChange={setPaymentModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Switch to {selectedPlan?.name}</DialogTitle>
            <DialogDescription>
              Confirm the plan change. This updates your plan in SynapFlow and refreshes your usage limits immediately.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            <div className="space-y-2 rounded-lg bg-muted/50 p-4">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Plan</span>
                <span className="font-medium">{selectedPlan?.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tickets/month</span>
                <span className="font-medium">{selectedPlan?.monthly_tickets.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Overage</span>
                <span className="font-medium">
                  {selectedPlan?.overage_rate ? `INR ${selectedPlan.overage_rate}/ticket` : 'None'}
                </span>
              </div>
              <Separator />
              <div className="flex justify-between text-lg">
                <span className="font-medium">Monthly price</span>
                <span className="font-bold">INR {selectedPlan?.price.toLocaleString()}</span>
              </div>
            </div>

            <p className="text-sm text-muted-foreground">
              This confirmation updates the plan record in your SynapFlow account. If you later wire in a payment gateway,
              this is the place to swap in a real checkout flow.
            </p>

            <Button
              onClick={handleConfirmPlanChange}
              disabled={isProcessing}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="mr-2 animate-spin" />
                  Updating Plan...
                </>
              ) : (
                <>
                  <CreditCard className="mr-2 h-4 w-4" />
                  Confirm Plan Change
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}


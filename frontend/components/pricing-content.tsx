"use client"

import { useState } from 'react'
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
import { Input } from '@/components/ui/input'
import { FieldGroup, Field, FieldLabel } from '@/components/ui/field'
import { Check, X, CreditCard, Zap, Building2, Sparkles, Download, FileText, Loader2 } from 'lucide-react'
import { generateInvoices, usageData } from '@/lib/sample-data'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface Plan {
  id: 'trial' | 'pro' | 'business'
  name: string
  price: number
  ticketsPerMonth: number
  overage?: number
  features: { name: string; included: boolean }[]
  popular?: boolean
}

const plans: Plan[] = [
  {
    id: 'trial',
    name: 'Trial',
    price: 0,
    ticketsPerMonth: 50,
    features: [
      { name: '50 tickets/month', included: true },
      { name: 'Basic AI classification', included: true },
      { name: 'Email support', included: true },
      { name: 'AI-generated responses', included: false },
      { name: 'Priority support', included: false },
      { name: 'Custom AI training', included: false },
      { name: 'API access', included: false },
      { name: 'Dedicated account manager', included: false }
    ]
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 999,
    ticketsPerMonth: 500,
    overage: 2,
    popular: true,
    features: [
      { name: '500 tickets/month', included: true },
      { name: 'Advanced AI classification', included: true },
      { name: 'Email support', included: true },
      { name: 'AI-generated responses', included: true },
      { name: 'Priority email support', included: true },
      { name: 'Custom AI training', included: false },
      { name: 'API access', included: false },
      { name: 'Dedicated account manager', included: false }
    ]
  },
  {
    id: 'business',
    name: 'Business',
    price: 4999,
    ticketsPerMonth: 5000,
    overage: 1,
    features: [
      { name: '5,000 tickets/month', included: true },
      { name: 'Advanced AI classification', included: true },
      { name: 'Email support', included: true },
      { name: 'AI-generated responses', included: true },
      { name: 'Priority support', included: true },
      { name: 'Custom AI training', included: true },
      { name: 'API access', included: true },
      { name: 'Dedicated account manager', included: true }
    ]
  }
]

export function PricingContent() {
  const { user, updatePlan } = useAuth()
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null)
  const [paymentModalOpen, setPaymentModalOpen] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [invoices] = useState(() => generateInvoices(10))

  const currentPlan = user?.plan || 'trial'
  const currentPlanData = plans.find(p => p.id === currentPlan)

  const handleUpgrade = (plan: Plan) => {
    if (plan.id === currentPlan) return
    setSelectedPlan(plan)
    setPaymentModalOpen(true)
  }

  const handlePayment = async () => {
    if (!selectedPlan) return
    
    setIsProcessing(true)
    // Simulate payment processing
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    updatePlan(selectedPlan.id)
    setIsProcessing(false)
    setPaymentModalOpen(false)
    toast.success(`Successfully upgraded to ${selectedPlan.name} plan!`)
  }

  const handleDownloadInvoice = (invoiceId: string) => {
    toast.success(`Downloading invoice ${invoiceId}`)
  }

  const usagePercentage = (usageData.ticketsUsed / usageData.ticketsLimit) * 100

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Billing & Plans</h1>
        <p className="text-muted-foreground mt-1">Manage your subscription and billing information</p>
      </div>

      {/* Current Plan Overview */}
      <Card className="bg-gradient-to-br from-blue-50 to-purple-50 border-blue-100">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold">Current Plan: {currentPlanData?.name}</h2>
                <Badge className="bg-gradient-to-r from-blue-600 to-purple-600">Active</Badge>
              </div>
              <p className="text-muted-foreground">
                {currentPlan === 'trial' 
                  ? 'You are on the free trial plan'
                  : `Billed monthly at ₹${currentPlanData?.price.toLocaleString()}`
                }
              </p>
              <p className="text-sm text-muted-foreground">
                Next billing date: April 19, 2026
              </p>
            </div>
            <div className="flex-1 max-w-md">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Usage this month</span>
                <span className="text-sm text-muted-foreground">
                  {usageData.ticketsUsed} / {usageData.ticketsLimit} tickets
                </span>
              </div>
              <Progress value={usagePercentage} className="h-3" />
              {usagePercentage > 80 && (
                <p className="text-sm text-orange-600 mt-2">
                  You&apos;re approaching your monthly limit. Consider upgrading.
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pricing Cards */}
      <div>
        <h2 className="text-2xl font-bold mb-6">Choose Your Plan</h2>
        <div className="grid gap-6 lg:grid-cols-3">
          {plans.map((plan) => (
            <Card
              key={plan.id}
              className={cn(
                "relative hover:shadow-lg transition-all",
                plan.popular && "border-2 border-primary shadow-lg",
                currentPlan === plan.id && "ring-2 ring-green-500"
              )}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4">
                    <Sparkles className="h-3 w-3 mr-1" />
                    Most Popular
                  </Badge>
                </div>
              )}
              {currentPlan === plan.id && (
                <div className="absolute -top-3 right-4">
                  <Badge className="bg-green-600 text-white">Current Plan</Badge>
                </div>
              )}
              
              <CardHeader className="text-center pb-2 pt-8">
                <div className="mx-auto mb-4 p-3 bg-gradient-to-br from-blue-100 to-purple-100 rounded-xl w-fit">
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
                    : 'For large organizations'
                  }
                </CardDescription>
              </CardHeader>
              
              <CardContent className="text-center">
                <div className="mb-6">
                  <span className="text-4xl font-bold">
                    ₹{plan.price.toLocaleString()}
                  </span>
                  <span className="text-muted-foreground">/month</span>
                </div>
                
                <div className="space-y-3 text-left">
                  {plan.features.map((feature, index) => (
                    <div key={index} className="flex items-center gap-2">
                      {feature.included ? (
                        <Check className="h-5 w-5 text-green-600 shrink-0" />
                      ) : (
                        <X className="h-5 w-5 text-muted-foreground shrink-0" />
                      )}
                      <span className={cn(
                        "text-sm",
                        !feature.included && "text-muted-foreground"
                      )}>
                        {feature.name}
                      </span>
                    </div>
                  ))}
                </div>
                
                {plan.overage && (
                  <p className="text-sm text-muted-foreground mt-4">
                    ₹{plan.overage} per ticket overage
                  </p>
                )}
              </CardContent>
              
              <CardFooter>
                <Button
                  className={cn(
                    "w-full",
                    currentPlan === plan.id
                      ? "bg-green-600 hover:bg-green-600"
                      : plan.popular
                      ? "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                      : ""
                  )}
                  variant={currentPlan === plan.id ? "default" : plan.popular ? "default" : "outline"}
                  disabled={currentPlan === plan.id}
                  onClick={() => handleUpgrade(plan)}
                >
                  {currentPlan === plan.id
                    ? 'Current Plan'
                    : plans.findIndex(p => p.id === plan.id) < plans.findIndex(p => p.id === currentPlan)
                    ? 'Downgrade'
                    : 'Upgrade'
                  }
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      </div>

      {/* Feature Comparison Table */}
      <Card>
        <CardHeader>
          <CardTitle>Feature Comparison</CardTitle>
          <CardDescription>Detailed comparison of all plan features</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[300px]">Feature</TableHead>
                  <TableHead className="text-center">Trial</TableHead>
                  <TableHead className="text-center">Pro</TableHead>
                  <TableHead className="text-center">Business</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="font-medium">Monthly Tickets</TableCell>
                  <TableCell className="text-center">50</TableCell>
                  <TableCell className="text-center">500</TableCell>
                  <TableCell className="text-center">5,000</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">AI Classification</TableCell>
                  <TableCell className="text-center">Basic</TableCell>
                  <TableCell className="text-center">Advanced</TableCell>
                  <TableCell className="text-center">Advanced + Custom</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">AI-generated Responses</TableCell>
                  <TableCell className="text-center"><X className="h-5 w-5 text-muted-foreground mx-auto" /></TableCell>
                  <TableCell className="text-center"><Check className="h-5 w-5 text-green-600 mx-auto" /></TableCell>
                  <TableCell className="text-center"><Check className="h-5 w-5 text-green-600 mx-auto" /></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">API Access</TableCell>
                  <TableCell className="text-center"><X className="h-5 w-5 text-muted-foreground mx-auto" /></TableCell>
                  <TableCell className="text-center"><X className="h-5 w-5 text-muted-foreground mx-auto" /></TableCell>
                  <TableCell className="text-center"><Check className="h-5 w-5 text-green-600 mx-auto" /></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Custom AI Training</TableCell>
                  <TableCell className="text-center"><X className="h-5 w-5 text-muted-foreground mx-auto" /></TableCell>
                  <TableCell className="text-center"><X className="h-5 w-5 text-muted-foreground mx-auto" /></TableCell>
                  <TableCell className="text-center"><Check className="h-5 w-5 text-green-600 mx-auto" /></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Support</TableCell>
                  <TableCell className="text-center">Email</TableCell>
                  <TableCell className="text-center">Priority Email</TableCell>
                  <TableCell className="text-center">Phone + Dedicated Manager</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Overage Rate</TableCell>
                  <TableCell className="text-center">N/A</TableCell>
                  <TableCell className="text-center">₹2/ticket</TableCell>
                  <TableCell className="text-center">₹1/ticket</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Payment History */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Payment History</CardTitle>
            <CardDescription>Your recent invoices and payments</CardDescription>
          </div>
          <Button variant="outline" className="gap-2">
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
                  <TableHead>Plan</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((invoice) => (
                  <TableRow key={invoice.id}>
                    <TableCell className="font-mono text-sm">{invoice.id}</TableCell>
                    <TableCell>
                      {new Date(invoice.date).toLocaleDateString('en-IN', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric'
                      })}
                    </TableCell>
                    <TableCell>{invoice.plan}</TableCell>
                    <TableCell>₹{invoice.amount.toLocaleString()}</TableCell>
                    <TableCell>
                      <Badge className={cn(
                        invoice.status === 'paid' && 'bg-green-100 text-green-700',
                        invoice.status === 'pending' && 'bg-yellow-100 text-yellow-700',
                        invoice.status === 'failed' && 'bg-red-100 text-red-700'
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
                        PDF
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Payment Method */}
      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
          <CardDescription>Manage your payment information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg">
                <CreditCard className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="font-medium">Visa ending in 4242</p>
                <p className="text-sm text-muted-foreground">Expires 12/2027</p>
              </div>
            </div>
            <Button variant="outline">Update Card</Button>
          </div>
        </CardContent>
      </Card>

      {/* Payment Modal */}
      <Dialog open={paymentModalOpen} onOpenChange={setPaymentModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Upgrade to {selectedPlan?.name}</DialogTitle>
            <DialogDescription>
              Complete your payment to upgrade your plan
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* Plan Summary */}
            <div className="p-4 bg-muted/50 rounded-lg space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Plan</span>
                <span className="font-medium">{selectedPlan?.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tickets/month</span>
                <span className="font-medium">{selectedPlan?.ticketsPerMonth.toLocaleString()}</span>
              </div>
              <Separator />
              <div className="flex justify-between text-lg">
                <span className="font-medium">Total</span>
                <span className="font-bold">₹{selectedPlan?.price.toLocaleString()}/month</span>
              </div>
            </div>

            {/* Card Details */}
            <FieldGroup>
              <Field>
                <FieldLabel>Card Number</FieldLabel>
                <Input placeholder="1234 5678 9012 3456" />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field>
                  <FieldLabel>Expiry</FieldLabel>
                  <Input placeholder="MM/YY" />
                </Field>
                <Field>
                  <FieldLabel>CVV</FieldLabel>
                  <Input placeholder="123" />
                </Field>
              </div>
              <Field>
                <FieldLabel>Name on Card</FieldLabel>
                <Input placeholder="John Doe" />
              </Field>
            </FieldGroup>

            <Button
              onClick={handlePayment}
              disabled={isProcessing}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <CreditCard className="h-4 w-4 mr-2" />
                  Pay with Razorpay
                </>
              )}
            </Button>

            <p className="text-xs text-center text-muted-foreground">
              This will redirect to Razorpay payment gateway for secure processing.
              <br />
              By proceeding, you agree to our Terms of Service.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

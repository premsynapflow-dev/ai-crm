"use client"

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { AlertTriangle, TrendingUp, ArrowUpRight } from 'lucide-react'
import Link from 'next/link'
import { billingAPI, type Usage } from '@/lib/api/billing'

export function UsageContent() {
  const [usage, setUsage] = useState<Usage | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true

    billingAPI.getUsage()
      .then((response) => {
        if (active) {
          setUsage(response)
        }
      })
      .catch(() => {
        if (active) {
          setUsage(null)
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  if (isLoading) {
    return <div className="flex h-96 items-center justify-center">Loading usage data...</div>
  }

  if (!usage) {
    return <div className="flex h-96 items-center justify-center">Unable to load usage data.</div>
  }

  const usagePercentage = usage.usage_percentage
  const isNearLimit = usagePercentage > 80
  const willExceed = usage.projected_usage > usage.monthly_limit

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Usage & Limits</h1>
        <p className="mt-1 text-muted-foreground">Monitor your ticket usage and plan limits</p>
      </div>

      {isNearLimit && (
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="flex items-center gap-4 p-4">
            <div className="rounded-full bg-orange-100 p-3">
              <AlertTriangle className="h-6 w-6 text-orange-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-orange-900">You&apos;re approaching your monthly limit</p>
              <p className="text-sm text-orange-700">
                You&apos;ve used {usagePercentage.toFixed(0)}% of your monthly ticket allocation.
                Consider upgrading to avoid overage charges.
              </p>
            </div>
            <Button asChild className="bg-orange-600 hover:bg-orange-700">
              <Link href="/pricing">Upgrade Plan</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Current Usage</CardTitle>
            <CardDescription>Your ticket usage this billing period</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            <div className="relative h-48 w-48">
              <svg className="h-48 w-48 -rotate-90 transform">
                <circle
                  cx="96"
                  cy="96"
                  r="88"
                  stroke="currentColor"
                  strokeWidth="12"
                  fill="none"
                  className="text-muted"
                />
                <circle
                  cx="96"
                  cy="96"
                  r="88"
                  stroke="url(#circleGradient)"
                  strokeWidth="12"
                  fill="none"
                  strokeLinecap="round"
                  strokeDasharray={`${usagePercentage * 5.53} 553`}
                />
                <defs>
                  <linearGradient id="circleGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3B82F6" />
                    <stop offset="100%" stopColor="#8B5CF6" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-4xl font-bold">{usage.current_usage}</span>
                <span className="text-muted-foreground">of {usage.monthly_limit}</span>
                <span className="text-sm text-muted-foreground">tickets</span>
              </div>
            </div>

            <div className="mt-6 w-full space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Usage</span>
                <span className="font-medium">{usagePercentage.toFixed(1)}%</span>
              </div>
              <Progress value={usagePercentage} className="h-3" />
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Remaining</span>
                <span className="font-medium">{usage.remaining_tickets} tickets</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Usage Forecast</CardTitle>
            <CardDescription>Projected usage based on current rate</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="rounded-xl bg-gradient-to-br from-blue-50 to-purple-50 p-6 text-center">
              <p className="mb-2 text-sm text-muted-foreground">Projected Monthly Usage</p>
              <p className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-4xl font-bold text-transparent">
                ~{usage.projected_usage}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">tickets</p>
              {willExceed && (
                <Badge className="mt-4 bg-orange-100 text-orange-700">
                  <TrendingUp className="mr-1 h-3 w-3" />
                  {usage.projected_usage - usage.monthly_limit} over limit
                </Badge>
              )}
            </div>

            {willExceed && (
              <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                <p className="text-sm text-orange-800">
                  <strong>Heads up!</strong> At your current rate, you&apos;ll use approximately {usage.projected_usage} tickets this month,
                  which is {usage.projected_usage - usage.monthly_limit} tickets over your limit.
                </p>
                <Button asChild variant="link" className="mt-2 h-auto p-0 text-orange-700">
                  <Link href="/pricing">
                    Upgrade to avoid overage charges
                    <ArrowUpRight className="ml-1 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            )}

            <div className="space-y-3">
              <div className="flex justify-between rounded-lg bg-muted/50 p-3">
                <span className="text-sm text-muted-foreground">Days remaining</span>
                <span className="font-medium">{usage.days_remaining} days</span>
              </div>
              <div className="flex justify-between rounded-lg bg-muted/50 p-3">
                <span className="text-sm text-muted-foreground">Daily average</span>
                <span className="font-medium">{usage.daily_average.toFixed(1)} tickets</span>
              </div>
              <div className="flex justify-between rounded-lg bg-muted/50 p-3">
                <span className="text-sm text-muted-foreground">Peak day</span>
                <span className="font-medium">
                  {usage.peak_day ? `${usage.peak_day} (${usage.peak_day_count} tickets)` : 'No activity yet'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Usage History</CardTitle>
          <CardDescription>Daily ticket usage for the current billing period</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={usage.history}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" className="text-xs" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                <YAxis className="text-xs" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="tickets"
                  stroke="url(#usageLineGradient)"
                  strokeWidth={2}
                  dot={{ fill: '#3B82F6', strokeWidth: 2, r: 3 }}
                  activeDot={{ r: 5, fill: '#8B5CF6' }}
                />
                <defs>
                  <linearGradient id="usageLineGradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#3B82F6" />
                    <stop offset="100%" stopColor="#8B5CF6" />
                  </linearGradient>
                </defs>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage by Category</CardTitle>
          <CardDescription>Breakdown of tickets by complaint category</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Tickets</TableHead>
                <TableHead>Percentage</TableHead>
                <TableHead className="w-[300px]">Distribution</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {usage.category_breakdown.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No usage data available for this billing period yet.
                  </TableCell>
                </TableRow>
              ) : (
                usage.category_breakdown.map((category) => {
                  const percentage = usage.current_usage > 0 ? (category.tickets / usage.current_usage) * 100 : 0
                  return (
                    <TableRow key={category.category}>
                      <TableCell className="font-medium">{category.category}</TableCell>
                      <TableCell>{category.tickets}</TableCell>
                      <TableCell>{percentage.toFixed(1)}%</TableCell>
                      <TableCell>
                        <Progress value={percentage} className="h-2" />
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {usage.overage > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Overage Charges</CardTitle>
            <CardDescription>Additional charges for exceeding your plan limit this period</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Billing Period</TableHead>
                  <TableHead>Overage Tickets</TableHead>
                  <TableHead>Rate</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>
                    {new Date(usage.period_start).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })} - {' '}
                    {new Date(usage.period_end).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                  </TableCell>
                  <TableCell>{usage.overage}</TableCell>
                  <TableCell>INR {usage.overage_rate}/ticket</TableCell>
                  <TableCell className="text-right font-medium">INR {usage.overage_cost.toLocaleString()}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}


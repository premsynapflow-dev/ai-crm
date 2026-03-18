"use client"

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
  ResponsiveContainer
} from 'recharts'
import { AlertTriangle, TrendingUp, ArrowUpRight } from 'lucide-react'
import { usageData, dailyUsage, usageByCategory } from '@/lib/sample-data'
import Link from 'next/link'

export function UsageContent() {
  const usagePercentage = (usageData.ticketsUsed / usageData.ticketsLimit) * 100
  const isNearLimit = usagePercentage > 80
  const willExceed = usageData.projectedUsage > usageData.ticketsLimit

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Usage & Limits</h1>
        <p className="text-muted-foreground mt-1">Monitor your ticket usage and plan limits</p>
      </div>

      {/* Warning Banner */}
      {isNearLimit && (
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-orange-100 rounded-full">
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

      {/* Current Usage Card */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Current Usage</CardTitle>
            <CardDescription>Your ticket usage this billing period</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            {/* Circular Progress */}
            <div className="relative w-48 h-48">
              <svg className="w-48 h-48 transform -rotate-90">
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
                <span className="text-4xl font-bold">{usageData.ticketsUsed}</span>
                <span className="text-muted-foreground">of {usageData.ticketsLimit}</span>
                <span className="text-sm text-muted-foreground">tickets</span>
              </div>
            </div>

            <div className="w-full mt-6 space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Usage</span>
                <span className="font-medium">{usagePercentage.toFixed(1)}%</span>
              </div>
              <Progress value={usagePercentage} className="h-3" />
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Remaining</span>
                <span className="font-medium">{usageData.ticketsLimit - usageData.ticketsUsed} tickets</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Forecast Card */}
        <Card>
          <CardHeader>
            <CardTitle>Usage Forecast</CardTitle>
            <CardDescription>Projected usage based on current rate</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="p-6 bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl text-center">
              <p className="text-sm text-muted-foreground mb-2">Projected Monthly Usage</p>
              <p className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                ~{usageData.projectedUsage}
              </p>
              <p className="text-sm text-muted-foreground mt-2">tickets</p>
              {willExceed && (
                <Badge className="mt-4 bg-orange-100 text-orange-700">
                  <TrendingUp className="h-3 w-3 mr-1" />
                  {usageData.projectedUsage - usageData.ticketsLimit} over limit
                </Badge>
              )}
            </div>

            {willExceed && (
              <div className="p-4 border border-orange-200 bg-orange-50 rounded-lg">
                <p className="text-sm text-orange-800">
                  <strong>Heads up!</strong> At your current rate, you&apos;ll use approximately {usageData.projectedUsage} tickets this month, 
                  which is {usageData.projectedUsage - usageData.ticketsLimit} tickets over your limit.
                </p>
                <Button asChild variant="link" className="text-orange-700 p-0 mt-2 h-auto">
                  <Link href="/pricing">
                    Upgrade to avoid overage charges
                    <ArrowUpRight className="h-4 w-4 ml-1" />
                  </Link>
                </Button>
              </div>
            )}

            <div className="space-y-3">
              <div className="flex justify-between p-3 bg-muted/50 rounded-lg">
                <span className="text-sm text-muted-foreground">Days remaining</span>
                <span className="font-medium">12 days</span>
              </div>
              <div className="flex justify-between p-3 bg-muted/50 rounded-lg">
                <span className="text-sm text-muted-foreground">Daily average</span>
                <span className="font-medium">25 tickets</span>
              </div>
              <div className="flex justify-between p-3 bg-muted/50 rounded-lg">
                <span className="text-sm text-muted-foreground">Peak day</span>
                <span className="font-medium">42 tickets (Mar 12)</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Usage History Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Usage History</CardTitle>
          <CardDescription>Daily ticket usage for the current month</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dailyUsage}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" className="text-xs" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                <YAxis className="text-xs" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px'
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

      {/* Usage by Category */}
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
              {usageByCategory.map((cat) => {
                const percentage = (cat.tickets / usageData.ticketsUsed) * 100
                return (
                  <TableRow key={cat.category}>
                    <TableCell className="font-medium">{cat.category}</TableCell>
                    <TableCell>{cat.tickets}</TableCell>
                    <TableCell>{percentage.toFixed(1)}%</TableCell>
                    <TableCell>
                      <Progress value={percentage} className="h-2" />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Overage Charges */}
      {usageData.overageCharges > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Overage Charges</CardTitle>
            <CardDescription>Additional charges for exceeding your plan limit</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Overage Tickets</TableHead>
                  <TableHead>Rate</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>Mar 15, 2026</TableCell>
                  <TableCell>12</TableCell>
                  <TableCell>₹2/ticket</TableCell>
                  <TableCell className="text-right font-medium">₹24</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Mar 18, 2026</TableCell>
                  <TableCell>8</TableCell>
                  <TableCell>₹2/ticket</TableCell>
                  <TableCell className="text-right font-medium">₹16</TableCell>
                </TableRow>
                <TableRow className="bg-muted/50">
                  <TableCell colSpan={3} className="font-medium">Total Overage Charges</TableCell>
                  <TableCell className="text-right font-bold">₹40</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

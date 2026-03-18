"use client"

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import {
  TrendingUp,
  TrendingDown,
  Users,
  CheckCircle2,
  Clock,
  Target,
  Brain
} from 'lucide-react'
import {
  complaintVolumeTrend,
  topCategories,
  resolutionStatus,
  responseTimeTrend,
  complaintsByHour,
  topSources
} from '@/lib/sample-data'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  change?: number
  icon: React.ElementType
  trend?: 'up' | 'down'
  comparison?: string
}

function StatCard({ title, value, change, icon: Icon, trend, comparison }: StatCardProps) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold mt-2">{value}</p>
            {change !== undefined && (
              <div className="flex items-center gap-1 mt-2">
                {trend === 'up' ? (
                  <TrendingUp className="h-4 w-4 text-green-600" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-600" />
                )}
                <span className={cn(
                  "text-sm font-medium",
                  trend === 'up' ? "text-green-600" : "text-red-600"
                )}>
                  {change}%
                </span>
                <span className="text-sm text-muted-foreground">{comparison || 'vs last period'}</span>
              </div>
            )}
          </div>
          <div className="p-3 bg-gradient-to-br from-blue-100 to-purple-100 rounded-xl">
            <Icon className="h-6 w-6 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

type DateRange = '7d' | '30d' | '90d' | 'custom'

export function AnalyticsContent() {
  const [dateRange, setDateRange] = useState<DateRange>('30d')

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Analytics</h1>
          <p className="text-muted-foreground mt-1">Gain insights from your complaint data</p>
        </div>

        {/* Date Range Selector */}
        <div className="flex gap-2">
          {[
            { value: '7d', label: 'Last 7 Days' },
            { value: '30d', label: 'Last 30 Days' },
            { value: '90d', label: 'Last 90 Days' },
            { value: 'custom', label: 'Custom' }
          ].map((range) => (
            <Button
              key={range.value}
              variant={dateRange === range.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => setDateRange(range.value as DateRange)}
              className={dateRange === range.value ? 'bg-gradient-to-r from-blue-600 to-purple-600' : ''}
            >
              {range.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Complaints"
          value="1,247"
          change={12}
          trend="up"
          icon={Users}
        />
        <StatCard
          title="Resolution Rate"
          value="87.5%"
          change={5}
          trend="up"
          icon={CheckCircle2}
        />
        <StatCard
          title="Avg First Response"
          value="32min"
          change={8}
          trend="down"
          icon={Clock}
        />
        <StatCard
          title="Customer Satisfaction"
          value="4.2/5"
          change={3}
          trend="up"
          icon={Target}
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Area Chart - Complaint Volume */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Complaint Volume Trend</CardTitle>
            <CardDescription>Daily complaint volume over the selected period</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={complaintVolumeTrend}>
                  <defs>
                    <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
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
                  <Area
                    type="monotone"
                    dataKey="complaints"
                    stroke="url(#lineGradient2)"
                    strokeWidth={2}
                    fill="url(#areaGradient)"
                  />
                  <defs>
                    <linearGradient id="lineGradient2" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#3B82F6" />
                      <stop offset="100%" stopColor="#8B5CF6" />
                    </linearGradient>
                  </defs>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Bar Chart - Top Categories */}
        <Card>
          <CardHeader>
            <CardTitle>Top 5 Categories</CardTitle>
            <CardDescription>Most frequent complaint categories</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topCategories} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
                  <XAxis type="number" className="text-xs" />
                  <YAxis dataKey="category" type="category" className="text-xs" width={80} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="count" fill="url(#barGradient)" radius={[0, 4, 4, 0]} />
                  <defs>
                    <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#3B82F6" />
                      <stop offset="100%" stopColor="#8B5CF6" />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Donut Chart - Resolution Status */}
        <Card>
          <CardHeader>
            <CardTitle>Resolution Status</CardTitle>
            <CardDescription>Current status distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={resolutionStatus}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {resolutionStatus.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Line Chart - Response Time */}
        <Card>
          <CardHeader>
            <CardTitle>Response Time Trend</CardTitle>
            <CardDescription>Average response time by day</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={responseTimeTrend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="day" className="text-xs" />
                  <YAxis className="text-xs" unit="min" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                    formatter={(value) => [`${value} min`, 'Response Time']}
                  />
                  <Line
                    type="monotone"
                    dataKey="time"
                    stroke="#8B5CF6"
                    strokeWidth={2}
                    dot={{ fill: '#8B5CF6', strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 3 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Heat Map Alternative - Complaints by Hour */}
        <Card>
          <CardHeader>
            <CardTitle>Complaints by Hour</CardTitle>
            <CardDescription>When complaints are typically received</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={complaintsByHour}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="hour" className="text-xs" tick={{ fontSize: 10 }} interval={2} />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="count" fill="#3B82F6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Bar Chart - Top Sources */}
        <Card>
          <CardHeader>
            <CardTitle>Top Complaint Sources</CardTitle>
            <CardDescription>Where complaints are coming from</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topSources}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="source" className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="count" fill="url(#barGradient2)" radius={[4, 4, 0, 0]} />
                  <defs>
                    <linearGradient id="barGradient2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8B5CF6" />
                      <stop offset="100%" stopColor="#3B82F6" />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* AI Performance Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <CardTitle>AI Performance</CardTitle>
          </div>
          <CardDescription>How well is the AI performing on complaint classification</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="text-center p-6 bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl">
              <p className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                94.5%
              </p>
              <p className="text-sm text-muted-foreground mt-2">Classification Accuracy</p>
              <Badge className="mt-3 bg-green-100 text-green-700">
                <TrendingUp className="h-3 w-3 mr-1" />
                +2.3% vs last month
              </Badge>
            </div>
            <div className="text-center p-6 bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl">
              <p className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                67%
              </p>
              <p className="text-sm text-muted-foreground mt-2">Auto-resolution Rate</p>
              <Badge className="mt-3 bg-green-100 text-green-700">
                <TrendingUp className="h-3 w-3 mr-1" />
                +5.1% vs last month
              </Badge>
            </div>
            <div className="text-center p-6 bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl">
              <p className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                89%
              </p>
              <p className="text-sm text-muted-foreground mt-2">Avg AI Confidence</p>
              <Badge className="mt-3 bg-green-100 text-green-700">
                <TrendingUp className="h-3 w-3 mr-1" />
                +1.8% vs last month
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

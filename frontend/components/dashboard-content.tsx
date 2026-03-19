"use client"

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import {
  TrendingUp,
  TrendingDown,
  Users,
  CheckCircle2,
  Clock,
  Star,
  Eye,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ComplaintDetailModal } from '@/components/complaint-detail-modal'
import { analyticsAPI, type AnalyticsOverview } from '@/lib/api/analytics'
import { complaintsAPI, type Complaint } from '@/lib/api/complaints'

const priorityColors: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

const sentimentColors: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-700',
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-purple-100 text-purple-700',
  resolved: 'bg-green-100 text-green-700',
  escalated: 'bg-red-100 text-red-700',
}

const sentimentChartColors: Record<string, string> = {
  positive: 'var(--chart-3)',
  neutral: 'var(--chart-4)',
  negative: 'var(--chart-5)',
}

const priorityChartColors: Record<string, string> = {
  low: 'var(--chart-3)',
  medium: 'var(--chart-4)',
  high: 'var(--chart-1)',
  critical: 'var(--chart-5)',
}

interface StatCardProps {
  title: string
  value: string | number
  change?: number
  icon: React.ElementType
  trend?: 'up' | 'down'
}

function StatCard({ title, value, change, icon: Icon, trend }: StatCardProps) {
  return (
    <Card className="transition-shadow hover:shadow-lg">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="mt-2 text-3xl font-bold">{value}</p>
            {change !== undefined && (
              <div className="mt-2 flex items-center gap-1">
                {trend === 'up' ? (
                  <TrendingUp className="h-4 w-4 text-green-600" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-600" />
                )}
                <span className={cn('text-sm font-medium', trend === 'up' ? 'text-green-600' : 'text-red-600')}>
                  {Math.abs(change)}%
                </span>
                <span className="text-sm text-muted-foreground">vs previous window</span>
              </div>
            )}
          </div>
          <div className="rounded-xl bg-gradient-to-br from-blue-100 to-purple-100 p-3">
            <Icon className="h-6 w-6 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardContent() {
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null)
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true

    async function loadDashboard() {
      try {
        const [overview, complaintsResponse] = await Promise.all([
          analyticsAPI.getOverview(7),
          complaintsAPI.list({ page: 1, pageSize: 10 }),
        ])

        if (!active) {
          return
        }

        setAnalytics(overview)
        setComplaints(complaintsResponse.items)
      } catch {
        if (active) {
          setAnalytics(null)
          setComplaints([])
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadDashboard()

    return () => {
      active = false
    }
  }, [])

  const handleViewDetails = (complaint: Complaint) => {
    setSelectedComplaint(complaint)
    setModalOpen(true)
  }

  const handleComplaintUpdated = (updatedComplaint: Complaint) => {
    setComplaints((current) => current.map((item) => (item.id === updatedComplaint.id ? updatedComplaint : item)))
    setSelectedComplaint(updatedComplaint)
  }

  const trendChange = analytics?.trend?.previous
    ? Math.round(((analytics.trend.current - analytics.trend.previous) / analytics.trend.previous) * 100)
    : 0
  const trendDirection = analytics?.trend?.direction === 'down' ? 'down' : 'up'
  const volumeTrend = analytics?.volume_trend.map((item) => ({ date: item.date, complaints: item.count })) ?? []
  const sentimentDistribution = analytics?.sentiment_distribution.map((item) => ({
    name: item.sentiment,
    value: item.count,
    fill: sentimentChartColors[item.sentiment] ?? 'var(--chart-4)',
  })) ?? []
  const priorityBreakdown = analytics?.priority_breakdown.map((item) => ({
    priority: item.priority,
    count: item.count,
    fill: priorityChartColors[item.priority] ?? 'var(--chart-1)',
  })) ?? []

  if (isLoading) {
    return <div className="flex h-96 items-center justify-center">Loading dashboard...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">Welcome back! Here&apos;s what&apos;s happening with your complaints.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Complaints"
          value={(analytics?.total_complaints ?? 0).toLocaleString()}
          change={trendChange}
          trend={trendDirection}
          icon={Users}
        />
        <StatCard
          title="Resolved Today"
          value={analytics?.resolved_today ?? 0}
          icon={CheckCircle2}
          trend="up"
        />
        <StatCard
          title="Avg Response Time"
          value={`${Math.round(analytics?.avg_response_time ?? 0)}s`}
          icon={Clock}
          trend="down"
        />
        <StatCard
          title="Customer Satisfaction"
          value={`${(analytics?.customer_satisfaction ?? 0).toFixed(1)}/5`}
          icon={Star}
          trend="up"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Complaints Over Time</CardTitle>
            <CardDescription>Daily complaint volume for the last 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={volumeTrend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" className="text-xs" />
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
                    dataKey="complaints"
                    stroke="url(#lineGradient)"
                    strokeWidth={3}
                    dot={{ fill: '#3B82F6', strokeWidth: 2 }}
                    activeDot={{ r: 6, fill: '#8B5CF6' }}
                  />
                  <defs>
                    <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
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
            <CardTitle>Sentiment Distribution</CardTitle>
            <CardDescription>Customer sentiment breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sentimentDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {sentimentDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Priority Breakdown</CardTitle>
          <CardDescription>Complaints grouped by priority level</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priorityBreakdown} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
                <XAxis type="number" className="text-xs" />
                <YAxis dataKey="priority" type="category" className="text-xs" width={80} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {priorityBreakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Complaints</CardTitle>
          <CardDescription>Latest complaints from your customers</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Sentiment</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {complaints.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                      No complaints found yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  complaints.map((complaint) => (
                    <TableRow key={complaint.id} className="hover:bg-muted/50">
                      <TableCell className="font-mono text-sm">{complaint.id}</TableCell>
                      <TableCell className="font-medium">{complaint.customerName}</TableCell>
                      <TableCell className="max-w-[200px] truncate">{complaint.subject}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {complaint.category}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', priorityColors[complaint.priority])}>
                          {complaint.priority}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', sentimentColors[complaint.sentiment])}>
                          {complaint.sentiment}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', statusColors[complaint.status])}>
                          {complaint.status.replace('-', ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(complaint.createdAt).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewDetails(complaint)}
                          className="text-primary hover:text-primary"
                        >
                          <Eye className="mr-1 h-4 w-4" />
                          View
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

      <ComplaintDetailModal
        complaint={selectedComplaint}
        open={modalOpen}
        onOpenChange={setModalOpen}
        onComplaintUpdated={handleComplaintUpdated}
      />
    </div>
  )
}


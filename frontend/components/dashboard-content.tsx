"use client"

import { useState, useEffect } from 'react'
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
  Legend
} from 'recharts'
import {
  TrendingUp,
  TrendingDown,
  Users,
  CheckCircle2,
  Clock,
  Star,
  Eye
} from 'lucide-react'
import {
  complaintsOverTime,
  sentimentDistribution,
  priorityBreakdown
} from '@/lib/sample-data'
import { cn } from '@/lib/utils'
import { ComplaintDetailModal } from '@/components/complaint-detail-modal'
import { analyticsAPI } from '@/lib/api/analytics'
import { complaintsAPI, type Complaint } from '@/lib/api/complaints'

const priorityColors: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700'
}

const sentimentColors: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-700'
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-purple-100 text-purple-700',
  resolved: 'bg-green-100 text-green-700',
  escalated: 'bg-red-100 text-red-700'
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
                <span className="text-sm text-muted-foreground">vs last week</span>
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

export function DashboardContent() {
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [analytics, setAnalytics] = useState<{
    total_complaints: number
    resolved_today: number
    avg_response_time: number
    customer_satisfaction: number
    trend?: {
      direction: 'up' | 'down' | 'flat'
      current: number
      previous: number
    }
  } | null>(null)
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    let active = true

    async function loadDashboard() {
      try {
        const [overview, recentComplaints] = await Promise.all([
          analyticsAPI.getOverview(),
          complaintsAPI.getAll({ page: 1, pageSize: 10 }),
        ])

        if (!active) {
          return
        }

        setAnalytics(overview)
        setComplaints(recentComplaints)
      } catch {
        if (active) {
          setComplaints([])
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

  const trendChange = analytics?.trend?.previous
    ? Math.round(((analytics.trend.current - analytics.trend.previous) / analytics.trend.previous) * 100)
    : 0
  const trendDirection = analytics?.trend?.direction === 'down' ? 'down' : 'up'

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Welcome back! Here&apos;s what&apos;s happening with your complaints.</p>
      </div>

      {/* Stats Grid */}
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
          trend="up"
          icon={CheckCircle2}
        />
        <StatCard
          title="Avg Response Time"
          value={`${Math.round(analytics?.avg_response_time ?? 0)}s`}
          trend="down"
          icon={Clock}
        />
        <StatCard
          title="Customer Satisfaction"
          value={`${(analytics?.customer_satisfaction ?? 0).toFixed(1)}/5`}
          trend="up"
          icon={Star}
        />
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Line Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Complaints Over Time</CardTitle>
            <CardDescription>Daily complaint volume for the last 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={complaintsOverTime}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" className="text-xs" />
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

        {/* Pie Chart */}
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
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bar Chart */}
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
                    borderRadius: '8px'
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

      {/* Recent Complaints Table */}
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
                {complaints.map((complaint) => (
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
                      <Badge className={cn("capitalize", priorityColors[complaint.priority])}>
                        {complaint.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("capitalize", sentimentColors[complaint.sentiment])}>
                        {complaint.sentiment === 'positive' ? '😊' : complaint.sentiment === 'negative' ? '😠' : '😐'}{' '}
                        {complaint.sentiment}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("capitalize", statusColors[complaint.status])}>
                        {complaint.status.replace('-', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(complaint.createdAt).toLocaleDateString('en-IN', {
                        day: 'numeric',
                        month: 'short'
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewDetails(complaint)}
                        className="text-primary hover:text-primary"
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Complaint Detail Modal */}
      <ComplaintDetailModal
        complaint={selectedComplaint}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  )
}

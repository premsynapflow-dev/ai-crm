"use client"

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
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
  ArrowUpRight,
  CheckCircle2,
  Eye,
  Flame,
  FolderKanban,
  Loader2,
  MessageSquareWarning,
  Ticket,
  Users,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ComplaintDetailModal } from '@/components/complaint-detail-modal'
import { UpgradePrompt } from '@/components/upgrade-prompt'
import { DashboardSkeleton } from '@/components/ui/skeletons'
import { useAuth } from '@/lib/auth-context'
import { getFeatureGateDetail } from '@/lib/api-error'
import {
  analyticsAPI,
  type AnalyticsOverview,
  type ChurnRiskCustomer,
  type RootCauseAnalysisResponse,
  type SentimentDistributionResponse,
} from '@/lib/api/analytics'
import {
  assignmentDashboardAPI,
  type AssignmentTeam,
  type AssignmentTeamMember,
  type AssignmentTicket,
} from '@/lib/api/assignment-dashboard'
import { complaintsAPI, type Complaint } from '@/lib/api/complaints'
import { planIncludesFeature } from '@/lib/plan-features'
import { cn } from '@/lib/utils'

const priorityColors: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-rose-100 text-rose-700',
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-violet-100 text-violet-700',
  resolved: 'bg-emerald-100 text-emerald-700',
  escalated: 'bg-rose-100 text-rose-700',
}

const sentimentBadgeColors: Record<string, string> = {
  positive: 'bg-emerald-100 text-emerald-700',
  neutral: 'bg-slate-100 text-slate-700',
  negative: 'bg-rose-100 text-rose-700',
}

const sentimentScaleColors = ['#CDECCF', '#8EE0A1', '#F9D768', '#F9A45D', '#F36C5D']

interface DashboardStatCardProps {
  title: string
  value: string
  subtitle: string
  icon: React.ElementType
}

function DashboardStatCard({ title, value, subtitle, icon: Icon }: DashboardStatCardProps) {
  return (
    <Card className="overflow-hidden border-white/70 bg-white/80 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.55)] backdrop-blur">
      <CardContent className="relative p-6">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-sky-500 via-cyan-400 to-emerald-400" />
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
            <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <div className="rounded-2xl bg-slate-900 p-3 text-white shadow-lg shadow-slate-300/40">
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function formatDurationSeconds(value: number) {
  if (value < 60) {
    return `${Math.round(value)} sec`
  }
  return `${Math.round(value / 60)} min`
}

export function DashboardContent() {
  const { user } = useAuth()
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null)
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [sentimentDistribution, setSentimentDistribution] = useState<SentimentDistributionResponse | null>(null)
  const [churnRiskCustomers, setChurnRiskCustomers] = useState<ChurnRiskCustomer[]>([])
  const [rootCause, setRootCause] = useState<RootCauseAnalysisResponse | null>(null)
  const [assignmentTeams, setAssignmentTeams] = useState<AssignmentTeam[]>([])
  const [assignmentTickets, setAssignmentTickets] = useState<AssignmentTicket[]>([])
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [reassigningComplaintId, setReassigningComplaintId] = useState<string | null>(null)
  const [sentimentLocked, setSentimentLocked] = useState(false)
  const [churnLocked, setChurnLocked] = useState(false)
  const [rootCauseLocked, setRootCauseLocked] = useState(false)

  useEffect(() => {
    let active = true

    async function loadDashboard() {
      setIsLoading(true)
      try {
        const hasSentiment = planIncludesFeature(user?.plan_id, 'sentiment_analysis')
        const hasChurnRisk = planIncludesFeature(user?.plan_id, 'churn_risk_scoring')
        const hasRootCause = planIncludesFeature(user?.plan_id, 'root_cause_analysis')
        const overviewPromise = analyticsAPI.getOverview(30)
        const complaintsPromise = complaintsAPI.list({ page: 1, pageSize: 8 })
        const assignmentsPromise = assignmentDashboardAPI.getAssignments()
        const sentimentPromise = hasSentiment
          ? analyticsAPI.getSentimentDistribution()
          : Promise.resolve(null)
        const churnPromise = hasChurnRisk
          ? analyticsAPI.getChurnRisk()
          : Promise.resolve([])
        const rootCausePromise = hasRootCause
          ? analyticsAPI.getRootCauseAnalysis(30)
          : Promise.resolve(null)

        const [overviewResult, complaintsResult, assignmentsResult, sentimentResult, churnResult, rootCauseResult] = await Promise.allSettled([
          overviewPromise,
          complaintsPromise,
          assignmentsPromise,
          sentimentPromise,
          churnPromise,
          rootCausePromise,
        ])

        if (!active) {
          return
        }

        setAnalytics(overviewResult.status === 'fulfilled' ? overviewResult.value : null)
        setComplaints(complaintsResult.status === 'fulfilled' ? complaintsResult.value.items : [])
        if (assignmentsResult.status === 'fulfilled') {
          setAssignmentTeams(assignmentsResult.value.teams)
          setAssignmentTickets(assignmentsResult.value.tickets)
        } else {
          setAssignmentTeams([])
          setAssignmentTickets([])
        }

        if (sentimentResult.status === 'fulfilled') {
          setSentimentDistribution(sentimentResult.value)
          setSentimentLocked(!hasSentiment)
        } else {
          setSentimentDistribution(null)
          setSentimentLocked(Boolean(getFeatureGateDetail(sentimentResult.reason)))
        }

        if (churnResult.status === 'fulfilled') {
          setChurnRiskCustomers(churnResult.value)
          setChurnLocked(!hasChurnRisk)
        } else {
          setChurnRiskCustomers([])
          setChurnLocked(Boolean(getFeatureGateDetail(churnResult.reason)))
        }

        if (rootCauseResult.status === 'fulfilled') {
          setRootCause(rootCauseResult.value)
          setRootCauseLocked(!hasRootCause)
        } else {
          setRootCause(null)
          setRootCauseLocked(Boolean(getFeatureGateDetail(rootCauseResult.reason)))
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
  }, [user?.plan_id])

  const handleViewDetails = (complaint: Complaint) => {
    setSelectedComplaint(complaint)
    setModalOpen(true)
  }

  const handleComplaintUpdated = (updatedComplaint: Complaint) => {
    setComplaints((current) => current.map((item) => (item.id === updatedComplaint.id ? updatedComplaint : item)))
    setSelectedComplaint(updatedComplaint)
  }

  const teamMembersByUserId = useMemo(() => {
    const map = new Map<string, { team: AssignmentTeam; member: AssignmentTeamMember }>()
    assignmentTeams.forEach((team) => {
      team.members.forEach((member) => {
        if (!member.isActive) {
          return
        }
        if (!map.has(member.userId)) {
          map.set(member.userId, { team, member })
        }
      })
    })
    return map
  }, [assignmentTeams])

  const assignableUsers = useMemo(() => Array.from(teamMembersByUserId.values()), [teamMembersByUserId])

  const assignmentByTicketId = useMemo(() => {
    const map = new Map<string, AssignmentTicket>()
    assignmentTickets.forEach((ticket) => {
      if (ticket.ticketId) {
        map.set(ticket.ticketId, ticket)
      }
      map.set(ticket.id, ticket)
    })
    return map
  }, [assignmentTickets])

  const handleAssignComplaint = async (complaint: Complaint, userId: string) => {
    const ticket = assignmentByTicketId.get(complaint.ticketId ?? complaint.id)
    const ticketId = ticket?.id ?? complaint.ticketId ?? complaint.id
    const selection = teamMembersByUserId.get(userId)
    if (!ticketId || !selection) {
      return
    }

    setReassigningComplaintId(complaint.id)
    try {
      const updatedTicket = await assignmentDashboardAPI.reassignTicket(ticketId, userId)
      setAssignmentTickets((current) => {
        const index = current.findIndex((item) => item.id === updatedTicket.id)
        if (index === -1) {
          return [...current, updatedTicket]
        }
        return current.map((item) => (item.id === updatedTicket.id ? { ...item, ...updatedTicket } : item))
      })
      setComplaints((current) =>
        current.map((item) =>
          item.id === complaint.id
            ? { ...item, assignedTo: selection.member.name }
            : item,
        ),
      )
    } finally {
      setReassigningComplaintId(null)
    }
  }

  const trendChange = analytics?.trend.previous
    ? Math.round(((analytics.trend.current - analytics.trend.previous) / analytics.trend.previous) * 100)
    : 0
  const volumeTrend = analytics?.volume_trend.map((item) => ({ date: item.date, complaints: item.count })) ?? []
  const priorityBreakdown = analytics?.priority_breakdown.map((item) => ({
    priority: item.priority,
    count: item.count,
    fill:
      item.priority === 'critical'
        ? '#F36C5D'
        : item.priority === 'high'
          ? '#F9A45D'
          : item.priority === 'medium'
            ? '#F9D768'
            : '#7DD3A7',
  })) ?? []
  const sentimentPieData = sentimentDistribution
    ? Object.entries(sentimentDistribution.distribution).map(([score, count], index) => ({
        name: sentimentDistribution.labels[score] ?? `Score ${score}`,
        value: count,
        fill: sentimentScaleColors[index] ?? '#CBD5E1',
      }))
    : []

  if (isLoading) {
    return <DashboardSkeleton />
  }

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-[28px] border border-white/60 bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.16),_transparent_34%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.18),_transparent_36%),linear-gradient(135deg,_rgba(255,255,255,0.96),_rgba(241,245,249,0.92))] p-6 shadow-[0_35px_100px_-55px_rgba(15,23,42,0.65)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <Badge className="w-fit bg-slate-900 text-white hover:bg-slate-900">
              SynapFlow Command Center
            </Badge>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Complaint operations at a glance</h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-600">
                Track complaint volume, lead intent, resolution flow, and high-risk signals from one live dashboard.
              </p>
            </div>
          </div>
          <div className="rounded-3xl border border-slate-200/80 bg-white/80 px-4 py-3 text-sm shadow-sm">
            <p className="text-slate-500">Complaint trend</p>
            <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-slate-900">
              {trendChange >= 0 ? '+' : ''}
              {trendChange}%
              <ArrowUpRight className={cn('h-4 w-4', trendChange < 0 && 'rotate-90 text-rose-500')} />
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DashboardStatCard
          title="Total Complaints"
          value={(analytics?.total_complaints ?? 0).toLocaleString()}
          subtitle="All complaints processed across channels"
          icon={MessageSquareWarning}
        />
        <DashboardStatCard
          title="Total Leads"
          value={(analytics?.total_leads ?? 0).toLocaleString()}
          subtitle="Complaints classified as sales opportunities"
          icon={Users}
        />
        <DashboardStatCard
          title="Open Tickets"
          value={(analytics?.open_tickets ?? 0).toLocaleString()}
          subtitle="Tickets still awaiting full resolution"
          icon={Ticket}
        />
        <DashboardStatCard
          title="Resolved"
          value={(analytics?.resolved_tickets ?? 0).toLocaleString()}
          subtitle={`Avg. first response ${formatDurationSeconds(analytics?.avg_response_time ?? 0)}`}
          icon={CheckCircle2}
        />
      </section>

      <section>
        <Card className="overflow-hidden border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
          <CardHeader className="border-b bg-slate-50/70">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <CardTitle>Recent complaints</CardTitle>
                <CardDescription>Fresh complaints from the inbox, pulled directly from the complaints API.</CardDescription>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link href="/assignments">Open assignment board</Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Sentiment</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Assigned</TableHead>
                    <TableHead className="w-[190px]">Assign</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {complaints.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={10} className="h-28 text-center text-muted-foreground">
                        No complaints found yet.
                      </TableCell>
                    </TableRow>
                  ) : (
                    complaints.map((complaint) => (
                      <TableRow key={complaint.id}>
                        <TableCell className="font-medium">{complaint.customerName}</TableCell>
                        <TableCell className="max-w-[220px] truncate">{complaint.subject}</TableCell>
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
                          <Badge className={cn('capitalize', statusColors[complaint.status])}>
                            {complaint.status.replace('-', ' ')}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={cn('capitalize', sentimentBadgeColors[complaint.sentiment])}>
                            {complaint.sentimentLabel ?? complaint.sentiment}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(complaint.createdAt).toLocaleDateString('en-IN', {
                            day: 'numeric',
                            month: 'short',
                          })}
                        </TableCell>
                        <TableCell>
                          {(() => {
                            const ticket = assignmentByTicketId.get(complaint.ticketId ?? complaint.id)
                            const assignedLabel = ticket?.assignedTo ?? complaint.assignedTo ?? 'Unassigned'
                            const assignedTeam = ticket?.teamName
                            return (
                              <div className="space-y-1">
                                <p className="text-sm font-medium text-slate-900">{assignedLabel}</p>
                                <p className="text-xs text-muted-foreground">{assignedTeam ?? 'No team'}</p>
                              </div>
                            )
                          })()}
                        </TableCell>
                        <TableCell>
                          <Select
                            value={assignmentByTicketId.get(complaint.ticketId ?? complaint.id)?.assignedUserId ?? undefined}
                            onValueChange={(value) => void handleAssignComplaint(complaint, value)}
                            disabled={assignableUsers.length === 0 || reassigningComplaintId === complaint.id}
                          >
                            <SelectTrigger className="w-full bg-white">
                              <SelectValue placeholder={assignableUsers.length === 0 ? 'No active team' : 'Pick teammate'} />
                            </SelectTrigger>
                            <SelectContent>
                              {assignableUsers.map(({ team, member }) => (
                                <SelectItem key={member.userId} value={member.userId}>
                                  {member.name} - {team.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" className="gap-2" onClick={() => handleViewDetails(complaint)}>
                            <Eye className="h-4 w-4" />
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
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <Card className="overflow-hidden border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
          <CardHeader className="border-b bg-slate-50/70">
            <CardTitle>Complaint volume trend</CardTitle>
            <CardDescription>Daily complaint flow over the last 30 days from the live analytics API.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={volumeTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 16,
                      border: '1px solid #E2E8F0',
                      backgroundColor: '#FFFFFF',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="complaints"
                    stroke="#0F172A"
                    strokeWidth={3}
                    dot={{ fill: '#22C55E', strokeWidth: 0, r: 4 }}
                    activeDot={{ r: 6, fill: '#0EA5E9' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="overflow-hidden border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
            <CardHeader className="border-b bg-slate-50/70">
              <CardTitle>Sentiment distribution</CardTitle>
              <CardDescription>1-5 emotion intensity split from Pro+ sentiment analysis.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {sentimentLocked ? (
                <UpgradePrompt
                  title="Unlock sentiment analysis"
                  description="Map complaints from calm to furious and spot emotional spikes earlier."
                  requiredPlan="Pro"
                />
              ) : (
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={sentimentPieData} innerRadius={60} outerRadius={92} dataKey="value" paddingAngle={3}>
                        {sentimentPieData.map((entry, index) => (
                          <Cell key={`${entry.name}-${index}`} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          borderRadius: 16,
                          border: '1px solid #E2E8F0',
                          backgroundColor: '#FFFFFF',
                        }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden border-white/70 bg-slate-950 text-white shadow-[0_25px_80px_-50px_rgba(15,23,42,0.7)]">
            <CardContent className="p-6">
              <p className="text-sm text-slate-300">Customer satisfaction</p>
              <p className="mt-2 text-4xl font-semibold">{(analytics?.customer_satisfaction ?? 0).toFixed(1)}/5</p>
              <p className="mt-2 text-sm text-slate-400">
                Driven by resolution outcomes and satisfaction scores on resolved complaints.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="overflow-hidden border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
          <CardHeader className="border-b bg-slate-50/70">
            <CardTitle>Priority breakdown</CardTitle>
            <CardDescription>See where urgent workload is building across low, medium, high, and critical tickets.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priorityBreakdown} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" horizontal={false} />
                  <XAxis type="number" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis dataKey="priority" type="category" tickLine={false} axisLine={false} fontSize={12} width={76} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 16,
                      border: '1px solid #E2E8F0',
                      backgroundColor: '#FFFFFF',
                    }}
                  />
                  <Bar dataKey="count" radius={[0, 12, 12, 0]}>
                    {priorityBreakdown.map((entry, index) => (
                      <Cell key={`${entry.priority}-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="overflow-hidden border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
            <CardHeader className="border-b bg-slate-50/70">
              <CardTitle className="flex items-center gap-2">
                <Flame className="h-5 w-5 text-rose-500" />
                High churn risk customers
              </CardTitle>
              <CardDescription>Max+ alerting for customers who may need proactive retention outreach.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-6">
              {churnLocked ? (
                <UpgradePrompt
                  title="Unlock churn risk scoring"
                  description="Spot customers with repeated unresolved complaints before they disappear."
                  requiredPlan="Max"
                  compact
                />
              ) : churnRiskCustomers.length === 0 ? (
                <div className="rounded-2xl border border-dashed bg-slate-50 p-5 text-sm text-muted-foreground">
                  No high-risk customers detected in the last 30 days.
                </div>
              ) : (
                churnRiskCustomers.slice(0, 3).map((customer) => (
                  <div key={customer.customer_email} className="rounded-2xl border bg-slate-50/80 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-slate-900">{customer.customer_email}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{customer.recommendation}</p>
                      </div>
                      <Badge className={customer.risk_level === 'critical' ? 'bg-rose-100 text-rose-700' : 'bg-orange-100 text-orange-700'}>
                        {customer.risk_level} risk
                      </Badge>
                    </div>
                    <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
                      <span>{customer.complaint_count} recent complaints</span>
                      <span>{customer.unresolved_count} unresolved</span>
                      <span>Avg sentiment {customer.avg_sentiment}</span>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
            <CardHeader className="border-b bg-slate-50/70">
              <CardTitle className="flex items-center gap-2">
                <FolderKanban className="h-5 w-5 text-emerald-600" />
                Root cause summary
              </CardTitle>
              <CardDescription>Top issue clusters and movement over the current reporting window.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              {rootCauseLocked ? (
                <UpgradePrompt
                  title="Unlock root cause analysis"
                  description="Identify the categories driving the biggest complaint spikes and operational drag."
                  requiredPlan="Max"
                  compact
                />
              ) : rootCause ? (
                <>
                  {rootCause.top_issues.slice(0, 3).map((issue) => (
                    <div key={issue.category} className="flex items-center justify-between rounded-2xl border bg-slate-50/80 px-4 py-3">
                      <div>
                        <p className="font-medium text-slate-900">{issue.category}</p>
                        <p className="text-xs text-muted-foreground">{issue.percentage_of_total}% of current complaints</p>
                      </div>
                      <Badge className={issue.change_percentage > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}>
                        {issue.change_percentage > 0 ? '+' : ''}
                        {issue.change_percentage}%
                      </Badge>
                    </div>
                  ))}
                  <div className="rounded-2xl bg-slate-950 p-4 text-sm text-slate-100">
                    {rootCause.insights[0] ?? 'No major issue spikes detected.'}
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed bg-slate-50 p-5 text-sm text-muted-foreground">
                  Root cause insights are not available yet.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <ComplaintDetailModal
        complaint={selectedComplaint}
        open={modalOpen}
        onOpenChange={setModalOpen}
        onComplaintUpdated={handleComplaintUpdated}
      />
    </div>
  )
}


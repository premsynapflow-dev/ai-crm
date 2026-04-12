"use client"

import { useEffect, useState } from 'react'
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
  Legend,
} from 'recharts'
import {
  TrendingUp,
  TrendingDown,
  Users,
  CheckCircle2,
  Clock,
  Target,
  Brain,
  Flame,
  ShieldAlert,
  Loader2,
} from 'lucide-react'
import { UpgradePrompt } from '@/components/upgrade-prompt'
import { useAuth } from '@/lib/auth-context'
import { getFeatureGateDetail } from '@/lib/api-error'
import {
  analyticsAPI,
  type AnalyticsOverview,
  type ChurnRiskCustomer,
  type RootCauseAnalysisResponse,
  type TeamPerformanceResponse,
} from '@/lib/api/analytics'
import { planIncludesFeature } from '@/lib/plan-features'
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
                <span className="text-sm text-muted-foreground">{comparison || 'vs previous period'}</span>
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

type DateRange = '7d' | '30d' | '90d'

const rangeToDays: Record<DateRange, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
}

const statusColors: Record<string, string> = {
  resolved: 'var(--chart-3)',
  'in-progress': 'var(--chart-1)',
  escalated: 'var(--chart-5)',
  new: 'var(--chart-4)',
}

export function AnalyticsContent() {
  const { user } = useAuth()
  const [dateRange, setDateRange] = useState<DateRange>('30d')
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null)
  const [rootCause, setRootCause] = useState<RootCauseAnalysisResponse | null>(null)
  const [teamPerformance, setTeamPerformance] = useState<TeamPerformanceResponse | null>(null)
  const [churnRiskCustomers, setChurnRiskCustomers] = useState<ChurnRiskCustomer[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [rootCauseLocked, setRootCauseLocked] = useState(false)
  const [teamLocked, setTeamLocked] = useState(false)
  const [churnLocked, setChurnLocked] = useState(false)

  useEffect(() => {
    let active = true

    async function loadAnalytics() {
      setIsLoading(true)
      try {
        const hasRootCause = planIncludesFeature(user?.plan_id, 'root_cause_analysis')
        const hasTeamPerformance = planIncludesFeature(user?.plan_id, 'team_performance')
        const hasChurnRisk = planIncludesFeature(user?.plan_id, 'churn_risk_scoring')

        const [overviewResult, rootCauseResult, teamResult, churnResult] = await Promise.allSettled([
          analyticsAPI.getOverview(rangeToDays[dateRange]),
          hasRootCause ? analyticsAPI.getRootCauseAnalysis(rangeToDays[dateRange]) : Promise.resolve(null),
          hasTeamPerformance ? analyticsAPI.getTeamPerformance(rangeToDays[dateRange]) : Promise.resolve(null),
          hasChurnRisk ? analyticsAPI.getChurnRisk() : Promise.resolve([]),
        ])

        if (active) {
          setAnalytics(overviewResult.status === 'fulfilled' ? overviewResult.value : null)

          if (rootCauseResult.status === 'fulfilled') {
            setRootCause(rootCauseResult.value)
            setRootCauseLocked(!hasRootCause)
          } else {
            setRootCause(null)
            setRootCauseLocked(Boolean(getFeatureGateDetail(rootCauseResult.reason)))
          }

          if (teamResult.status === 'fulfilled') {
            setTeamPerformance(teamResult.value)
            setTeamLocked(!hasTeamPerformance)
          } else {
            setTeamPerformance(null)
            setTeamLocked(Boolean(getFeatureGateDetail(teamResult.reason)))
          }

          if (churnResult.status === 'fulfilled') {
            setChurnRiskCustomers(churnResult.value)
            setChurnLocked(!hasChurnRisk)
          } else {
            setChurnRiskCustomers([])
            setChurnLocked(Boolean(getFeatureGateDetail(churnResult.reason)))
          }
        }
      } catch {
        if (active) {
          setAnalytics(null)
          setRootCause(null)
          setTeamPerformance(null)
          setChurnRiskCustomers([])
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadAnalytics()

    return () => {
      active = false
    }
  }, [dateRange, user?.plan_id])

  const volumeTrend = analytics?.volume_trend.map((item) => ({ date: item.date, complaints: item.count })) ?? []
  const topCategories = (analytics?.category_breakdown ?? []).slice(0, 5)
  const resolutionStatus = analytics?.status_distribution.map((item) => ({
    name: item.status,
    value: item.count,
    fill: statusColors[item.status] ?? 'var(--chart-4)',
  })) ?? []
  const responseTimeTrend = analytics?.response_time_trend.map((item) => ({
    day: item.date,
    time: item.average_minutes,
  })) ?? []
  const complaintsByHour = analytics?.complaints_by_hour ?? []
  const topSources = analytics?.sources ?? []
  const trendChange = analytics?.trend?.previous
    ? Math.round(((analytics.trend.current - analytics.trend.previous) / analytics.trend.previous) * 100)
    : 0
  const trendDirection = analytics?.trend?.direction === 'down' ? 'down' : 'up'
  const averageResponseMinutes = Math.round((analytics?.avg_response_time ?? 0) / 60)
  const autoResolutionRate = ((analytics?.ai_resolution.ai_resolution_rate ?? 0) * 100).toFixed(1)
  const escalationRate = ((analytics?.escalation.escalation_rate ?? 0) * 100).toFixed(1)
  const teamPerformanceData = teamPerformance?.team_performance ?? []
  const topRiskCustomers = churnRiskCustomers.slice(0, 5)
  const churnRiskBreakdown = [
    { level: 'High', count: churnRiskCustomers.filter((item) => item.risk_level === 'high').length, fill: '#F9A45D' },
    { level: 'Critical', count: churnRiskCustomers.filter((item) => item.risk_level === 'critical').length, fill: '#F36C5D' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Analytics</h1>
          <p className="mt-1 text-muted-foreground">Gain insights from your complaint data</p>
        </div>

        <div className="flex gap-2">
          {[
            { value: '7d', label: 'Last 7 Days' },
            { value: '30d', label: 'Last 30 Days' },
            { value: '90d', label: 'Last 90 Days' },
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

      {isLoading ? (
        <div className="flex h-96 items-center justify-center gap-3">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Loading analytics...</span>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Total Complaints"
              value={(analytics?.total_complaints ?? 0).toLocaleString()}
              change={trendChange}
              trend={trendDirection}
              icon={Users}
            />
            <StatCard
              title="Resolution Rate"
              value={`${(analytics?.resolution_rate ?? 0).toFixed(1)}%`}
              icon={CheckCircle2}
              trend="up"
            />
            <StatCard
              title="Avg First Response"
              value={`${averageResponseMinutes} min`}
              icon={Clock}
              trend="down"
            />
            <StatCard
              title="Customer Satisfaction"
              value={`${(analytics?.customer_satisfaction ?? 0).toFixed(1)}/5`}
              icon={Target}
              trend="up"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Complaint Volume Trend</CardTitle>
                <CardDescription>Daily complaint volume over the selected period</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={volumeTrend}>
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
                          borderRadius: '8px',
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

          <div className="grid gap-6 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Top Categories</CardTitle>
                <CardDescription>Most frequent complaint categories</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topCategories} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
                      <XAxis type="number" className="text-xs" />
                      <YAxis dataKey="category" type="category" className="text-xs" width={100} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
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
                          borderRadius: '8px',
                        }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

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
                          borderRadius: '8px',
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

          <div className="grid gap-6 lg:grid-cols-2">
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
                          borderRadius: '8px',
                        }}
                      />
                      <Bar dataKey="count" fill="#3B82F6" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

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
                          borderRadius: '8px',
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

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                <CardTitle>AI Performance</CardTitle>
              </div>
              <CardDescription>Metrics based on live AI activity in your complaint workflow</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 md:grid-cols-3">
                <div className="rounded-xl bg-gradient-to-br from-blue-50 to-purple-50 p-6 text-center">
                  <p className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-4xl font-bold text-transparent">
                    {(analytics?.average_ai_confidence ?? 0).toFixed(1)}%
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">Average AI Confidence</p>
                  <Badge className="mt-3 bg-blue-100 text-blue-700">
                    Live model confidence on classified complaints
                  </Badge>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-blue-50 to-purple-50 p-6 text-center">
                  <p className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-4xl font-bold text-transparent">
                    {autoResolutionRate}%
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">Auto-resolution Rate</p>
                  <Badge className="mt-3 bg-green-100 text-green-700">
                    Complaints resolved after an AI reply was sent
                  </Badge>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-blue-50 to-purple-50 p-6 text-center">
                  <p className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-4xl font-bold text-transparent">
                    {escalationRate}%
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">Escalation Rate</p>
                  <Badge className="mt-3 bg-orange-100 text-orange-700">
                    Complaints that required manual escalation
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Flame className="h-5 w-5 text-rose-500" />
                  <CardTitle>Root Cause Analysis</CardTitle>
                </div>
                <CardDescription>Trending complaint categories and where operational attention is needed most.</CardDescription>
              </CardHeader>
              <CardContent>
                {rootCauseLocked ? (
                  <UpgradePrompt
                    title="Unlock root cause analysis"
                    description="Compare complaint categories period over period and surface fast-growing issues."
                    requiredPlan="Max"
                  />
                ) : rootCause ? (
                  <div className="space-y-4">
                    <div className="rounded-xl bg-slate-950 p-4 text-white">
                      <p className="text-sm text-slate-300">Overall period change</p>
                      <p className="mt-2 text-3xl font-semibold">
                        {rootCause.overall_change_percentage > 0 ? '+' : ''}
                        {rootCause.overall_change_percentage}%
                      </p>
                      <p className="mt-2 text-sm text-slate-400">{rootCause.period}</p>
                    </div>
                    {rootCause.top_issues.slice(0, 4).map((issue) => (
                      <div key={issue.category} className="flex items-center justify-between rounded-xl border p-4">
                        <div>
                          <p className="font-medium">{issue.category}</p>
                          <p className="text-sm text-muted-foreground">
                            {issue.current_count} complaints, {issue.percentage_of_total}% of total
                          </p>
                        </div>
                        <Badge className={issue.change_percentage > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}>
                          {issue.change_percentage > 0 ? '+' : ''}
                          {issue.change_percentage}%
                        </Badge>
                      </div>
                    ))}
                    <div className="rounded-xl bg-muted/50 p-4 text-sm text-muted-foreground">
                      {rootCause.insights[0] ?? 'No critical issue spikes detected.'}
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                    Root cause analysis is not available yet for this range.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-sky-600" />
                  <CardTitle>Team Performance</CardTitle>
                </div>
                <CardDescription>Resolution quality, response speed, and workload by assigned owner.</CardDescription>
              </CardHeader>
              <CardContent>
                {teamLocked ? (
                  <UpgradePrompt
                    title="Unlock team performance"
                    description="Measure agent workload, resolution rate, and handling speed across the team."
                    requiredPlan="Max"
                  />
                ) : teamPerformanceData.length > 0 ? (
                  <div className="space-y-4">
                    <div className="h-[240px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={teamPerformanceData}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="agent_name" className="text-xs" />
                          <YAxis className="text-xs" />
                          <Tooltip />
                          <Bar dataKey="total_tickets" fill="#0EA5E9" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="resolved_tickets" fill="#22C55E" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="grid gap-3">
                      {teamPerformanceData.slice(0, 3).map((member) => (
                        <div key={member.agent_name} className="flex items-center justify-between rounded-xl border p-4">
                          <div>
                            <p className="font-medium">{member.agent_name}</p>
                            <p className="text-sm text-muted-foreground">
                              {member.avg_response_time_hours}h avg response, {member.avg_handle_time_hours}h avg handle
                            </p>
                          </div>
                          <Badge className="bg-emerald-100 text-emerald-700">
                            {member.resolution_rate}% resolved
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                    Team performance data is not available yet.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-orange-500" />
                <CardTitle>Churn Risk Outlook</CardTitle>
              </div>
              <CardDescription>High and critical risk customers who may need retention-first support.</CardDescription>
            </CardHeader>
            <CardContent>
              {churnLocked ? (
                <UpgradePrompt
                  title="Unlock churn risk scoring"
                  description="Highlight customers with repeated unresolved complaints and worsening sentiment."
                  requiredPlan="Max"
                />
              ) : churnRiskCustomers.length > 0 ? (
                <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
                  <div className="h-[220px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={churnRiskBreakdown}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="level" className="text-xs" />
                        <YAxis className="text-xs" />
                        <Tooltip />
                        <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                          {churnRiskBreakdown.map((entry) => (
                            <Cell key={entry.level} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-3">
                    {topRiskCustomers.map((customer) => (
                      <div key={customer.customer_email} className="rounded-xl border p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{customer.customer_email}</p>
                            <p className="mt-1 text-sm text-muted-foreground">{customer.recommendation}</p>
                          </div>
                          <Badge className={customer.risk_level === 'critical' ? 'bg-rose-100 text-rose-700' : 'bg-orange-100 text-orange-700'}>
                            {customer.risk_level}
                          </Badge>
                        </div>
                        <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
                          <span>Risk score {customer.risk_score}</span>
                          <span>{customer.unresolved_count} unresolved</span>
                          <span>Avg sentiment {customer.avg_sentiment}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                  No high-risk customers were identified in the selected period.
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}


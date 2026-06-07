import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import {
  MessageSquare,
  CheckCircle,
  Clock,
  TrendingUp,
  AlertTriangle,
  Bot,
  ArrowRight,
  Brain,
  IndianRupee,
  Layers,
  Users,
  Sparkles,
  Send,
} from "lucide-react";
import { Link, useNavigate } from "react-router";
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

function formatINR(val: number) {
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
  if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
  if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
  return `₹${val}`;
}

export function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pulse, setPulse] = useState<any>(null);
  const [risk, setRisk] = useState<any>(null);
  const [copilotInput, setCopilotInput] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    loadStats();
    api.intelligence.pulse().then(setPulse).catch(() => null);
    api.intelligence.revenueRisk().then(setRisk).catch(() => null);
  }, []);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.dashboard.stats();
      setStats(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || "Failed to load dashboard";
      setError(msg);
      console.error("Failed to load stats:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopilotAsk = () => {
    if (!copilotInput.trim()) return;
    navigate(`/app/copilot?q=${encodeURIComponent(copilotInput.trim())}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-500 gap-2">
        <Clock className="size-5 animate-spin" />
        Loading dashboard…
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <AlertTriangle className="size-8 text-red-500" />
        <p className="text-red-600 font-medium">Failed to load dashboard</p>
        <p className="text-sm text-gray-500">{error}</p>
        <Button variant="outline" size="sm" onClick={loadStats}>Try Again</Button>
      </div>
    );
  }

  const priorityData = [
    { name: "Critical", value: stats.priority_breakdown.critical, color: "#ef4444" },
    { name: "High", value: stats.priority_breakdown.high, color: "#f97316" },
    { name: "Medium", value: stats.priority_breakdown.medium, color: "#eab308" },
    { name: "Low", value: stats.priority_breakdown.low, color: "#22c55e" },
  ];

  const categoryData = Object.entries(stats.category_distribution).map(([name, value]) => ({
    name,
    value,
  }));

  const volumeData = stats.ticket_volume.map((value: number, index: number) => ({
    day: `Day ${index + 1}`,
    tickets: value,
  }));

  const csatData = stats.csat_trend.map((value: number, index: number) => ({
    day: `Day ${index + 1}`,
    csat: value,
  }));

  // Spike detection from pulse
  const topSpike = pulse?.new_complaint_spikes?.[0] ?? null;
  const topIssue = pulse?.top_issues?.[0] ?? null;
  const churnCount = pulse?.churn_risk_customers?.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold dark:text-white">Operational Intelligence</h1>
          <p className="text-gray-600 dark:text-gray-400">AI-powered intelligence across your customer operations</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/app/copilot">
            <Button size="sm" className="gap-2">
              <Sparkles className="size-4" />
              Ask Copilot
            </Button>
          </Link>
          <Link to="/app/intelligence">
            <Button variant="outline" size="sm" className="gap-2 dark:border-gray-700">
              <Brain className="size-4 text-blue-600" />
              Intelligence Hub
            </Button>
          </Link>
        </div>
      </div>

      {/* Quick Copilot — primary CTA */}
      <Card className="dark:bg-gray-900 dark:border-gray-800 border-blue-100 dark:border-blue-900/40 bg-gradient-to-r from-blue-50/60 to-white dark:from-blue-950/20 dark:to-gray-900">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <Sparkles className="size-5 text-blue-600 shrink-0" />
            <div className="flex-1 relative">
              <input
                type="text"
                value={copilotInput}
                onChange={(e) => setCopilotInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCopilotAsk()}
                placeholder="Ask the AI — What is broken? What does it cost? What should we fix first?"
                className="w-full border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2.5 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <Button
              size="sm"
              onClick={handleCopilotAsk}
              disabled={!copilotInput.trim()}
              className="shrink-0"
            >
              <Send className="size-3.5 mr-1.5" />
              Ask
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Spike alert */}
      {topSpike && (
        <div className="flex items-center gap-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-4 py-3">
          <AlertTriangle className="size-5 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-800 dark:text-amber-200 flex-1">
            {topSpike.type === "volume_spike"
              ? `Complaint spike detected — ${topSpike.hour_count ?? "?"} complaints in the last hour`
              : `Sentiment drop detected — avg ${topSpike.avg_sentiment?.toFixed(2) ?? "?"}`}
            {" "}(severity: <span className="font-medium">{topSpike.severity}</span>)
          </p>
          <Link to="/app/intelligence" className="text-xs font-medium text-amber-700 dark:text-amber-300 hover:underline shrink-0">
            View in Intelligence Hub →
          </Link>
        </div>
      )}

      {/* Intelligence summary row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="size-9 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
              <IndianRupee className="size-4 text-red-600" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {risk && !risk.has_revenue_data ? "Customer Risk" : "Revenue at Risk"}
                </p>
                {risk && (
                  <span className={`text-[9px] font-semibold uppercase px-1 py-0.5 rounded ${
                    risk.confidence === "high"
                      ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                      : risk.confidence === "medium"
                      ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400"
                      : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                  }`}>
                    {risk.confidence}
                  </span>
                )}
              </div>
              <p className="text-lg font-bold dark:text-white">
                {risk
                  ? risk.has_revenue_data
                    ? <>
                        {risk.confidence === "medium" && <span className="text-sm font-normal text-gray-400 mr-0.5">Est.</span>}
                        {formatINR(risk.total_revenue_at_risk)}
                      </>
                    : `${risk.high_risk_count} accounts`
                  : "—"}
              </p>
              {risk && (
                <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                  {risk.has_revenue_data
                    ? `Avg risk ${risk.avg_risk_score?.toFixed(0) ?? "—"}/100`
                    : "No revenue data · connect Stripe or Razorpay"}
                </p>
              )}
            </div>
            <Link to="/app/intelligence" className="ml-auto text-xs text-blue-600 hover:underline shrink-0">
              View →
            </Link>
          </CardContent>
        </Card>

        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="size-9 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
              <Layers className="size-4 text-blue-600" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-gray-500 dark:text-gray-400">Top Issue Theme</p>
              <p className="text-sm font-semibold dark:text-white capitalize truncate">
                {topIssue ? `${topIssue.category} (${topIssue.count})` : "No data yet"}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="size-9 rounded-full bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center shrink-0">
              <Users className="size-4 text-orange-600" />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">Churn Risk Customers</p>
              <p className="text-lg font-bold dark:text-white">{churnCount}</p>
            </div>
            <Link to="/app/customers" className="ml-auto text-xs text-blue-600 hover:underline shrink-0">
              View →
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total Tickets
            </CardTitle>
            <MessageSquare className="size-4 text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.total_tickets_month}</div>
            <p className="text-xs text-gray-500 mt-1">
              {stats.total_tickets} all time
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Open Tickets
            </CardTitle>
            <Clock className="size-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.open_tickets}</div>
            <p className="text-xs text-gray-500 mt-1">Requires attention</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Resolved (This Month)
            </CardTitle>
            <CheckCircle className="size-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.resolved_tickets_month}</div>
            <p className="text-xs text-gray-500 mt-1">
              {Math.round((stats.resolved_tickets_month / stats.total_tickets_month) * 100)}% of total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Avg CSAT Score
            </CardTitle>
            <TrendingUp className="size-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.csat_avg.toFixed(1)}</div>
            <p className="text-xs text-gray-500 mt-1">Out of 5.0</p>
          </CardContent>
        </Card>
      </div>

      {/* Alerts */}
      {stats.sla_breached > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <AlertTriangle className="size-8 text-red-600" />
              <div className="flex-1">
                <h3 className="font-semibold text-red-900">
                  {stats.sla_breached} SLA Breaches
                </h3>
                <p className="text-sm text-red-700">
                  Some tickets have exceeded their SLA deadline. Immediate action required.
                </p>
              </div>
              <Link to="/app/complaints?sla=breached">
                <Button variant="destructive">
                  View Breached Tickets
                  <ArrowRight className="size-4 ml-2" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {stats.ai_queue_size > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <Bot className="size-8 text-blue-600" />
              <div className="flex-1">
                <h3 className="font-semibold text-blue-900">
                  {stats.ai_queue_size} AI Replies Pending Review
                </h3>
                <p className="text-sm text-blue-700">
                  AI-generated drafts are waiting for human approval before sending.
                </p>
              </div>
              <Link to="/app/reply-queue">
                <Button>
                  Review Drafts
                  <ArrowRight className="size-4 ml-2" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Signal Volume (Last 14 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={volumeData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="tickets"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.6}
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CSAT Trend (Last 7 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={csatData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis domain={[0, 5]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="csat"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Priority Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={priorityData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.name}: ${entry.value}`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {priorityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top Complaint Categories</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={categoryData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#8b5cf6" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="dark:text-white text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link to="/app/complaints">
              <Button variant="outline" className="w-full dark:border-gray-700">
                <MessageSquare className="size-4 mr-2" />
                View Inbox
              </Button>
            </Link>
            <Link to="/app/reply-queue">
              <Button variant="outline" className="w-full dark:border-gray-700">
                <Bot className="size-4 mr-2" />
                Review AI Replies
              </Button>
            </Link>
            <Link to="/app/assignments">
              <Button variant="outline" className="w-full dark:border-gray-700">
                <Clock className="size-4 mr-2" />
                Manage Assignments
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

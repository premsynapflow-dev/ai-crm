import { useEffect, useState } from "react";
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
} from "lucide-react";
import { Link } from "react-router";
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

export function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await api.dashboard.stats();
      setStats(data);
    } catch (error) {
      console.error("Failed to load stats:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !stats) {
    return <div>Loading...</div>;
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-600">Overview of your complaint operations</p>
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
            <CardTitle>Ticket Volume (Last 14 Days)</CardTitle>
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

      {/* Quick Links */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link to="/app/complaints">
              <Button variant="outline" className="w-full">
                <MessageSquare className="size-4 mr-2" />
                View All Complaints
              </Button>
            </Link>
            <Link to="/app/reply-queue">
              <Button variant="outline" className="w-full">
                <Bot className="size-4 mr-2" />
                Review AI Replies
              </Button>
            </Link>
            <Link to="/app/assignments">
              <Button variant="outline" className="w-full">
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

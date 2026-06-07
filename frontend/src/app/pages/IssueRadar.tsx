import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import {
  Radar,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ArrowRight,
  IndianRupee,
  ChevronRight,
} from "lucide-react";
import { Link } from "react-router";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

type Cluster = Awaited<ReturnType<typeof api.intelligence.clusters>>[number];
type OpsData = Awaited<ReturnType<typeof api.intelligence.operations>>;

interface ExecutiveSummary {
  what_broke: { issue: string; count: number; change_pct: number };
  cost: { revenue_at_risk: number; high_risk_customers: number };
}

interface IssueRow {
  id: string;
  title: string;
  severity: "high" | "medium" | "low";
  affectedCategory: string;
  signalCount: number;
  revenueImpact: number | null;
  trend: "rising" | "stable" | "falling";
  source: "cluster" | "spike" | "theme";
}

function formatINR(val: number) {
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
  if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
  if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
  return `₹${val}`;
}

function severityColor(s: IssueRow["severity"]) {
  if (s === "high") return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800";
  if (s === "medium") return "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300 border-orange-200 dark:border-orange-800";
  return "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-700";
}

function TrendIcon({ trend }: { trend: IssueRow["trend"] }) {
  if (trend === "rising") return <TrendingUp className="size-4 text-red-500" />;
  if (trend === "falling") return <TrendingDown className="size-4 text-green-500" />;
  return <Minus className="size-4 text-gray-400" />;
}

function buildIssues(
  clusters: Cluster[],
  ops: OpsData | null,
  exec: ExecutiveSummary | null,
  revenueAtRisk: number,
): IssueRow[] {
  const issues: IssueRow[] = [];

  // Clusters → issues
  clusters.forEach((c) => {
    const severity: IssueRow["severity"] = c.size > 20 ? "high" : c.size > 8 ? "medium" : "low";
    issues.push({
      id: c.id,
      title: c.cluster_label,
      severity,
      affectedCategory: c.top_category || "general",
      signalCount: c.size,
      revenueImpact: null,
      trend: "stable",
      source: "cluster",
    });
  });

  // Spikes → issues (if not already represented by a cluster)
  if (ops?.spikes?.length) {
    ops.spikes.forEach((spike: { severity?: string; type?: string; category?: string }) => {
      const sev = spike.severity === "high" ? "high" : "medium";
      issues.push({
        id: `spike-${spike.type}-${spike.category}`,
        title: spike.type === "volume_spike"
          ? `Volume spike: ${spike.category || "multiple categories"}`
          : `Sentiment drop: ${spike.category || "multiple categories"}`,
        severity: sev,
        affectedCategory: (spike.category as string) || "general",
        signalCount: 0,
        revenueImpact: null,
        trend: "rising",
        source: "spike",
      });
    });
  }

  // Apply revenue impact to highest-severity issue from executive data
  if (exec && revenueAtRisk > 0 && issues.length > 0) {
    const highestIdx = issues.findIndex((i) => i.severity === "high");
    if (highestIdx >= 0) {
      issues[highestIdx].revenueImpact = revenueAtRisk;
    }
  }

  // Sort: high → medium → low, then by signalCount
  return issues.sort((a, b) => {
    const sevOrder = { high: 0, medium: 1, low: 2 };
    if (sevOrder[a.severity] !== sevOrder[b.severity]) return sevOrder[a.severity] - sevOrder[b.severity];
    return b.signalCount - a.signalCount;
  });
}

export function IssueRadar() {
  const { user } = useAuth();
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [ops, setOps] = useState<OpsData | null>(null);
  const [exec, setExec] = useState<ExecutiveSummary | null>(null);
  const [revenueAtRisk, setRevenueAtRisk] = useState(0);
  const [loading, setLoading] = useState(true);

  const apiKey = user?.apiKey || "";

  async function load() {
    setLoading(true);
    try {
      const [clusterData, opsData, riskData] = await Promise.all([
        api.intelligence.clusters(30).catch(() => []),
        api.intelligence.operations().catch(() => null),
        api.intelligence.revenueRisk().catch(() => null),
      ]);
      setClusters(clusterData);
      setOps(opsData);
      setRevenueAtRisk(riskData?.total_revenue_at_risk ?? 0);

      if (apiKey) {
        try {
          const resp = await fetch(`${API_BASE}/api/v1/executive/summary?days=7`, {
            headers: { "x-api-key": apiKey },
          });
          if (resp.ok) setExec(await resp.json());
        } catch {
          // executive summary is optional enrichment
        }
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const issues = buildIssues(clusters, ops, exec, revenueAtRisk);
  const topSpike = ops?.spikes?.[0] ?? null;
  const themeData = (ops?.top_themes ?? []).slice(0, 5).map((t) => ({ name: t.theme, value: t.count }));

  const COLORS = ["#ef4444", "#f97316", "#f59e0b", "#3b82f6", "#8b5cf6"];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radar className="size-6 text-blue-600" />
          <div>
            <h1 className="text-xl font-semibold dark:text-white">Issue Radar</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">Emerging operational failures · Last 30 days</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="dark:border-gray-700">
          <RefreshCw className={`size-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Spike alert banner */}
      {topSpike && (
        <div className="flex items-center gap-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg px-4 py-3">
          <AlertTriangle className="size-5 text-red-600 shrink-0" />
          <div className="text-sm text-red-800 dark:text-red-200 flex-1">
            {topSpike.type === "volume_spike"
              ? `Active volume spike detected — elevated complaint rate (severity: ${topSpike.severity})`
              : `Sentiment deterioration detected (severity: ${topSpike.severity})`}
          </div>
          <Badge variant="outline" className="border-red-400 text-red-600 shrink-0">
            {topSpike.severity}
          </Badge>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Issue table */}
        <div className="lg:col-span-2 space-y-3">
          {loading ? (
            [...Array(4)].map((_, i) => (
              <Card key={i} className="animate-pulse dark:bg-gray-900 dark:border-gray-800">
                <CardContent className="h-20" />
              </Card>
            ))
          ) : issues.length === 0 ? (
            <Card className="dark:bg-gray-900 dark:border-gray-800">
              <CardContent className="py-12 text-center">
                <Radar className="size-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400">No issues detected in the last 30 days.</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Run clustering from the Intelligence Hub to surface patterns.</p>
                <Link to="/app/intelligence">
                  <Button variant="outline" size="sm" className="mt-4 dark:border-gray-700">
                    Go to Intelligence Hub
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            issues.map((issue) => (
              <Card
                key={issue.id}
                className={`dark:bg-gray-900 border ${
                  issue.severity === "high"
                    ? "border-red-200 dark:border-red-900/60"
                    : issue.severity === "medium"
                    ? "border-orange-200 dark:border-orange-900/60"
                    : "dark:border-gray-800"
                }`}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    {/* Severity badge */}
                    <span className={`shrink-0 mt-0.5 inline-block text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${severityColor(issue.severity)}`}>
                      {issue.severity}
                    </span>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold dark:text-white truncate">{issue.title}</p>
                        <Badge variant="outline" className="text-xs dark:border-gray-700 capitalize">
                          {issue.affectedCategory}
                        </Badge>
                        {issue.source === "spike" && (
                          <Badge variant="secondary" className="text-[10px]">Live Spike</Badge>
                        )}
                      </div>

                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
                        <span>{issue.signalCount > 0 ? `${issue.signalCount} signals` : "Active spike"}</span>
                        {issue.revenueImpact !== null && issue.revenueImpact > 0 && (
                          <span className="flex items-center gap-0.5 text-red-600 dark:text-red-400 font-medium">
                            <IndianRupee className="size-3" />
                            {formatINR(issue.revenueImpact)} at risk
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <TrendIcon trend={issue.trend} />
                          {issue.trend}
                        </span>
                      </div>
                    </div>

                    {/* Action */}
                    {issue.source === "cluster" && (
                      <Link
                        to={`/app/investigations?cluster_id=${issue.id}`}
                        className="shrink-0 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium whitespace-nowrap"
                      >
                        Investigate
                        <ArrowRight className="size-3" />
                      </Link>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          {/* Top themes */}
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
                <TrendingUp className="size-4 text-blue-500" />
                Top Signal Themes (7d)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {themeData.length === 0 ? (
                <p className="text-xs text-gray-400 dark:text-gray-500 py-4 text-center">No theme data available</p>
              ) : (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={themeData} layout="vertical" margin={{ left: 0, right: 16, top: 0, bottom: 0 }}>
                    <XAxis type="number" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      width={80}
                      tickFormatter={(v: string) => v.length > 12 ? v.slice(0, 12) + "…" : v}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 11, borderRadius: 6 }}
                      formatter={(v: number) => [v, "signals"]}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {themeData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Executive summary context */}
          {exec && (
            <Card className="dark:bg-gray-900 dark:border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold dark:text-white">Primary Concern</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="size-4 text-amber-500 shrink-0" />
                  <span className="text-sm font-medium dark:text-white capitalize">{exec.what_broke.issue}</span>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {exec.what_broke.count} signals ·{" "}
                  <span className={exec.what_broke.change_pct > 0 ? "text-red-500" : "text-green-500"}>
                    {exec.what_broke.change_pct > 0 ? "+" : ""}{exec.what_broke.change_pct.toFixed(0)}% vs prior period
                  </span>
                </div>
                {exec.cost.revenue_at_risk > 0 && (
                  <div className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium">
                    <IndianRupee className="size-3" />
                    {formatINR(exec.cost.revenue_at_risk)} revenue at risk
                  </div>
                )}
                <Link
                  to="/app/health"
                  className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-1"
                >
                  Full operational health
                  <ChevronRight className="size-3" />
                </Link>
              </CardContent>
            </Card>
          )}

          {/* Quick nav */}
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="p-4 space-y-2">
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Investigate</p>
              <Link to="/app/investigations" className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 py-1">
                <span>All Issue Clusters</span>
                <ChevronRight className="size-4" />
              </Link>
              <Link to="/app/health" className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 py-1">
                <span>Operational Health</span>
                <ChevronRight className="size-4" />
              </Link>
              <Link to="/app/customers" className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 py-1">
                <span>Customer Impact</span>
                <ChevronRight className="size-4" />
              </Link>
              <Link to="/app/copilot" className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 py-1">
                <span>Ask Operational Copilot</span>
                <ChevronRight className="size-4" />
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

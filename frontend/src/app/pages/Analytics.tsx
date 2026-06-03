import { useEffect, useState, useMemo } from "react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "../components/ui/dialog";
import { Lock, RefreshCw, TrendingUp, TrendingDown, Minus, BrainCircuit, ChevronRight } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { api, Complaint, Customer } from "../lib/api";
import { Link } from "react-router";

// ── palette ───────────────────────────────────────────────────────────────────
const BLUE = "#3b82f6";
const GREEN = "#22c55e";
const AMBER = "#f59e0b";
const RED = "#ef4444";
const PURPLE = "#a855f7";
const GRAY = "#6b7280";

const PRIORITY_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#22c55e",
};
const SENTIMENT_COLORS: Record<string, string> = {
  positive: GREEN,
  neutral: AMBER,
  negative: RED,
};
const SLA_COLORS: Record<string, string> = {
  on_track: GREEN,
  at_risk: AMBER,
  breached: RED,
  approaching: "#f97316",
};
const CHURN_COLORS: Record<string, string> = { low: GREEN, medium: AMBER, high: RED };
const CATEGORY_COLORS = [BLUE, PURPLE, AMBER, GREEN, RED, "#06b6d4", "#84cc16", "#f43f5e"];

// ── helper: last N days labels ────────────────────────────────────────────────
function lastNDays(n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(Date.now() - (n - 1 - i) * 86400000);
    return d.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
  });
}

function dayKey(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

// ── mini stat card ────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, trend,
}: { label: string; value: string | number; sub?: string; trend?: "up" | "down" | "neutral" }) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor = trend === "up" ? "text-red-500" : trend === "down" ? "text-green-500" : "text-gray-400";
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
        <p className="text-3xl font-bold mt-1 dark:text-white">{value}</p>
        {sub && (
          <p className={`text-xs mt-1 flex items-center gap-1 ${trendColor}`}>
            <TrendIcon className="size-3" /> {sub}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── custom tooltip ────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg p-2 text-sm">
      {label && <p className="text-gray-500 dark:text-gray-400 mb-1">{label}</p>}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="size-2 rounded-full inline-block" style={{ background: p.fill || p.stroke }} />
          <span className="dark:text-gray-200">{p.name}: <strong>{p.value}</strong></span>
        </div>
      ))}
    </div>
  );
}

// ── pie label ─────────────────────────────────────────────────────────────────
function PieLabel({ cx, cy, midAngle, outerRadius, percent, name }: any) {
  if (percent < 0.06) return null;
  const RADIAN = Math.PI / 180;
  const radius = outerRadius + 24;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="currentColor" textAnchor={x > cx ? "start" : "end"} fontSize={11}
      className="fill-gray-600 dark:fill-gray-400">
      {name} ({(percent * 100).toFixed(0)}%)
    </text>
  );
}

// ── Root Cause Analysis card ──────────────────────────────────────────────────
function EntityPill({ label, value, freq }: { label: string; value: string; freq: number }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs border border-blue-200 dark:border-blue-700">
      <span className="font-medium capitalize">{label}:</span> {value}
      <span className="text-blue-400">({Math.round(freq * 100)}%)</span>
    </span>
  );
}

function CausalDetailModal({ item }: { item: any }) {
  const category = (item.category || "unknown").replace(/_/g, " ");
  const hypotheses: string[] = item.hypotheses || [];
  const entities: Record<string, Array<{ value: string; frequency: number; count: number }>> = item.common_entities || {};
  const change = item.change_percentage ?? 0;

  return (
    <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 capitalize">
          <BrainCircuit className="size-5 text-blue-500" />
          Root Cause: {category}
          <Badge variant={change > 20 ? "destructive" : change > 0 ? "outline" : "secondary"} className="ml-2">
            {change > 0 ? "+" : ""}{change.toFixed(1)}% vs prior period
          </Badge>
        </DialogTitle>
      </DialogHeader>

      <div className="space-y-5 mt-2">
        {/* How AI reached this conclusion */}
        <section>
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
            AI Reasoning Chain
          </h3>
          <div className="space-y-2">
            <div className="flex gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm">
              <span className="shrink-0 size-6 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 flex items-center justify-center font-bold text-xs">1</span>
              <div>
                <p className="font-medium text-gray-700 dark:text-gray-300">Detected category spike</p>
                <p className="text-gray-500 dark:text-gray-400 text-xs mt-0.5">
                  <span className="capitalize">{category}</span> complaints rose {change > 0 ? "+" : ""}{change.toFixed(1)}% compared to the prior period. This triggered root cause analysis.
                </p>
              </div>
            </div>

            {Object.keys(entities).length > 0 && (
              <div className="flex gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm">
                <span className="shrink-0 size-6 rounded-full bg-purple-100 dark:bg-purple-900 text-purple-600 dark:text-purple-300 flex items-center justify-center font-bold text-xs">2</span>
                <div>
                  <p className="font-medium text-gray-700 dark:text-gray-300">Named entity extraction across all {category} complaints</p>
                  <p className="text-gray-500 dark:text-gray-400 text-xs mt-0.5">
                    AI extracted products, locations, employee names, order IDs, and dates mentioned across all tickets in this category to identify common patterns.
                  </p>
                </div>
              </div>
            )}

            {hypotheses.length > 0 && (
              <div className="flex gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm">
                <span className="shrink-0 size-6 rounded-full bg-green-100 dark:bg-green-900 text-green-600 dark:text-green-300 flex items-center justify-center font-bold text-xs">3</span>
                <div>
                  <p className="font-medium text-gray-700 dark:text-gray-300">Causal hypothesis generation</p>
                  <p className="text-gray-500 dark:text-gray-400 text-xs mt-0.5">
                    Based on entity frequency patterns, Gemini generated {hypotheses.length} probable root cause{hypotheses.length !== 1 ? "s" : ""} explaining the spike.
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Common entities found */}
        {Object.keys(entities).length > 0 && (
          <section>
            <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
              Common Signals Detected (appearing in ≥ 30% of tickets)
            </h3>
            <div className="space-y-3">
              {Object.entries(entities).map(([etype, entries]) => (
                <div key={etype}>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 capitalize mb-1.5">
                    {etype.replace(/_/g, " ")}s
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {entries.map((e, i) => (
                      <EntityPill key={i} label={etype.replace(/_/g, " ")} value={e.value} freq={e.frequency} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* AI hypotheses */}
        {hypotheses.length > 0 && (
          <section>
            <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
              AI-Generated Root Cause Hypotheses
            </h3>
            <div className="space-y-2">
              {hypotheses.map((h, i) => (
                <div key={i} className="flex gap-3 p-3 border dark:border-gray-700 rounded-lg">
                  <span className="shrink-0 size-5 rounded-full bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 flex items-center justify-center font-bold text-xs">
                    {i + 1}
                  </span>
                  <p className="text-sm text-gray-800 dark:text-gray-200">{h}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* What to do next */}
        <section className="p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1">Suggested Next Step</p>
          <p className="text-xs text-blue-600 dark:text-blue-400">
            Investigate the highest-frequency signals above with your team. If entities include specific products or
            locations, cross-reference with engineering or operations logs from the same timeframe.
          </p>
        </section>
      </div>
    </DialogContent>
  );
}

function RootCauseCard({ rootCause }: { rootCause: any }) {
  const causal: any[] = rootCause?.causal_analysis || [];
  const insights: string[] = rootCause?.why?.root_cause_insights || [];

  if (!rootCause) {
    return (
      <Card>
        <CardHeader><CardTitle className="dark:text-white">Root Cause Analysis</CardTitle></CardHeader>
        <CardContent>
          <div className="h-48 flex items-center justify-center text-gray-400">Loading AI analysis…</div>
        </CardContent>
      </Card>
    );
  }

  // If no trending categories triggered causal analysis, fall back to insights list
  if (causal.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 dark:text-white">
            <BrainCircuit className="size-5 text-blue-500" />
            Root Cause Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          {insights.length === 0 ? (
            <p className="text-gray-400 text-sm">No significant category spikes detected in this period.</p>
          ) : (
            <ul className="space-y-2">
              {insights.map((ins, i) => (
                <li key={i} className="flex gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <span className="text-blue-400 shrink-0 mt-0.5">•</span>
                  {ins}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 dark:text-white">
            <BrainCircuit className="size-5 text-blue-500" />
            Root Cause Analysis
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {causal.length} categor{causal.length === 1 ? "y" : "ies"} analysed
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {causal.map((item: any, idx: number) => {
          const category = (item.category || "unknown").replace(/_/g, " ");
          const change = item.change_percentage ?? 0;
          const hypotheses: string[] = item.hypotheses || [];
          const entities: Record<string, any[]> = item.common_entities || {};
          const topEntities = Object.values(entities).flat().slice(0, 3);

          return (
            <div key={idx}
              className="border dark:border-gray-700 rounded-lg p-4 space-y-3 hover:border-blue-300 dark:hover:border-blue-600 transition-colors">
              {/* Category header */}
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-800 dark:text-white capitalize text-sm">{category}</h3>
                <Badge variant={change > 20 ? "destructive" : change > 0 ? "outline" : "secondary"}>
                  {change > 0 ? "+" : ""}{change.toFixed(1)}% complaints
                </Badge>
              </div>

              {/* Top hypothesis — the "why" */}
              {hypotheses.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    Most likely cause
                  </p>
                  <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                    {hypotheses[0]}
                  </p>
                  {hypotheses.length > 1 && (
                    <p className="text-xs text-gray-400">
                      +{hypotheses.length - 1} more hypothesis{hypotheses.length > 2 ? "es" : ""} in details
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-500 italic">
                  No causal hypotheses generated yet — more data needed.
                </p>
              )}

              {/* Common signals */}
              {topEntities.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Common signals</p>
                  <div className="flex flex-wrap gap-1.5">
                    {topEntities.map((e: any, i: number) => (
                      <span key={i}
                        className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-full">
                        {e.value} ({Math.round(e.frequency * 100)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* View Details button */}
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="w-full mt-1">
                    <ChevronRight className="size-4 mr-1" />
                    View Full AI Reasoning
                  </Button>
                </DialogTrigger>
                <CausalDetailModal item={item} />
              </Dialog>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

// ── main ──────────────────────────────────────────────────────────────────────
export function Analytics() {
  const { user } = useAuth();
  const hasAdvanced = user && ["max", "scale", "enterprise"].includes(user.plan);

  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [rootCause, setRootCause] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  async function load() {
    setLoading(true);
    try {
      const [c, cu] = await Promise.all([
        api.complaints.list({ page: 1 }),
        hasAdvanced ? api.customers.list() : Promise.resolve([]),
      ]);
      setComplaints(c);
      setCustomers(cu);

      if (hasAdvanced) {
        try {
          const apiKey = user?.apiKey || "";
          const resp = await fetch(`/api/v1/executive/summary?days=${days}`, {
            headers: { "x-api-key": apiKey },
          });
          if (resp.ok) setRootCause(await resp.json());
        } catch { /* ignore */ }
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [days]);

  // ── derived data ──────────────────────────────────────────────────────────
  const cutoff = useMemo(
    () => new Date(Date.now() - days * 86400000),
    [days]
  );

  const filtered = useMemo(
    () => complaints.filter((c) => new Date(c.created_at) >= cutoff),
    [complaints, cutoff]
  );

  // Volume trend
  const volumeData = useMemo(() => {
    const keys = lastNDays(days);
    const isoKeys = Array.from({ length: days }, (_, i) =>
      new Date(Date.now() - (days - 1 - i) * 86400000).toISOString().slice(0, 10)
    );
    const map: Record<string, number> = {};
    for (const c of filtered) {
      const k = dayKey(c.created_at);
      map[k] = (map[k] || 0) + 1;
    }
    return isoKeys.map((iso, i) => ({ date: keys[i], count: map[iso] || 0 }));
  }, [filtered, days]);

  // Category
  const categoryData = useMemo(() => {
    const map: Record<string, number> = {};
    for (const c of filtered) if (c.category) map[c.category] = (map[c.category] || 0) + 1;
    return Object.entries(map)
      .map(([name, count]) => ({ name: name.replace(/_/g, " "), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [filtered]);

  // Priority
  const priorityData = useMemo(() => {
    const map: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const c of filtered) {
      if (c.priority >= 5) map.critical++;
      else if (c.priority === 4) map.high++;
      else if (c.priority === 3) map.medium++;
      else map.low++;
    }
    return Object.entries(map)
      .filter(([, v]) => v > 0)
      .map(([name, value]) => ({ name, value }));
  }, [filtered]);

  // SLA
  const slaData = useMemo(() => {
    const map: Record<string, number> = { on_track: 0, at_risk: 0, breached: 0 };
    for (const c of filtered) {
      const k = c.sla_status as string;
      map[k] = (map[k] || 0) + 1;
    }
    return Object.entries(map).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [filtered]);

  // Sentiment
  const sentimentData = useMemo(() => {
    const map: Record<string, number> = { positive: 0, neutral: 0, negative: 0 };
    for (const c of filtered) {
      const k = c.sentiment_label as string || "neutral";
      map[k] = (map[k] || 0) + 1;
    }
    return Object.entries(map).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [filtered]);

  // Status
  const statusData = useMemo(() => {
    const map: Record<string, number> = {};
    for (const c of filtered) {
      const k = c.status || "new";
      map[k] = (map[k] || 0) + 1;
    }
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [filtered]);

  // Churn risk (advanced)
  const churnData = useMemo(() => {
    const map: Record<string, number> = { low: 0, medium: 0, high: 0 };
    for (const cu of customers) map[cu.churn_risk] = (map[cu.churn_risk] || 0) + 1;
    return Object.entries(map).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [customers]);

  const totalFiltered = filtered.length;
  const resolved = filtered.filter((c) => c.status === "resolved").length;
  const resolutionRate = totalFiltered ? Math.round((resolved / totalFiltered) * 100) : 0;
  const breached = filtered.filter((c) => c.sla_status === "breached").length;
  const highChurn = customers.filter((c) => c.churn_risk === "high").length;

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold dark:text-white">Analytics</h1>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Card key={i} className="animate-pulse"><CardContent className="h-24" /></Card>)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[...Array(4)].map((_, i) => <Card key={i} className="animate-pulse"><CardContent className="h-64" /></Card>)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold dark:text-white">Analytics</h1>
          <p className="text-gray-500 dark:text-gray-400">Complaint intelligence · Last {days} days</p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 14, 30].map((d) => (
            <Button key={d} variant={days === d ? "default" : "outline"} size="sm" onClick={() => setDays(d)}>
              {d}d
            </Button>
          ))}
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="size-4" />
          </Button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Complaints" value={totalFiltered} />
        <StatCard label="Resolved" value={`${resolutionRate}%`}
          sub={`${resolved} of ${totalFiltered}`} trend="down" />
        <StatCard label="SLA Breached" value={breached}
          sub={totalFiltered ? `${Math.round(breached / totalFiltered * 100)}% of tickets` : "0%"}
          trend={breached > 0 ? "up" : "neutral"} />
        {hasAdvanced
          ? <StatCard label="High Churn Risk" value={highChurn}
            sub={`${customers.length} customers tracked`} trend={highChurn > 0 ? "up" : "neutral"} />
          : <StatCard label="Open Tickets" value={filtered.filter(c => c.status !== "resolved").length} />}
      </div>

      {/* Row 1: Volume trend + Category */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="dark:text-white">Ticket Volume Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={volumeData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="vol-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={BLUE} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={BLUE} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  tickLine={false}
                  interval={Math.floor(days / 6)} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} tickLine={false} allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="count" name="Complaints"
                  stroke={BLUE} fill="url(#vol-grad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="dark:text-white">Category Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            {categoryData.length === 0 ? (
              <div className="h-60 flex items-center justify-center text-gray-400">No data yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={categoryData} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
                  <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} tickLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={90}
                    tick={{ fontSize: 11, fill: "#6b7280" }} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="count" name="Complaints" radius={[0, 4, 4, 0]}>
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Row 2: Priority + SLA + Sentiment */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="dark:text-white">Priority Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {priorityData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-400">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={priorityData} cx="50%" cy="50%"
                    innerRadius={50} outerRadius={75}
                    dataKey="value" nameKey="name"
                    labelLine={false}
                    label={PieLabel}>
                    {priorityData.map((e, i) => (
                      <Cell key={i} fill={PRIORITY_COLORS[e.name] || GRAY} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend iconType="circle" iconSize={8}
                    formatter={(v) => <span className="text-xs text-gray-600 dark:text-gray-400 capitalize">{v}</span>} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="dark:text-white">SLA Compliance</CardTitle>
          </CardHeader>
          <CardContent>
            {slaData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-400">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={slaData} cx="50%" cy="50%"
                    innerRadius={50} outerRadius={75}
                    dataKey="value" nameKey="name"
                    labelLine={false}
                    label={PieLabel}>
                    {slaData.map((e, i) => (
                      <Cell key={i} fill={SLA_COLORS[e.name] || GRAY} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend iconType="circle" iconSize={8}
                    formatter={(v) => (
                      <span className="text-xs text-gray-600 dark:text-gray-400 capitalize">
                        {v.replace("_", " ")}
                      </span>
                    )} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="dark:text-white">Sentiment Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {sentimentData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-400">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={sentimentData} cx="50%" cy="50%"
                    innerRadius={50} outerRadius={75}
                    dataKey="value" nameKey="name"
                    labelLine={false}
                    label={PieLabel}>
                    {sentimentData.map((e, i) => (
                      <Cell key={i} fill={SENTIMENT_COLORS[e.name] || GRAY} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend iconType="circle" iconSize={8}
                    formatter={(v) => <span className="text-xs text-gray-600 dark:text-gray-400 capitalize">{v}</span>} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Status breakdown bar */}
      <Card>
        <CardHeader>
          <CardTitle className="dark:text-white">Ticket Status Overview</CardTitle>
        </CardHeader>
        <CardContent>
          {statusData.length === 0 ? (
            <div className="h-32 flex items-center justify-center text-gray-400">No data</div>
          ) : (
            <div className="space-y-3">
              {statusData.map((s) => {
                const pct = totalFiltered ? Math.round((s.value / totalFiltered) * 100) : 0;
                const color = s.name === "resolved" ? GREEN : s.name === "escalated" ? RED : s.name === "in-progress" ? AMBER : BLUE;
                return (
                  <div key={s.name}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="capitalize text-gray-700 dark:text-gray-300">{s.name.replace("-", " ")}</span>
                      <span className="text-gray-500 dark:text-gray-400">{s.value} ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Advanced — locked */}
      {!hasAdvanced ? (
        <Card className="border-2 border-dashed relative overflow-hidden">
          <div className="absolute inset-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm flex items-center justify-center z-10 rounded-lg">
            <div className="text-center p-8">
              <Lock className="size-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2 dark:text-white">Unlock Advanced Analytics</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Churn risk distribution, root cause analysis, and revenue impact — Max plan and above
              </p>
              <Link to="/app/billing">
                <Button>Upgrade to Max Plan</Button>
              </Link>
            </div>
          </div>
          <CardHeader><CardTitle>Advanced Analytics</CardTitle></CardHeader>
          <CardContent>
            <div className="h-48 opacity-20 bg-gray-100 dark:bg-gray-800 rounded" />
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Churn risk + Root cause */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="dark:text-white">Customer Churn Risk</CardTitle>
              </CardHeader>
              <CardContent>
                {churnData.length === 0 ? (
                  <div className="h-48 flex items-center justify-center text-gray-400">
                    No customer data — sync customers to see churn distribution
                  </div>
                ) : (
                  <>
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie data={churnData} cx="50%" cy="50%"
                          innerRadius={50} outerRadius={75}
                          dataKey="value" nameKey="name"
                          labelLine={false}
                          label={PieLabel}>
                          {churnData.map((e, i) => (
                            <Cell key={i} fill={CHURN_COLORS[e.name] || GRAY} />
                          ))}
                        </Pie>
                        <Tooltip content={<ChartTooltip />} />
                        <Legend iconType="circle" iconSize={8}
                          formatter={(v) => (
                            <span className="text-xs text-gray-600 dark:text-gray-400 capitalize">{v} risk</span>
                          )} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-center text-sm">
                      {churnData.map((d) => (
                        <div key={d.name}>
                          <div className="text-xl font-bold dark:text-white" style={{ color: CHURN_COLORS[d.name] }}>
                            {d.value}
                          </div>
                          <div className="text-xs text-gray-500 capitalize">{d.name} risk</div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <RootCauseCard rootCause={rootCause} />
          </div>

          {/* Revenue at risk */}
          {rootCause?.cost && (
            <Card className="border-red-200 dark:border-red-800">
              <CardHeader>
                <CardTitle className="text-red-700 dark:text-red-400">Revenue at Risk</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-4xl font-bold text-red-600 dark:text-red-400">
                      ₹{(rootCause.cost.revenue_at_risk ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {rootCause.cost.high_risk_customers ?? 0} customers with churn risk ≥ 70%
                    </p>
                  </div>
                  <Link to="/app/executive">
                    <Button variant="outline">View Full Report →</Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

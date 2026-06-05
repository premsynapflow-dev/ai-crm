import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Users,
  Layers,
  BarChart3,
  IndianRupee,
  RefreshCw,
  CheckCircle2,
  Zap,
  ArrowRight,
} from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Link } from "react-router";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";

type PulseData = Awaited<ReturnType<typeof api.intelligence.pulse>>;
type OpsData = Awaited<ReturnType<typeof api.intelligence.operations>>;
type RiskData = Awaited<ReturnType<typeof api.intelligence.revenueRisk>>;
type Cluster = Awaited<ReturnType<typeof api.intelligence.clusters>>[number];

function formatINR(val: number) {
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
  if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
  if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
  return `₹${val}`;
}

interface ActionItem {
  priority: "urgent" | "high" | "medium";
  title: string;
  description: string;
  href: string;
  linkLabel: string;
}

function deriveActions(
  ops: OpsData | null,
  clusters: Cluster[],
  risk: RiskData | null,
  pulse: PulseData | null,
): ActionItem[] {
  const actions: ActionItem[] = [];

  // Spike → urgent investigation
  const topSpike = ops?.spikes?.[0] ?? pulse?.new_complaint_spikes?.[0] ?? null;
  if (topSpike && topSpike.severity === "high") {
    actions.push({
      priority: "urgent",
      title: "Investigate complaint surge immediately",
      description: "A high-severity spike was detected. Assign your senior support lead to diagnose the root cause before volume compounds.",
      href: "/app/executive",
      linkLabel: "Executive summary →",
    });
  }

  // Revenue risk → customer outreach (only trigger when we have real revenue data)
  if (risk && risk.has_revenue_data && risk.total_revenue_at_risk > 50000) {
    actions.push({
      priority: "urgent",
      title: `Protect ${formatINR(risk.total_revenue_at_risk)} at-risk revenue`,
      description: `${risk.high_risk_count} high-churn customers represent ${formatINR(risk.total_revenue_at_risk)} in revenue. Proactive outreach now prevents churn that can't be reversed.`,
      href: "/app/customers",
      linkLabel: "View at-risk customers →",
    });
  } else if (risk && !risk.has_revenue_data && risk.high_risk_count > 0) {
    actions.push({
      priority: "high",
      title: `${risk.high_risk_count} customers at high churn risk`,
      description: `Avg risk score: ${risk.avg_risk_score.toFixed(0)}/100. No revenue data connected — financial impact unknown. Prioritise outreach to these accounts.`,
      href: "/app/customers",
      linkLabel: "View at-risk customers →",
    });
  }

  // Top cluster → bulk action
  if (clusters[0]) {
    actions.push({
      priority: "high",
      title: `Address cluster: "${clusters[0].cluster_label}"`,
      description: `${clusters[0].size} complaints share this pattern. A single bulk reply + product fix here closes more tickets than handling them individually.`,
      href: `/app/complaints?category=${clusters[0].top_category}`,
      linkLabel: "View affected complaints →",
    });
  }

  // Sentiment worsening → escalation
  if (pulse?.sentiment_trend.direction === "worsening") {
    actions.push({
      priority: "high",
      title: "Halt sentiment decline before it reaches social media",
      description: `Sentiment dropped from ${pulse.sentiment_trend.previous_avg.toFixed(2)} to ${pulse.sentiment_trend.current_avg.toFixed(2)}. Assign a senior resolver to the worst-rated open tickets today.`,
      href: "/app/complaints?priority=critical",
      linkLabel: "View critical tickets →",
    });
  }

  // Top theme from ops
  const topTheme = ops?.top_themes?.[0];
  if (topTheme && topTheme.pct > 30) {
    actions.push({
      priority: "medium",
      title: `Fix root cause of "${topTheme.theme}" complaints`,
      description: `${topTheme.pct}% of complaints this week are in one category — a product or process fix here has outsized leverage on complaint volume.`,
      href: "/app/copilot",
      linkLabel: "Ask Copilot for root cause →",
    });
  }

  return actions.slice(0, 4);
}

function SentimentArrow({ direction }: { direction: string }) {
  if (direction === "improving") return <TrendingUp className="size-4 text-green-500" />;
  if (direction === "worsening") return <TrendingDown className="size-4 text-red-500" />;
  return <span className="text-gray-400 text-xs">→ stable</span>;
}

interface AcknowledgeModalProps {
  cluster: Cluster | null;
  onClose: () => void;
  onDone: (clusterId: string) => void;
}

function AcknowledgeModal({ cluster, onClose, onDone }: AcknowledgeModalProps) {
  const [action, setAction] = useState("bulk_reply");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!cluster) return;
    setSaving(true);
    try {
      await api.intelligence.acknowledgeCluster(cluster.id, action, note);
      toast.success("Cluster acknowledged");
      onDone(cluster.id);
      onClose();
    } catch {
      toast.error("Failed to acknowledge cluster");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!cluster} onOpenChange={onClose}>
      <DialogContent className="dark:bg-gray-900 dark:border-gray-800">
        <DialogHeader>
          <DialogTitle className="dark:text-white">Acknowledge Cluster</DialogTitle>
        </DialogHeader>
        {cluster && (
          <div className="space-y-4">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium text-gray-900 dark:text-gray-100">{cluster.cluster_label}</span>
              {" "}— {cluster.size} complaints
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Action</label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value)}
                className="w-full border border-gray-200 dark:border-gray-700 rounded-md px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
                <option value="bulk_reply">Send bulk reply to affected customers</option>
                <option value="escalate">Escalate all complaints in cluster</option>
                <option value="create_task">Create internal task</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Note (optional)</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 dark:border-gray-700 rounded-md px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 resize-none"
                placeholder="Add a note for your team…"
              />
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="dark:border-gray-700">
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Acknowledge"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function Intelligence() {
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [ops, setOps] = useState<OpsData | null>(null);
  const [risk, setRisk] = useState<RiskData | null>(null);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [coverage, setCoverage] = useState<{ actual: number; estimated: number; unknown: number; total: number; coverage_pct: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [clusteringRunning, setClusteringRunning] = useState(false);
  const [acknowledgeTarget, setAcknowledgeTarget] = useState<Cluster | null>(null);
  const [acknowledgedIds, setAcknowledgedIds] = useState<Set<string>>(new Set());

  const load = async () => {
    setLoading(true);
    try {
      const [pulseData, opsData, riskData, clusterData, coverageData] = await Promise.all([
        api.intelligence.pulse().catch(() => null),
        api.intelligence.operations().catch(() => null),
        api.intelligence.revenueRisk().catch(() => null),
        api.intelligence.clusters(30).catch(() => []),
        api.intelligence.dataCoverage().catch(() => null),
      ]);
      if (pulseData) setPulse(pulseData);
      if (opsData) setOps(opsData);
      if (riskData) setRisk(riskData);
      setClusters(clusterData);
      if (coverageData) setCoverage(coverageData);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const topSpike = pulse?.new_complaint_spikes?.[0] ?? ops?.spikes?.[0] ?? null;
  const topCluster = clusters[0] ?? null;
  const recommendedActions = deriveActions(ops, clusters, risk, pulse);

  const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const forecastChartData = Array.from({ length: 7 }, (_, i) => {
    const base = ops ? Math.max(0, Math.round(ops.total_complaints / 7 * (0.8 + (i * 0.06)))) : 0;
    return {
      day: dayLabels[i],
      predicted: base,
      lower: Math.round(base * 0.70),
      upper: Math.round(base * 1.40),
    };
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="size-6 text-blue-600" />
          <h1 className="text-xl font-semibold dark:text-white">Intelligence Hub</h1>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="dark:border-gray-700">
          <RefreshCw className={`size-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Spike alert banner */}
      {topSpike && (
        <div className="flex items-center gap-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-4 py-3">
          <AlertTriangle className="size-5 text-amber-600 shrink-0" />
          <div className="text-sm text-amber-800 dark:text-amber-200">
            {topSpike.type === "volume_spike"
              ? `Volume spike detected — ${(topSpike as { hour_count?: number }).hour_count ?? "?"} complaints in the last hour (severity: ${topSpike.severity})`
              : `Sentiment drop detected — avg sentiment ${(topSpike as { avg_sentiment?: number }).avg_sentiment?.toFixed(2) ?? "?"} (severity: ${topSpike.severity})`}
          </div>
          <Badge
            variant="outline"
            className={`ml-auto shrink-0 ${topSpike.severity === "high" ? "border-red-400 text-red-600" : "border-amber-400 text-amber-600"}`}
          >
            {topSpike.severity}
          </Badge>
        </div>
      )}

      {/* Action Engine */}
      {recommendedActions.length > 0 && (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
              <Zap className="size-4 text-yellow-500" />
              Recommended Actions
              <Badge variant="secondary" className="text-[10px] ml-1">{recommendedActions.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recommendedActions.map((action, i) => (
                <div
                  key={i}
                  className={`flex items-start gap-3 p-3 rounded-lg border ${
                    action.priority === "urgent"
                      ? "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10"
                      : action.priority === "high"
                      ? "border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/10"
                      : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40"
                  }`}
                >
                  <div className="shrink-0 mt-0.5">
                    <span className={`inline-block text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                      action.priority === "urgent"
                        ? "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
                        : action.priority === "high"
                        ? "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                    }`}>
                      {action.priority}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold dark:text-white">{action.title}</p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 leading-relaxed">{action.description}</p>
                    <Link to={action.href} className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mt-1.5">
                      {action.linkLabel}
                      <ArrowRight className="size-3" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="size-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
              <IndianRupee className="size-5 text-red-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {risk?.has_revenue_data ? "Revenue at Risk" : "Customer Risk Index"}
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
              <p className="text-xl font-bold dark:text-white">
                {risk
                  ? risk.has_revenue_data
                    ? formatINR(risk.total_revenue_at_risk)
                    : `${risk.high_risk_count} accounts`
                  : "—"}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="size-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
              <Layers className="size-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Top Complaint Cluster</p>
              <p className="text-sm font-semibold dark:text-white line-clamp-1">
                {topCluster ? `${topCluster.cluster_label} (${topCluster.size})` : "No clusters yet"}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="size-10 rounded-full bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center shrink-0">
              <Users className="size-5 text-orange-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Churn Risk Customers</p>
              <p className="text-xl font-bold dark:text-white">
                {pulse ? pulse.churn_risk_customers.length : "—"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Complaint Clusters */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
              <Layers className="size-4 text-blue-500" />
              Complaint Clusters
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {clusters.length === 0 ? (
              <div className="py-6 text-center space-y-3">
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  No clusters computed yet. Group complaints into themes automatically.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={clusteringRunning}
                  className="dark:border-gray-700"
                  onClick={async () => {
                    setClusteringRunning(true);
                    try {
                      await api.intelligence.runClustering(30);
                      toast.success("Clustering started — results will appear in ~30 seconds");
                      setTimeout(() => {
                        api.intelligence.clusters(30).catch(() => []).then(setClusters);
                        setClusteringRunning(false);
                      }, 30000);
                    } catch {
                      toast.error("Failed to start clustering");
                      setClusteringRunning(false);
                    }
                  }}
                >
                  {clusteringRunning ? (
                    <><RefreshCw className="size-3.5 mr-1.5 animate-spin" />Running…</>
                  ) : (
                    <><Layers className="size-3.5 mr-1.5" />Run Clustering</>
                  )}
                </Button>
              </div>
            ) : (
              clusters.slice(0, 5).map((cluster) => (
                <div
                  key={cluster.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium dark:text-white truncate">
                        {cluster.cluster_label}
                      </span>
                      <Badge variant="secondary" className="shrink-0 text-xs">
                        {cluster.size} complaints
                      </Badge>
                      {acknowledgedIds.has(cluster.id) && (
                        <CheckCircle2 className="size-4 text-green-500 shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {cluster.summary}
                    </p>
                    <div className="flex items-center gap-3 mt-2">
                      <Link
                        to={`/app/complaints?category=${cluster.top_category}`}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View complaints
                      </Link>
                      {!acknowledgedIds.has(cluster.id) && (
                        <button
                          onClick={() => setAcknowledgeTarget(cluster)}
                          className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                        >
                          Acknowledge →
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Customer Pulse */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
              <BarChart3 className="size-4 text-purple-500" />
              Customer Pulse (Last 7 Days)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {pulse ? (
              <>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Sentiment trend:</span>
                  <SentimentArrow direction={pulse.sentiment_trend.direction} />
                  <span className="font-medium dark:text-white capitalize">
                    {pulse.sentiment_trend.direction}
                  </span>
                  <span className="text-xs text-gray-400">
                    ({pulse.sentiment_trend.current_avg.toFixed(2)} vs {pulse.sentiment_trend.previous_avg.toFixed(2)})
                  </span>
                </div>
                <div className="space-y-1.5">
                  {pulse.top_issues.slice(0, 5).map((issue) => (
                    <div key={issue.category} className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full"
                          style={{
                            width: `${Math.min(100, (issue.count / (pulse.top_issues[0]?.count || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs w-20 truncate text-gray-600 dark:text-gray-400 capitalize">
                        {issue.category}
                      </span>
                      <span className="text-xs font-medium dark:text-white w-6 text-right">{issue.count}</span>
                    </div>
                  ))}
                </div>
                {pulse.suggested_actions.length > 0 && (
                  <div className="mt-3 pt-3 border-t dark:border-gray-800">
                    <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Suggested Actions</p>
                    <ul className="space-y-1">
                      {pulse.suggested_actions.map((action, i) => (
                        <li key={i} className="text-xs text-gray-700 dark:text-gray-300 flex gap-1.5">
                          <span className="text-blue-500 shrink-0">•</span>
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-gray-400 py-4 text-center">Loading pulse data…</p>
            )}
          </CardContent>
        </Card>

        {/* Revenue at Risk / Customer Risk Index */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
              <IndianRupee className="size-4 text-red-500" />
              {risk?.has_revenue_data ? "Revenue at Risk" : "Customer Risk Index"}
              {risk && (
                <span className={`ml-auto text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                  risk.confidence === "high"
                    ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                    : risk.confidence === "medium"
                    ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400"
                    : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                }`}>
                  {risk.confidence} confidence
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {risk && risk.high_risk_customers.length > 0 ? (
              <div className="space-y-2">
                {risk.has_revenue_data ? (
                  <>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                      {risk.confidence === "medium" && <span className="text-sm font-normal text-gray-400 mr-1">Est.</span>}
                      {formatINR(risk.total_revenue_at_risk)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Across {risk.high_risk_count} high-risk accounts · avg risk {risk.avg_risk_score.toFixed(0)}/100
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                      {risk.high_risk_count} accounts
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Avg risk score {risk.avg_risk_score.toFixed(0)}/100 · no revenue data connected
                    </p>
                  </>
                )}
                <p className="text-[11px] text-gray-400 dark:text-gray-600 mt-1 leading-relaxed">
                  {risk.confidence === "high"
                    ? "Based on actual customer revenue data."
                    : risk.confidence === "medium"
                    ? "Revenue estimate based on model assumptions — connect a revenue integration for higher accuracy."
                    : "No revenue data available. Connect Stripe, Razorpay, or enter customer values manually to see financial impact."}
                </p>
                <div className="space-y-2 mt-3">
                  {risk.high_risk_customers.slice(0, 5).map((c, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-xs dark:text-gray-300">{c.customer_email}</p>
                      </div>
                      {c.revenue_at_risk > 0 ? (
                        <span className="text-xs font-medium text-red-600 dark:text-red-400 shrink-0">
                          {formatINR(c.revenue_at_risk)}
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-orange-600 dark:text-orange-400 shrink-0">
                          risk {c.risk_score.toFixed(0)}
                        </span>
                      )}
                      <Badge
                        variant="outline"
                        className="shrink-0 text-[10px] border-orange-300 text-orange-600"
                      >
                        {Math.round(c.churn_probability * 100)}%
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">
                {risk ? "No high-risk accounts detected" : "Loading…"}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Revenue Data Coverage */}
        {coverage && (
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
                <IndianRupee className="size-4 text-blue-500" />
                Revenue Data Coverage
                <span className="ml-auto text-xs font-normal text-gray-400">{coverage.total} customers</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-green-500 transition-all"
                    style={{ width: `${coverage.total > 0 ? (coverage.actual / coverage.total) * 100 : 0}%` }}
                  />
                  <div
                    className="h-full bg-yellow-400 transition-all"
                    style={{ width: `${coverage.total > 0 ? (coverage.estimated / coverage.total) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-xs font-semibold dark:text-white shrink-0">{coverage.coverage_pct}%</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-green-500" /> Actual ({coverage.actual})</span>
                <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-yellow-400" /> Estimated ({coverage.estimated})</span>
                <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-gray-300 dark:bg-gray-600" /> No data ({coverage.unknown})</span>
              </div>
              {coverage.coverage_pct < 50 && (
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  Revenue risk calculations cover {coverage.coverage_pct}% of customers. Connect Stripe or Razorpay in Settings → Connections to improve accuracy.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Operations Signals */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold dark:text-white flex items-center gap-2">
              <TrendingUp className="size-4 text-green-500" />
              Operations Signals (7d)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {ops ? (
              <div className="space-y-3">
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={forecastChartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorPred" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorBand" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#93c5fd" stopOpacity={0.20} />
                          <stop offset="95%" stopColor="#93c5fd" stopOpacity={0.05} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                      <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip formatter={(v: number, name: string) => [v, name === "upper" ? "Upper bound" : name === "lower" ? "Lower bound" : "Predicted"]} />
                      <Area type="monotone" dataKey="upper" stroke="none" fill="url(#colorBand)" strokeWidth={0} />
                      <Area type="monotone" dataKey="lower" stroke="none" fill="white" fillOpacity={0.4} strokeWidth={0} />
                      <Area type="monotone" dataKey="predicted" stroke="#3b82f6" fill="url(#colorPred)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-1.5">
                  {ops.top_themes.slice(0, 4).map((theme) => (
                    <div key={theme.theme} className="flex items-center gap-2 text-xs">
                      <span className="flex-1 capitalize text-gray-700 dark:text-gray-300">{theme.theme}</span>
                      <span className="text-gray-500">{theme.count} complaints</span>
                      <Badge variant="secondary" className="text-[10px]">{theme.pct}%</Badge>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400 py-4 text-center">Loading operations data…</p>
            )}
          </CardContent>
        </Card>
      </div>

      <AcknowledgeModal
        cluster={acknowledgeTarget}
        onClose={() => setAcknowledgeTarget(null)}
        onDone={(id) => setAcknowledgedIds((prev) => new Set([...prev, id]))}
      />
    </div>
  );
}

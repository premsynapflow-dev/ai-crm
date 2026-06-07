import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { ScrollArea } from "../components/ui/scroll-area";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import {
  Search,
  Layers,
  FileText,
  GitBranch,
  Users,
  ChevronRight,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  IndianRupee,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import { Link } from "react-router";
import { toast } from "sonner";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

type Cluster = Awaited<ReturnType<typeof api.intelligence.clusters>>[number];
type ClusterComplaints = Awaited<ReturnType<typeof api.intelligence.clusterComplaints>>;

interface RootCauseData {
  why: {
    root_cause_insights: string[];
    trending_categories: { category: string; change_percentage: number }[];
  };
  correlational_signals?: Array<{
    category: string;
    hypothesis: string;
    confidence: number;
  }>;
}

function sentimentLabel(s: number | null): { label: string; color: string } {
  if (s === null) return { label: "Unknown", color: "text-gray-400" };
  if (s > 0.2) return { label: "Positive", color: "text-green-600 dark:text-green-400" };
  if (s < -0.2) return { label: "Negative", color: "text-red-600 dark:text-red-400" };
  return { label: "Neutral", color: "text-gray-500 dark:text-gray-400" };
}

function priorityColor(p: string) {
  if (p === "critical") return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
  if (p === "high") return "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300";
  if (p === "medium") return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400";
  return "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300";
}

type Tab = "overview" | "evidence" | "root-cause" | "customers";

export function Investigations() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();

  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("cluster_id"));
  const [clusterDetail, setClusterDetail] = useState<ClusterComplaints | null>(null);
  const [rootCause, setRootCause] = useState<RootCauseData | null>(null);
  const [pulse, setPulse] = useState<Awaited<ReturnType<typeof api.intelligence.pulse>> | null>(null);
  const [risk, setRisk] = useState<Awaited<ReturnType<typeof api.intelligence.revenueRisk>> | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);
  const [acknowledgedIds, setAcknowledgedIds] = useState<Set<string>>(new Set());

  const apiKey = user?.apiKey || "";

  async function loadClusters() {
    setLoading(true);
    try {
      const [clusterData, pulseData, riskData] = await Promise.all([
        api.intelligence.clusters(30).catch(() => []),
        api.intelligence.pulse().catch(() => null),
        api.intelligence.revenueRisk().catch(() => null),
      ]);
      setClusters(clusterData);
      if (pulseData) setPulse(pulseData);
      if (riskData) setRisk(riskData);
    } finally {
      setLoading(false);
    }
  }

  async function loadClusterDetail(id: string) {
    setDetailLoading(true);
    setClusterDetail(null);
    setRootCause(null);
    try {
      const detail = await api.intelligence.clusterComplaints(id, 50);
      setClusterDetail(detail);

      if (apiKey) {
        try {
          const resp = await fetch(`${API_BASE}/api/v1/executive/summary?days=7`, {
            headers: { "x-api-key": apiKey },
          });
          if (resp.ok) setRootCause(await resp.json());
        } catch {
          // optional enrichment
        }
      }
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => { loadClusters(); }, []);

  useEffect(() => {
    if (selectedId) {
      loadClusterDetail(selectedId);
      setTab("overview");
    }
  }, [selectedId]);

  const selectedCluster = clusters.find((c) => c.id === selectedId) ?? null;

  function selectCluster(id: string) {
    setSelectedId(id);
    setSearchParams({ cluster_id: id }, { replace: true });
  }

  async function handleAcknowledge(action: string) {
    if (!selectedId) return;
    setAcknowledging(true);
    try {
      await api.intelligence.acknowledgeCluster(selectedId, action, "");
      setAcknowledgedIds((prev) => new Set([...prev, selectedId]));
      toast.success("Issue acknowledged");
    } catch {
      toast.error("Failed to acknowledge");
    } finally {
      setAcknowledging(false);
    }
  }

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "overview", label: "Overview", icon: FileText },
    { id: "evidence", label: "Signal Evidence", icon: Layers },
    { id: "root-cause", label: "Root Cause", icon: GitBranch },
    { id: "customers", label: "Customer Impact", icon: Users },
  ];

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0 -m-6 overflow-hidden">
      {/* Left panel — cluster list */}
      <aside className="w-72 shrink-0 border-r dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col">
        <div className="p-4 border-b dark:border-gray-800">
          <div className="flex items-center gap-2">
            <Search className="size-5 text-blue-600" />
            <h1 className="text-base font-semibold dark:text-white">Investigations</h1>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Select an issue cluster to investigate</p>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-3 space-y-1.5">
            {loading ? (
              [...Array(5)].map((_, i) => (
                <div key={i} className="h-16 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
              ))
            ) : clusters.length === 0 ? (
              <div className="py-8 text-center px-4">
                <Layers className="size-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
                <p className="text-xs text-gray-500 dark:text-gray-400">No clusters yet.</p>
                <Link to="/app/intelligence" className="text-xs text-blue-600 hover:underline mt-1 block">
                  Run clustering →
                </Link>
              </div>
            ) : (
              clusters.map((cluster) => {
                const isSelected = cluster.id === selectedId;
                const isAcknowledged = acknowledgedIds.has(cluster.id);
                const severity = cluster.size > 20 ? "high" : cluster.size > 8 ? "medium" : "low";
                return (
                  <button
                    key={cluster.id}
                    onClick={() => selectCluster(cluster.id)}
                    className={`w-full text-left rounded-lg p-3 transition-colors ${
                      isSelected
                        ? "bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                        : "hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className={`shrink-0 mt-0.5 text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${
                        severity === "high" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                          : severity === "medium" ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300"
                          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
                      }`}>
                        {severity}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium dark:text-white line-clamp-1">{cluster.cluster_label}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {cluster.size} signals · {cluster.top_category}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {isAcknowledged && <CheckCircle2 className="size-3.5 text-green-500" />}
                        {isSelected && <ChevronRight className="size-3.5 text-blue-500" />}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </ScrollArea>
      </aside>

      {/* Right panel — detail */}
      <main className="flex-1 flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950">
        {!selectedCluster ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Search className="size-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-500 dark:text-gray-400">Select an issue cluster to begin your investigation</p>
            </div>
          </div>
        ) : (
          <>
            {/* Detail header */}
            <div className="bg-white dark:bg-gray-900 border-b dark:border-gray-800 px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-lg font-semibold dark:text-white">{selectedCluster.cluster_label}</h2>
                    <Badge variant="secondary">{selectedCluster.size} signals</Badge>
                    <Badge variant="outline" className="capitalize dark:border-gray-700">
                      {selectedCluster.top_category}
                    </Badge>
                    {acknowledgedIds.has(selectedCluster.id) && (
                      <Badge variant="outline" className="border-green-400 text-green-600 dark:text-green-400">
                        <CheckCircle2 className="size-3 mr-1" /> Acknowledged
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {selectedCluster.period_start} → {selectedCluster.period_end}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Link to={`/app/copilot?q=${encodeURIComponent(`What is causing the "${selectedCluster.cluster_label}" issue?`)}`}>
                    <Button variant="outline" size="sm" className="dark:border-gray-700 gap-1.5">
                      <Sparkles className="size-3.5 text-blue-500" />
                      Ask Copilot
                    </Button>
                  </Link>
                  {!acknowledgedIds.has(selectedCluster.id) && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="dark:border-gray-700"
                      disabled={acknowledging}
                      onClick={() => handleAcknowledge("create_task")}
                    >
                      {acknowledging ? <RefreshCw className="size-3.5 animate-spin" /> : "Acknowledge"}
                    </Button>
                  )}
                </div>
              </div>

              {/* Tabs */}
              <div className="flex gap-1 mt-4">
                {tabs.map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    onClick={() => setTab(id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                      tab === id
                        ? "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 font-medium"
                        : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                    }`}
                  >
                    <Icon className="size-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab content */}
            <ScrollArea className="flex-1">
              <div className="p-6 space-y-4">
                {detailLoading ? (
                  [...Array(3)].map((_, i) => (
                    <Card key={i} className="animate-pulse dark:bg-gray-900 dark:border-gray-800">
                      <CardContent className="h-24" />
                    </Card>
                  ))
                ) : (
                  <>
                    {/* Overview tab */}
                    {tab === "overview" && (
                      <div className="space-y-4">
                        <Card className="dark:bg-gray-900 dark:border-gray-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm dark:text-white">Issue Summary</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                              {clusterDetail?.cluster?.summary || selectedCluster.summary || "No summary available."}
                            </p>
                            <div className="grid grid-cols-2 gap-4 mt-4">
                              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                <p className="text-2xl font-bold dark:text-white">{selectedCluster.size}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Total Signals</p>
                              </div>
                              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                <p className="text-2xl font-bold capitalize dark:text-white">{selectedCluster.top_category}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Primary Category</p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>

                        {/* Severity assessment */}
                        <Card className="dark:bg-gray-900 dark:border-gray-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm dark:text-white flex items-center gap-2">
                              <AlertTriangle className="size-4 text-amber-500" />
                              Severity Assessment
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-2">
                            {selectedCluster.size > 20 && (
                              <div className="flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
                                <span className="size-1.5 rounded-full bg-red-500 shrink-0" />
                                High volume — {selectedCluster.size} signals indicate a systemic issue
                              </div>
                            )}
                            {selectedCluster.size > 8 && selectedCluster.size <= 20 && (
                              <div className="flex items-center gap-2 text-sm text-orange-700 dark:text-orange-300">
                                <span className="size-1.5 rounded-full bg-orange-500 shrink-0" />
                                Moderate pattern — worth investigating before it escalates
                              </div>
                            )}
                            <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                              <span className="size-1.5 rounded-full bg-blue-500 shrink-0" />
                              Category: {selectedCluster.top_category} — review affected workflows
                            </div>
                            <Link to="/app/radar" className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-2">
                              <TrendingUp className="size-3" />
                              View on Issue Radar
                            </Link>
                          </CardContent>
                        </Card>
                      </div>
                    )}

                    {/* Evidence tab */}
                    {tab === "evidence" && (
                      <div className="space-y-3">
                        {!clusterDetail || clusterDetail.complaints.length === 0 ? (
                          <Card className="dark:bg-gray-900 dark:border-gray-800">
                            <CardContent className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                              No complaint evidence available for this cluster.
                            </CardContent>
                          </Card>
                        ) : (
                          <>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              Showing {clusterDetail.complaints.length} of {clusterDetail.total} signals in this cluster
                            </p>
                            {clusterDetail.complaints.map((complaint) => {
                              const sent = sentimentLabel(complaint.sentiment);
                              return (
                                <Card key={complaint.id} className="dark:bg-gray-900 dark:border-gray-800">
                                  <CardContent className="p-4">
                                    <div className="flex items-start gap-3">
                                      <div className="flex-1 min-w-0">
                                        <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                                          {complaint.summary}
                                        </p>
                                        <div className="flex items-center gap-3 mt-2 text-xs text-gray-500 dark:text-gray-400 flex-wrap">
                                          <span className={`font-medium ${sent.color}`}>{sent.label}</span>
                                          {complaint.customer_email && (
                                            <span>{complaint.customer_email}</span>
                                          )}
                                          <span>{new Date(complaint.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
                                        </div>
                                      </div>
                                      <div className="flex flex-col gap-1.5 shrink-0 items-end">
                                        <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${priorityColor(complaint.priority)}`}>
                                          {complaint.priority}
                                        </span>
                                        <Link
                                          to={`/app/complaints/${complaint.id}`}
                                          className="text-xs text-blue-600 hover:underline"
                                        >
                                          View →
                                        </Link>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              );
                            })}
                          </>
                        )}
                      </div>
                    )}

                    {/* Root cause tab */}
                    {tab === "root-cause" && (
                      <div className="space-y-4">
                        {!rootCause ? (
                          <Card className="dark:bg-gray-900 dark:border-gray-800">
                            <CardContent className="py-8 text-center">
                              <p className="text-sm text-gray-500 dark:text-gray-400">
                                Root cause analysis requires API key access.
                              </p>
                            </CardContent>
                          </Card>
                        ) : (
                          <>
                            {(rootCause.why?.root_cause_insights ?? []).length > 0 && (
                              <Card className="dark:bg-gray-900 dark:border-gray-800">
                                <CardHeader className="pb-2">
                                  <CardTitle className="text-sm dark:text-white flex items-center gap-2">
                                    <GitBranch className="size-4 text-purple-500" />
                                    Probable Causes
                                  </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                  {rootCause.why.root_cause_insights.map((insight, i) => (
                                    <div key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                                      <span className="shrink-0 text-purple-500 font-bold mt-0.5">{i + 1}.</span>
                                      <p className="leading-relaxed">{insight}</p>
                                    </div>
                                  ))}
                                </CardContent>
                              </Card>
                            )}

                            {(rootCause.why?.trending_categories ?? []).length > 0 && (
                              <Card className="dark:bg-gray-900 dark:border-gray-800">
                                <CardHeader className="pb-2">
                                  <CardTitle className="text-sm dark:text-white">Trending Categories</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                  {rootCause.why.trending_categories.map((cat, i) => (
                                    <div key={i} className="flex items-center justify-between text-sm">
                                      <span className="capitalize text-gray-700 dark:text-gray-300">{cat.category}</span>
                                      <span className={cat.change_percentage > 0 ? "text-red-500 font-medium" : "text-green-500 font-medium"}>
                                        {cat.change_percentage > 0 ? "+" : ""}{cat.change_percentage.toFixed(0)}%
                                      </span>
                                    </div>
                                  ))}
                                </CardContent>
                              </Card>
                            )}

                            <Card className="border-dashed dark:bg-gray-900 dark:border-gray-700">
                              <CardContent className="p-4 text-xs text-gray-500 dark:text-gray-400">
                                These are observational associations, not confirmed causal relationships. Use the Copilot for deeper analysis.
                              </CardContent>
                            </Card>
                          </>
                        )}
                      </div>
                    )}

                    {/* Customer impact tab */}
                    {tab === "customers" && (
                      <div className="space-y-4">
                        {pulse && (
                          <Card className="dark:bg-gray-900 dark:border-gray-800">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-sm dark:text-white flex items-center gap-2">
                                <Users className="size-4 text-orange-500" />
                                Customer Sentiment
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                              <div className="flex items-center gap-3 text-sm">
                                <span className="text-gray-500 dark:text-gray-400">Trend:</span>
                                <span className={`font-medium capitalize ${
                                  pulse.sentiment_trend.direction === "worsening"
                                    ? "text-red-600 dark:text-red-400"
                                    : pulse.sentiment_trend.direction === "improving"
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-gray-600 dark:text-gray-300"
                                }`}>
                                  {pulse.sentiment_trend.direction}
                                </span>
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">
                                Avg: {pulse.sentiment_trend.current_avg.toFixed(2)} (was {pulse.sentiment_trend.previous_avg.toFixed(2)})
                              </div>
                            </CardContent>
                          </Card>
                        )}

                        {(pulse?.churn_risk_customers ?? []).length > 0 && (
                          <Card className="dark:bg-gray-900 dark:border-gray-800">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-sm dark:text-white">High Churn Risk Customers</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                              {pulse!.churn_risk_customers.slice(0, 8).map((c, i) => (
                                <div key={i} className="flex items-center justify-between text-sm py-1 border-b dark:border-gray-800 last:border-0">
                                  <span className="text-gray-700 dark:text-gray-300 truncate">{c.email || "Unknown"}</span>
                                  <Badge variant="outline" className="border-red-300 text-red-600 dark:text-red-400 text-xs shrink-0 ml-2">
                                    {Math.round((c.churn_probability ?? 0) * 100)}% risk
                                  </Badge>
                                </div>
                              ))}
                              <Link to="/app/customers" className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-2">
                                <Users className="size-3" />
                                View all customers
                              </Link>
                            </CardContent>
                          </Card>
                        )}

                        {risk && risk.has_revenue_data && (
                          <Card className="dark:bg-gray-900 dark:border-gray-800">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-sm dark:text-white flex items-center gap-2">
                                <IndianRupee className="size-4 text-red-500" />
                                Revenue Exposure
                              </CardTitle>
                            </CardHeader>
                            <CardContent>
                              <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                                {risk.total_revenue_at_risk >= 100000
                                  ? `₹${(risk.total_revenue_at_risk / 100000).toFixed(1)}L`
                                  : `₹${risk.total_revenue_at_risk.toLocaleString()}`}
                              </div>
                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                Across {risk.high_risk_count} high-risk accounts
                              </p>
                              <Link to="/app/customers" className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-3">
                                View at-risk customers <ChevronRight className="size-3" />
                              </Link>
                            </CardContent>
                          </Card>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </ScrollArea>
          </>
        )}
      </main>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AlertTriangle, HelpCircle, DollarSign, Zap, RefreshCw, GitBranch, Activity } from "lucide-react";
import { useAuth } from "../lib/auth-context";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

interface WhatBroke {
  issue: string;
  count: number;
  change_pct: number;
}

interface WhyData {
  root_cause_insights: string[];
  trending_categories: { category: string; change_percentage: number }[];
}

interface CostData {
  revenue_at_risk: number;
  high_risk_customers: number;
  currency: string;
}

interface ActionData {
  narrative: string;
  top_recommendations: string[];
}

interface TopIssue {
  category: string;
  current_count: number;
  change_percentage: number;
  percentage_of_total: number;
}

interface FullAnalytics {
  total_complaints: number;
  previous_period_total: number;
  overall_change_pct: number;
  top_issues: TopIssue[];
  resolution_rates: Record<string, number>;
}

interface CausalChain {
  category: string;
  change_percentage: number;
  hypotheses: string[];
  common_entities: Record<string, Array<{ value: string; count: number; frequency: number }>>;
}

interface ExecutiveSummary {
  period_days: number;
  what_broke: WhatBroke;
  why: WhyData;
  cost: CostData;
  action: ActionData;
  full_analytics: FullAnalytics;
  causal_analysis?: CausalChain[];
  generated_at: string;
  cached?: boolean;
}

export function Executive() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  const [refreshing, setRefreshing] = useState(false);

  const apiKey = user?.apiKey || "";

  async function fetchSummary(forceRefresh = false) {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ days: String(days) });
      if (forceRefresh) params.set("force_refresh", "true");
      const resp = await fetch(`${API_BASE}/api/v1/executive/summary?${params}`, {
        headers: { "x-api-key": apiKey },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setSummary(data);
    } catch (e: any) {
      setError(e.message || "Failed to load executive summary");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    fetchSummary();
  }, [days, apiKey]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchSummary(true);
  };

  const fmtPct = (n: number | undefined | null) => {
    const v = n ?? 0;
    return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
  };

  const changeColor = (pct: number | undefined | null) =>
    (pct ?? 0) > 0
      ? "text-red-600 dark:text-red-400"
      : "text-green-600 dark:text-green-400";

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold dark:text-white">Operational Health</h1>
          <p className="text-gray-500 dark:text-gray-400">Loading summary…</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-40" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold dark:text-white">Operational Health</h1>
          <p className="text-gray-500 dark:text-gray-400">
            AI-generated operational summary · Last {days} days
            {summary?.cached && (
              <span className="ml-2 text-xs text-gray-400">(cached)</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            {[7, 14, 30].map((d) => (
              <Button
                key={d}
                variant={days === d ? "default" : "outline"}
                size="sm"
                onClick={() => setDays(d)}
              >
                {d}d
              </Button>
            ))}
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`size-4 mr-1 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
          <CardContent className="pt-4 text-red-700 dark:text-red-300">{error}</CardContent>
        </Card>
      )}

      {summary && (
        <>
          {/* Operational Health Score */}
          {(() => {
            const changeVal = summary.what_broke?.change_pct ?? 0;
            const issueCount = summary.full_analytics?.total_complaints ?? 0;
            const prevCount = summary.full_analytics?.previous_period_total ?? issueCount;
            const trendPenalty = changeVal > 20 ? 20 : changeVal > 10 ? 10 : 0;
            const volumePenalty = Math.min(30, Math.round(issueCount / Math.max(prevCount, 1) * 10));
            const costPenalty = summary.cost?.revenue_at_risk > 0 ? 15 : 0;
            const score = Math.max(20, Math.min(100, 100 - trendPenalty - volumePenalty - costPenalty));
            const grade = score >= 80 ? { label: "Good", color: "text-green-600 dark:text-green-400" }
              : score >= 60 ? { label: "Fair", color: "text-yellow-600 dark:text-yellow-400" }
              : score >= 40 ? { label: "At Risk", color: "text-orange-600 dark:text-orange-400" }
              : { label: "Critical", color: "text-red-600 dark:text-red-400" };
            return (
              <Card className="dark:bg-gray-900 dark:border-gray-800">
                <CardContent className="p-4 flex items-center gap-6">
                  <div className="size-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                    <Activity className="size-6 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Operational Health Score</p>
                    <div className="flex items-baseline gap-2">
                      <span className={`text-3xl font-bold ${grade.color}`}>{score}</span>
                      <span className={`text-sm font-medium ${grade.color}`}>{grade.label}</span>
                      <span className="text-xs text-gray-400">/ 100</span>
                    </div>
                  </div>
                  <div className="ml-auto text-xs text-gray-500 dark:text-gray-400 hidden md:block">
                    Based on signal volume, trend, and revenue risk
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {/* 4-card executive view */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* What Broke */}
            <Card className="border-orange-200 dark:border-orange-800">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-orange-700 dark:text-orange-400">
                  <AlertTriangle className="size-5" />
                  What Broke
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-semibold dark:text-white capitalize">
                  {summary.what_broke?.issue || "No significant issues detected"}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {summary.what_broke?.count ?? 0} complaints ·{" "}
                  <span className={changeColor(summary.what_broke?.change_pct)}>
                    {fmtPct(summary.what_broke?.change_pct)} vs prior period
                  </span>
                </p>
                {(summary.why?.trending_categories?.length ?? 0) > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {summary.why.trending_categories.map((t) => (
                      <Badge key={t.category} variant="outline" className="text-orange-600 border-orange-300">
                        {t.category} {fmtPct(t.change_percentage)}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Why */}
            <Card className="border-blue-200 dark:border-blue-800">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-blue-700 dark:text-blue-400">
                  <HelpCircle className="size-5" />
                  Why
                </CardTitle>
              </CardHeader>
              <CardContent>
                {(summary.why?.root_cause_insights?.length ?? 0) > 0 ? (
                  <ul className="space-y-1">
                    {summary.why.root_cause_insights.map((insight, i) => (
                      <li key={i} className="text-sm text-gray-800 dark:text-gray-200 flex gap-2">
                        <span className="text-blue-400 shrink-0">•</span>
                        {insight}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">
                    No significant trends detected in this period.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Cost */}
            <Card className="border-red-200 dark:border-red-800">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-red-700 dark:text-red-400">
                  <DollarSign className="size-5" />
                  Revenue at Risk
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-red-600 dark:text-red-400">
                  ₹{(summary.cost?.revenue_at_risk ?? 0).toLocaleString("en-IN", {
                    maximumFractionDigits: 0,
                  })}
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {summary.cost?.high_risk_customers ?? 0} high-risk customers (churn score ≥ 70)
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-600 mt-1">
                  Calculated as customer LTV × churn probability. LTV estimated from resolved tickets × per-plan rate.
                </p>
                <div className="mt-3 space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 dark:text-gray-400">Total complaints</span>
                    <span className="font-medium dark:text-white">
                      {summary.full_analytics?.total_complaints ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 dark:text-gray-400">vs prior period</span>
                    <span className={`font-medium ${changeColor(summary.full_analytics?.overall_change_pct)}`}>
                      {fmtPct(summary.full_analytics?.overall_change_pct)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Action */}
            <Card className="border-green-200 dark:border-green-800">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-green-700 dark:text-green-400">
                  <Zap className="size-5" />
                  Recommended Action
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                  {summary.action?.narrative || "No specific action recommended at this time."}
                </p>
                {(summary.action?.top_recommendations?.length ?? 0) > 0 && (
                  <ul className="space-y-1">
                    {summary.action.top_recommendations.map((rec, i) => (
                      <li key={i} className="text-xs text-gray-600 dark:text-gray-400 flex gap-2">
                        <span className="text-green-400 shrink-0">→</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Issue Chain Analysis */}
          {(summary.causal_analysis?.length ?? 0) > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 dark:text-white">
                  <GitBranch className="size-5 text-purple-600" />
                  Probable Root Causes
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {summary.causal_analysis!.map((chain) => (
                  <div key={chain.category} className="border dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-semibold capitalize dark:text-white">{chain.category}</span>
                      <Badge
                        variant="outline"
                        className={chain.change_percentage > 0 ? "border-red-300 text-red-600" : "border-green-300 text-green-600"}
                      >
                        {chain.change_percentage > 0 ? "+" : ""}{chain.change_percentage.toFixed(1)}% vs prior period
                      </Badge>
                    </div>
                    {chain.hypotheses.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">AI Root Cause Hypotheses</p>
                        {chain.hypotheses.map((h, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
                            <span className="mt-0.5 shrink-0 text-purple-500 font-mono text-xs">
                              {String.fromCharCode(65 + i)}.
                            </span>
                            {h}
                          </div>
                        ))}
                      </div>
                    )}
                    {Object.keys(chain.common_entities).length > 0 && (
                      <div className="mt-3 pt-3 border-t dark:border-gray-700">
                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Common Signals</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(chain.common_entities).flatMap(([_type, items]) =>
                            items.slice(0, 3).map((item) => (
                              <Badge key={item.value} variant="secondary" className="text-xs">
                                {item.value} <span className="ml-1 text-gray-400">×{item.count}</span>
                              </Badge>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Top Issues table */}
          {(summary.full_analytics?.top_issues?.length ?? 0) > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="dark:text-white">Top Complaint Categories</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b dark:border-gray-700">
                        <th className="pb-2">Category</th>
                        <th className="pb-2 text-right">Count</th>
                        <th className="pb-2 text-right">Change</th>
                        <th className="pb-2 text-right">% of Total</th>
                        <th className="pb-2 text-right">Resolution</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y dark:divide-gray-800">
                      {summary.full_analytics.top_issues.map((issue) => (
                        <tr key={issue.category} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                          <td className="py-2 font-medium dark:text-white capitalize">
                            {issue.category}
                          </td>
                          <td className="py-2 text-right dark:text-gray-300">
                            {issue.current_count ?? 0}
                          </td>
                          <td className={`py-2 text-right font-medium ${changeColor(issue.change_percentage)}`}>
                            {fmtPct(issue.change_percentage)}
                          </td>
                          <td className="py-2 text-right text-gray-500 dark:text-gray-400">
                            {(issue.percentage_of_total ?? 0).toFixed(1)}%
                          </td>
                          <td className="py-2 text-right dark:text-gray-300">
                            {summary.full_analytics.resolution_rates?.[issue.category] != null
                              ? `${summary.full_analytics.resolution_rates[issue.category]}%`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          <p className="text-xs text-gray-400 text-right">
            Generated {summary.generated_at ? new Date(summary.generated_at).toLocaleString() : "—"}
          </p>
        </>
      )}
    </div>
  );
}

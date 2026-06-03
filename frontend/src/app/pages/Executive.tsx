import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AlertTriangle, TrendingUp, DollarSign, Zap, RefreshCw } from "lucide-react";
import { useAuth } from "../lib/auth-context";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

interface ExecutiveSummary {
  what_broke: string;
  why: string;
  cost: {
    revenue_at_risk: number;
    high_risk_customers: number;
  };
  action: string;
  full_analytics: {
    total_complaints: number;
    overall_change_percentage: number;
    trending_up: { category: string; change_percentage: number }[];
    top_issues: { category: string; current_count: number; change_percentage: number }[];
    resolution_rates: Record<string, number>;
  };
  generated_at: string;
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

  const changeColor = (pct: number) =>
    pct > 0 ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400";

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold dark:text-white">Executive Intelligence</h1>
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
          <h1 className="text-3xl font-bold dark:text-white">Executive Intelligence</h1>
          <p className="text-gray-500 dark:text-gray-400">
            AI-generated operational summary · Last {days} days
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
                <p className="text-gray-800 dark:text-gray-200 leading-relaxed">
                  {summary.what_broke}
                </p>
                {summary.full_analytics?.trending_up?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {summary.full_analytics.trending_up.map((t) => (
                      <Badge key={t.category} variant="outline" className="text-orange-600 border-orange-300">
                        {t.category} +{t.change_percentage.toFixed(0)}%
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
                  <TrendingUp className="size-5" />
                  Why
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-800 dark:text-gray-200 leading-relaxed">
                  {summary.why}
                </p>
              </CardContent>
            </Card>

            {/* Cost */}
            <Card className="border-red-200 dark:border-red-800">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-red-700 dark:text-red-400">
                  <DollarSign className="size-5" />
                  Cost / Revenue at Risk
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-red-600 dark:text-red-400">
                  ₹{(summary.cost?.revenue_at_risk ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {summary.cost?.high_risk_customers ?? 0} high-risk customers (churn score ≥ 70)
                </p>
                {summary.full_analytics && (
                  <div className="mt-3 space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Total complaints</span>
                      <span className="font-medium dark:text-white">{summary.full_analytics.total_complaints}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">vs prior period</span>
                      <span className={`font-medium ${changeColor(summary.full_analytics.overall_change_percentage)}`}>
                        {summary.full_analytics.overall_change_percentage > 0 ? "+" : ""}
                        {summary.full_analytics.overall_change_percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                )}
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
              <CardContent>
                <p className="text-gray-800 dark:text-gray-200 leading-relaxed">
                  {summary.action}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Top Issues table */}
          {summary.full_analytics?.top_issues?.length > 0 && (
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
                        <th className="pb-2 text-right">Resolution</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y dark:divide-gray-800">
                      {summary.full_analytics.top_issues.map((issue) => (
                        <tr key={issue.category} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                          <td className="py-2 font-medium dark:text-white capitalize">{issue.category}</td>
                          <td className="py-2 text-right dark:text-gray-300">{issue.current_count}</td>
                          <td className={`py-2 text-right font-medium ${changeColor(issue.change_percentage)}`}>
                            {issue.change_percentage > 0 ? "+" : ""}{issue.change_percentage.toFixed(1)}%
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
            Generated {new Date(summary.generated_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}

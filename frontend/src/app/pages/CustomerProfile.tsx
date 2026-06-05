import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { Progress } from "../components/ui/progress";
import { api, Customer } from "../lib/api";
import { ArrowLeft, Mail, Phone, Building, Lightbulb, CheckCircle2 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export function CustomerProfile() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [weeklyData, setWeeklyData] = useState<Array<{ week: string; complaints: number }>>([]);

  useEffect(() => {
    if (id) {
      api.customers.get(id).then((c) => {
        setCustomer(c);
        setLoading(false);
        if (c && (c.churn_risk === "high" || c.churn_risk === "medium")) {
          api.customers.getSaveRecommendations(id).then((r) => {
            if (r) setRecommendations(r.recommendations);
          }).catch(() => null);
        }
        // Load complaint history for timeline chart
        if (c?.email) {
          api.complaints.list({ search: c.email }).then((complaints) => {
            const counts: Record<string, number> = {};
            const now = Date.now();
            for (let i = 7; i >= 0; i--) {
              const d = new Date(now - i * 7 * 86400000);
              const key = `W${8 - i} ${d.toLocaleDateString("en-IN", { month: "short", day: "numeric" })}`;
              counts[key] = 0;
            }
            for (const c of complaints) {
              const ts = new Date(c.created_at).getTime();
              const weeksAgo = Math.floor((now - ts) / (7 * 86400000));
              if (weeksAgo >= 0 && weeksAgo < 8) {
                const d = new Date(now - weeksAgo * 7 * 86400000);
                const key = `W${8 - weeksAgo} ${d.toLocaleDateString("en-IN", { month: "short", day: "numeric" })}`;
                counts[key] = (counts[key] || 0) + 1;
              }
            }
            setWeeklyData(Object.entries(counts).map(([week, complaints]) => ({ week, complaints })));
          }).catch(() => null);
        }
      }).catch(() => setLoading(false));
    }
  }, [id]);

  if (loading) return <div className="p-6">Loading customer profile...</div>;
  if (!customer) return (
    <div className="p-6 space-y-4">
      <Button variant="ghost" onClick={() => navigate("/app/customers")}>
        <ArrowLeft className="size-4 mr-2" /> Back to Customers
      </Button>
      <p className="text-gray-500">Customer not found.</p>
    </div>
  );

  const churnColor = customer.churn_risk === "high" ? "text-red-600" : customer.churn_risk === "medium" ? "text-yellow-600" : "text-green-600";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/app/customers")}>
          <ArrowLeft className="size-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{customer.name}</h1>
          <p className="text-gray-600">{customer.email}</p>
        </div>
        <div className="ml-auto flex gap-2">
          <Badge className={churnColor + " bg-transparent border"}>
            {customer.churn_risk} churn risk
          </Badge>
          {(customer.tags || []).map((tag) => (
            <Badge key={tag} variant="outline">{tag}</Badge>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Identity */}
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Contact</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center gap-2">
                <Mail className="size-4 text-gray-400" />
                <span>{customer.email}</span>
              </div>
              {customer.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="size-4 text-gray-400" />
                  <span>{customer.phone}</span>
                </div>
              )}
              {customer.company_name && (
                <div className="flex items-center gap-2">
                  <Building className="size-4 text-gray-400" />
                  <span>{customer.company_name}</span>
                </div>
              )}
              <Separator />
              <div className="flex justify-between">
                <span className="text-gray-600">Type</span>
                <span className="capitalize">{customer.customer_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Last interaction</span>
                <span>{new Date(customer.last_interaction_at).toLocaleDateString()}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Risk & Health</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="flex items-center gap-1">
                    Risk Score
                    {customer.risk_score_version && (
                      <span className="text-[9px] text-gray-400 font-normal">({customer.risk_score_version})</span>
                    )}
                  </span>
                  <span className={churnColor + " font-medium"}>
                    {Math.round(customer.churn_risk_score ?? 0)}/100
                  </span>
                </div>
                <Progress value={customer.churn_risk_score ?? 0} className="h-2" />
                {customer.predicted_churn_probability != null && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Calibrated churn probability: {Math.round((customer.predicted_churn_probability ?? 0) * 100)}%
                  </p>
                )}
                {customer.risk_score_computed_at && (
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    Updated {new Date(customer.risk_score_computed_at).toLocaleDateString()}
                  </p>
                )}
              </div>

              {/* Risk Breakdown */}
              {customer.prediction_explanation && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 select-none">
                    Risk breakdown ↓
                  </summary>
                  <div className="mt-2 space-y-1.5">
                    {(["volume_risk", "sentiment_risk", "escalation_risk", "resolution_risk", "behavioral_risk"] as const).map((key) => {
                      const label = key.replace("_risk", "").replace("_", " ");
                      const cap = { volume_risk: 20, sentiment_risk: 25, escalation_risk: 20, resolution_risk: 20, behavioral_risk: 25 }[key] ?? 25;
                      const val = (customer.prediction_explanation as Record<string, number>)[key] ?? 0;
                      return (
                        <div key={key} className="flex items-center gap-2">
                          <span className="capitalize text-gray-500 dark:text-gray-400 w-24 shrink-0">{label}</span>
                          <div className="flex-1 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                            <div className="h-full bg-orange-400 rounded-full" style={{ width: `${(val / cap) * 100}%` }} />
                          </div>
                          <span className="text-gray-600 dark:text-gray-400 w-8 text-right">{val}</span>
                        </div>
                      );
                    })}
                    {(customer.prediction_explanation as Record<string, number>).loyalty_discount > 0 && (
                      <p className="text-green-600 dark:text-green-400 text-[10px]">
                        -{(customer.prediction_explanation as Record<string, number>).loyalty_discount} loyalty discount applied
                      </p>
                    )}
                  </div>
                </details>
              )}

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Avg CSAT</span>
                  <span>{(customer.avg_satisfaction_score ?? 0).toFixed(1)} / 5.0</span>
                </div>
                <Progress value={(customer.avg_satisfaction_score ?? 0) * 20} className="h-2" />
              </div>
              {customer.lifetime_value != null && customer.lifetime_value > 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">
                    {customer.customer_value_source === "actual" ? "Revenue" : customer.customer_value_source === "estimated" ? "Est. Value" : "Lifetime Value"}
                  </span>
                  <span className="font-medium">
                    {customer.revenue_risk_confidence === "medium" && <span className="text-gray-400 text-xs mr-1">Est.</span>}
                    ₹{customer.lifetime_value.toLocaleString("en-IN")}
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {recommendations.length > 0 && (
            <Card className="border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-amber-800 dark:text-amber-200">
                  <Lightbulb className="size-4" />
                  Save Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {recommendations.map((rec, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-amber-900 dark:text-amber-100">
                      <CheckCircle2 className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                      {rec}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Stats */}
        <div className="lg:col-span-2 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-3xl font-bold">{customer.total_tickets}</div>
                <p className="text-sm text-gray-500 mt-1">Total Tickets</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-3xl font-bold">{customer.open_tickets}</div>
                <p className="text-sm text-gray-500 mt-1">Open Tickets</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-3xl font-bold capitalize">
                  <span className={
                    customer.sentiment_label === "positive" ? "text-green-600" :
                    customer.sentiment_label === "negative" ? "text-red-600" : "text-gray-700"
                  }>{customer.sentiment_label}</span>
                </div>
                <p className="text-sm text-gray-500 mt-1">Sentiment</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Complaint Frequency (Last 8 Weeks)</CardTitle>
                <Link to={`/app/complaints?search=${encodeURIComponent(customer.email)}`}>
                  <Button variant="outline" size="sm">View All</Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {weeklyData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={weeklyData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                    <Tooltip formatter={(v) => [v, "Tickets"]} />
                    <Bar dataKey="complaints" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-500 text-center py-8">Loading complaint history…</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

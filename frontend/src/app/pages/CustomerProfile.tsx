import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { Progress } from "../components/ui/progress";
import { api, Customer } from "../lib/api";
import { ArrowLeft, Mail, Phone, Building, Lightbulb, CheckCircle2 } from "lucide-react";

export function CustomerProfile() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [recommendations, setRecommendations] = useState<string[]>([]);

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
                  <span>Churn Risk Score</span>
                  <span className={churnColor + " font-medium"}>
                    {Math.round(customer.churn_risk_score * 100)}%
                  </span>
                </div>
                <Progress value={customer.churn_risk_score * 100} className="h-2" />
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Avg CSAT</span>
                  <span>{customer.avg_satisfaction_score.toFixed(1)} / 5.0</span>
                </div>
                <Progress value={customer.avg_satisfaction_score * 20} className="h-2" />
              </div>
              {customer.lifetime_value != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Lifetime Value</span>
                  <span className="font-medium">₹{customer.lifetime_value.toLocaleString("en-IN")}</span>
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
                <CardTitle>Ticket History</CardTitle>
                <Link to={`/app/complaints?search=${encodeURIComponent(customer.email)}`}>
                  <Button variant="outline" size="sm">View All</Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 text-center py-4">
                View tickets for this customer in the Complaints Inbox
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

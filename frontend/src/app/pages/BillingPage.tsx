import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Check } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { toast } from "sonner";
import { api } from "../lib/api";

export function BillingPage() {
  const { user } = useAuth();
  const [usage, setUsage] = useState<{ tickets_used: number; tickets_quota: number; next_billing_date?: string } | null>(null);
  const [invoices, setInvoices] = useState<Array<{ id: string; amount: number; date: string; plan: string }>>([]);

  useEffect(() => {
    api.billing.getUsage().then(setUsage).catch(() => null);
    api.billing.getInvoices().then((d) => setInvoices(d?.invoices || [])).catch(() => null);
  }, []);

  const plans = [
    {
      name: "Free",
      price: "₹0",
      tickets: "50 tickets/month",
      seats: "1 seat",
      features: ["Basic complaint tracking", "Email support", "7-day data retention"]
    },
    {
      name: "Starter",
      price: "₹2,999",
      period: "/month",
      tickets: "500 tickets/month",
      seats: "3 seats",
      features: ["AI reply drafts", "Multi-channel support", "30-day data retention", "Basic analytics"]
    },
    {
      name: "Pro",
      price: "₹4,999",
      period: "/month",
      tickets: "2,000 tickets/month",
      seats: "10 seats",
      features: ["Everything in Starter", "Advanced analytics", "Team management", "90-day data retention", "Priority support"],
      popular: true
    },
    {
      name: "Max",
      price: "₹9,999",
      period: "/month",
      tickets: "10,000 tickets/month",
      seats: "25 seats",
      features: ["Everything in Pro", "Churn prediction", "Root cause analysis", "Instagram & Google Reviews", "Custom integrations"]
    },
    {
      name: "Scale",
      price: "₹99,999",
      period: "/month",
      tickets: "1,00,000 tickets/month",
      seats: "100 seats",
      features: ["Everything in Max", "RBI compliance tracking", "TAT monitoring", "MIS reports", "Dedicated account manager"]
    },
    {
      name: "Enterprise",
      price: "Custom",
      tickets: "Unlimited tickets",
      seats: "Unlimited seats",
      features: ["Everything in Scale", "Custom AI prompts", "SSO/SAML", "SLA guarantees", "White-label options"]
    }
  ];

  const handleUpgrade = (planName: string) => {
    toast.success(`Upgrade to ${planName} initiated!`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Billing & Plans</h1>
        <p className="text-gray-600">Manage your subscription and invoices</p>
      </div>

      {/* Current Plan */}
      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold capitalize">{user?.plan} Plan</div>
              <div className="text-gray-600 mt-1">
                {usage?.tickets_used ?? user?.ticketsUsed ?? 0} / {usage?.tickets_quota ?? user?.ticketsQuota ?? 50} tickets used this month
              </div>
              <div className="w-full max-w-md bg-gray-200 rounded-full h-2 mt-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{
                    width: `${Math.min(100, ((usage?.tickets_used ?? user?.ticketsUsed ?? 0) / (usage?.tickets_quota ?? user?.ticketsQuota ?? 50)) * 100)}%`,
                  }}
                />
              </div>
            </div>
            {usage?.next_billing_date && (
              <div className="text-right">
                <div className="text-sm text-gray-600">Next billing date</div>
                <div className="font-medium">{new Date(usage.next_billing_date).toLocaleDateString()}</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Available Plans */}
      <div>
        <h2 className="text-2xl font-bold mb-4">Available Plans</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isCurrentPlan = user?.plan === plan.name.toLowerCase();

            return (
              <Card
                key={plan.name}
                className={`${plan.popular ? "border-2 border-blue-600 relative" : ""} ${
                  isCurrentPlan ? "bg-blue-50" : ""
                }`}
              >
                {plan.popular && (
                  <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">
                    Most Popular
                  </Badge>
                )}
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {plan.name}
                    {isCurrentPlan && (
                      <Badge variant="secondary">Current</Badge>
                    )}
                  </CardTitle>
                  <div className="mt-4">
                    <span className="text-3xl font-bold">{plan.price}</span>
                    {plan.period && <span className="text-gray-600">{plan.period}</span>}
                  </div>
                  <div className="text-sm text-gray-600 mt-2">
                    <div>{plan.tickets}</div>
                    <div>{plan.seats}</div>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3 mb-6">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2">
                        <Check className="size-5 text-green-600 shrink-0 mt-0.5" />
                        <span className="text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    className="w-full"
                    variant={plan.popular ? "default" : "outline"}
                    disabled={isCurrentPlan}
                    onClick={() => handleUpgrade(plan.name)}
                  >
                    {isCurrentPlan ? "Current Plan" : "Upgrade"}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Invoice History */}
      <Card>
        <CardHeader>
          <CardTitle>Invoice History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {invoices.length === 0 ? (
              <p className="text-center text-gray-500 py-4">No invoices yet</p>
            ) : (
              invoices.map((inv) => (
                <div key={inv.id} className="flex items-center justify-between p-3 border rounded">
                  <div>
                    <div className="font-medium">{new Date(inv.date).toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</div>
                    <div className="text-sm text-gray-600 capitalize">{inv.plan} Plan</div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-medium">₹{inv.amount.toLocaleString("en-IN")}</span>
                    <Button size="sm" variant="outline">Download</Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

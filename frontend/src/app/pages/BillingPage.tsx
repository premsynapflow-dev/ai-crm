import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Check, Loader2 } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { toast } from "sonner";
import { api } from "../lib/api";

export function BillingPage() {
  const { user } = useAuth();
  const [usage, setUsage] = useState<{ tickets_used: number; tickets_quota: number; next_billing_date?: string } | null>(null);
  const [invoices, setInvoices] = useState<Array<{
    id: string;
    invoice_number: string;
    status: string;
    total: number;
    subtotal: number;
    tax: number;
    invoice_date: string | null;
    paid_at: string | null;
    payment_method: string | null;
    plan: string;
  }>>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    api.billing.getUsage().then(setUsage).catch(() => null);
    api.billing.getInvoices().then(setInvoices).catch(() => null);
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

  const handleDownloadInvoice = async (invoiceId: string, invoiceNumber: string) => {
    setDownloadingId(invoiceId);
    try {
      const blob = await api.billing.downloadInvoice(invoiceId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `synapflow-invoice-${invoiceNumber}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to download invoice. Please try again.");
    } finally {
      setDownloadingId(null);
    }
  };

  const PLAN_ID_MAP: Record<string, string> = {
    Free: "free",
    Starter: "starter",
    Pro: "pro",
    Max: "max",
    Scale: "scale",
    Enterprise: "enterprise",
  };

  const handleUpgrade = async (planName: string) => {
    if (planName === "Enterprise") {
      window.open("mailto:sales@synapflow.ai?subject=Enterprise%20Plan%20Inquiry", "_blank");
      return;
    }

    const planId = PLAN_ID_MAP[planName];
    if (!planId) return;

    setUpgrading(planName);
    try {
      const data = await api.billing.upgrade(planId, billingCycle);

      if (data.payment_url) {
        toast.success(`Redirecting to payment for ${planName}…`);
        window.location.href = data.payment_url;
        return;
      }

      if (data.status === "upgraded" && data.plan_applied) {
        toast.success(`You're now on the ${planName} plan!`);
        window.location.reload();
        return;
      }

      toast.info("Upgrade initiated — check your email for next steps.");
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message;
      if (msg?.includes("Upgrade not allowed")) {
        toast.error("You cannot downgrade via this page. Contact support.");
      } else if (msg?.includes("Razorpay is not configured")) {
        toast.error("Payment gateway not configured. Contact support.");
      } else {
        toast.error(msg || "Upgrade failed. Please try again.");
      }
    } finally {
      setUpgrading(null);
    }
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
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Available Plans</h2>
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setBillingCycle("monthly")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                billingCycle === "monthly"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle("annual")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                billingCycle === "annual"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Annual
              <span className="ml-1.5 text-xs text-green-600 font-semibold">2 months free</span>
            </button>
          </div>
        </div>
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
                    disabled={isCurrentPlan || upgrading === plan.name}
                    onClick={() => handleUpgrade(plan.name)}
                  >
                    {upgrading === plan.name ? (
                      <>
                        <Loader2 className="size-4 mr-2 animate-spin" />
                        Processing…
                      </>
                    ) : isCurrentPlan ? (
                      "Current Plan"
                    ) : plan.name === "Enterprise" ? (
                      "Contact Sales"
                    ) : (
                      "Upgrade"
                    )}
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
              invoices.map((inv) => {
                const date = inv.invoice_date ? new Date(inv.invoice_date) : null;
                const isPaid = inv.status === "paid";
                return (
                  <div key={inv.id} className="flex items-center justify-between p-3 border rounded hover:bg-gray-50 transition-colors">
                    <div>
                      <div className="font-medium">
                        {date
                          ? date.toLocaleDateString("en-IN", { month: "long", year: "numeric" })
                          : inv.invoice_number}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-sm text-gray-600">{inv.plan} Plan</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                          isPaid
                            ? "bg-green-100 text-green-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}>
                          {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">#{inv.invoice_number}</div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="font-medium">₹{Math.round(inv.total).toLocaleString("en-IN")}</span>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={downloadingId === inv.id}
                        onClick={() => handleDownloadInvoice(inv.id, inv.invoice_number)}
                      >
                        {downloadingId === inv.id ? (
                          <><Loader2 className="size-3 mr-1.5 animate-spin" />Downloading…</>
                        ) : (
                          "Download PDF"
                        )}
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

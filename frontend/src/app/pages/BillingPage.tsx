import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Check, Loader2 } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { toast } from "sonner";
import { api } from "../lib/api";

export function BillingPage() {
  const { user } = useAuth();
  const [usage, setUsage] = useState<{
    current_usage: number;
    monthly_limit: number;
    period_end?: string;
  } | null>(null);
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

  const paymentLinkVerified = useRef(false);

  useEffect(() => {
    api.billing.getUsage().then(setUsage).catch(() => null);
    api.billing.getInvoices().then(setInvoices).catch(() => null);

    // Handle return from Razorpay hosted payment link
    const params = new URLSearchParams(window.location.search);
    const rzpPaymentId = params.get("razorpay_payment_id");
    const rzpLinkId = params.get("razorpay_payment_link_id");
    const rzpRefId = params.get("razorpay_payment_link_reference_id");
    const rzpStatus = params.get("razorpay_payment_link_status");
    const rzpSig = params.get("razorpay_signature");
    const rzpPlan = params.get("rzp_plan");
    const rzpCycle = (params.get("rzp_cycle") as "monthly" | "annual") || "monthly";

    if (rzpPaymentId && rzpLinkId && rzpRefId && rzpStatus && rzpSig && rzpPlan && !paymentLinkVerified.current) {
      paymentLinkVerified.current = true;
      window.history.replaceState({}, "", window.location.pathname);
      api.billing.verifyPaymentLink({
        razorpay_payment_id: rzpPaymentId,
        razorpay_payment_link_id: rzpLinkId,
        razorpay_payment_link_reference_id: rzpRefId,
        razorpay_payment_link_status: rzpStatus,
        razorpay_signature: rzpSig,
        plan_id: rzpPlan,
        billing_cycle: rzpCycle,
      }).then(() => {
        toast.success("Payment successful! Your plan has been upgraded.");
        window.location.reload();
      }).catch(() => {
        toast.error("Payment received but plan activation failed — contact support.");
      });
    }
  }, []);

  const plans = [
    {
      name: "Free",
      monthlyPrice: "₹0",
      annualPrice: null,
      tickets: "50 tickets/month",
      seats: "1 seat",
      features: ["Basic complaint tracking", "Email support", "7-day data retention"]
    },
    {
      name: "Starter",
      monthlyPrice: "₹2,999",
      annualPrice: "₹29,990",
      annualMonthly: "₹2,499",
      tickets: "500 tickets/month",
      seats: "3 seats",
      features: ["AI reply drafts", "Multi-channel support", "30-day data retention", "Basic analytics"]
    },
    {
      name: "Growth",
      monthlyPrice: "₹19,999",
      annualPrice: "₹1,99,990",
      annualMonthly: "₹16,666",
      tickets: "2,000 tickets/month",
      seats: "10 seats",
      features: ["Everything in Starter", "Advanced analytics", "Team management", "90-day data retention", "Priority support"],
      popular: true
    },
    {
      name: "Business",
      monthlyPrice: "₹59,999",
      annualPrice: "₹5,99,990",
      annualMonthly: "₹49,999",
      tickets: "10,000 tickets/month",
      seats: "25 seats",
      features: ["Everything in Growth", "Churn prediction", "Root cause analysis", "Instagram & Google Reviews", "Custom integrations"]
    },
    {
      name: "Scale",
      monthlyPrice: "₹1,49,999",
      annualPrice: "₹14,99,990",
      annualMonthly: "₹1,24,999",
      tickets: "50,000 tickets/month",
      seats: "100 seats",
      features: ["Everything in Business", "RBI compliance tracking", "TAT monitoring", "MIS reports", "Dedicated account manager"]
    },
    {
      name: "Enterprise",
      monthlyPrice: "Custom",
      annualPrice: null,
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

  const loadRazorpayScript = (): Promise<void> =>
    new Promise((resolve, reject) => {
      if ((window as unknown as Record<string, unknown>).Razorpay) { resolve(); return; }
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Razorpay checkout"));
      document.body.appendChild(script);
    });

  const openRazorpayModal = async (data: {
    order_id: string;
    razorpay_key: string;
    amount: number;
    currency: string;
    plan_id: string;
    plan_name: string;
    billing_cycle: string;
  }) => {
    await loadRazorpayScript();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Razorpay = (window as any).Razorpay;
    const options = {
      key: data.razorpay_key,
      amount: data.amount,
      currency: data.currency,
      name: "SynapFlow",
      description: `${data.plan_name} Plan (${data.billing_cycle})`,
      order_id: data.order_id,
      handler: async (response: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) => {
        try {
          await api.billing.verifyPayment({
            order_id: response.razorpay_order_id,
            payment_id: response.razorpay_payment_id,
            signature: response.razorpay_signature,
            plan_id: data.plan_id,
            billing_cycle: data.billing_cycle,
          });
          toast.success(`You're now on the ${data.plan_name} plan!`);
          window.location.reload();
        } catch {
          toast.error("Payment received but plan activation failed — contact support.");
        }
      },
      theme: { color: "#2563eb" },
    };
    new Razorpay(options).open();
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

      if (data.checkout_mode === "order" && data.order_id && data.razorpay_key) {
        setUpgrading(null);
        await openRazorpayModal({
          order_id: data.order_id,
          razorpay_key: data.razorpay_key,
          amount: data.amount!,
          currency: data.currency || "INR",
          plan_id: data.plan_id,
          plan_name: data.plan_name || planName,
          billing_cycle: data.billing_cycle || billingCycle,
        });
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

  const ticketsUsed = usage?.current_usage ?? user?.ticketsUsed ?? 0;
  const ticketsQuota = usage?.monthly_limit ?? user?.ticketsQuota ?? 50;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Billing & Plans</h1>
        <p className="text-gray-600 dark:text-gray-400">Manage your subscription and invoices</p>
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
              <div className="text-gray-600 dark:text-gray-400 mt-1">
                {ticketsUsed} / {ticketsQuota} tickets used this month
              </div>
              <div className="w-full max-w-md bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{
                    width: `${Math.min(100, (ticketsUsed / Math.max(ticketsQuota, 1)) * 100)}%`,
                  }}
                />
              </div>
            </div>
            {usage?.period_end && (
              <div className="text-right">
                <div className="text-sm text-gray-600 dark:text-gray-400">Period ends</div>
                <div className="font-medium">{new Date(usage.period_end).toLocaleDateString()}</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Available Plans */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Available Plans</h2>
          <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setBillingCycle("monthly")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                billingCycle === "monthly"
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle("annual")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                billingCycle === "annual"
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              }`}
            >
              Annual
              <span className="ml-1.5 text-xs text-green-600 dark:text-green-400 font-semibold">2 months free</span>
            </button>
          </div>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isCurrentPlan = user?.plan === plan.name.toLowerCase();
            const displayPrice = billingCycle === "annual" && plan.annualPrice
              ? plan.annualPrice
              : plan.monthlyPrice;
            const displayPeriod = billingCycle === "annual" && plan.annualPrice
              ? "/year"
              : plan.monthlyPrice === "Custom" ? undefined : "/month";

            return (
              <Card
                key={plan.name}
                className={`${plan.popular ? "border-2 border-blue-600 relative" : ""} ${
                  isCurrentPlan ? "bg-blue-50 dark:bg-blue-900/10" : ""
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
                    <span className="text-3xl font-bold">{displayPrice}</span>
                    {displayPeriod && (
                      <span className="text-gray-600 dark:text-gray-400">{displayPeriod}</span>
                    )}
                  </div>
                  {billingCycle === "annual" && plan.annualMonthly && (
                    <div className="text-sm text-green-600 dark:text-green-400 font-medium">
                      {plan.annualMonthly}/mo effective
                    </div>
                  )}
                  <div className="text-sm text-gray-600 dark:text-gray-400 mt-2">
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
                  <div key={inv.id} className="flex items-center justify-between p-3 border dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                    <div>
                      <div className="font-medium">
                        {date
                          ? date.toLocaleDateString("en-IN", { month: "long", year: "numeric" })
                          : inv.invoice_number}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-sm text-gray-600 dark:text-gray-400">{inv.plan} Plan</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                          isPaid
                            ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                            : "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400"
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

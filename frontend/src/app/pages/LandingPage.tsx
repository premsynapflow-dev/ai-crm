import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Check, Zap, Shield, BarChart3, Bot, MessageSquare, TrendingUp } from "lucide-react";
import { Link } from "react-router";

export function LandingPage() {
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

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="SynapFlow" className="size-8 object-contain" />
            <span className="text-2xl font-semibold">SynapFlow</span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login">
              <Button variant="ghost">Log in</Button>
            </Link>
            <Link to="/signup">
              <Button>Sign up</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto text-center max-w-4xl">
          <Badge className="mb-4">AI-Powered Complaint Intelligence</Badge>
          <h1 className="text-5xl font-bold mb-6">
            Handle Customer Complaints at Scale with AI
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            SynapFlow helps Indian fintechs, NBFCs, and D2C brands manage complaints across channels,
            generate AI-powered replies, and maintain RBI compliance—all from one platform.
          </p>
          <div className="flex gap-4 justify-center">
            <Link to="/signup">
              <Button size="lg" className="text-lg px-8">
                Start Free Trial
              </Button>
            </Link>
            <Link to="/login">
              <Button size="lg" variant="outline" className="text-lg px-8">
                View Demo
              </Button>
            </Link>
          </div>
          <p className="text-sm text-gray-500 mt-4">
            No credit card required • 50 free tickets/month • Setup in 5 minutes
          </p>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 px-4 bg-gray-50">
        <div className="container mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Everything you need to manage complaints</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <Card>
              <CardHeader>
                <MessageSquare className="size-10 text-blue-600 mb-4" />
                <CardTitle>Multi-Channel Ingestion</CardTitle>
                <CardDescription>
                  Collect complaints from API, email, Gmail, WhatsApp, chat widget, Instagram, and Google Reviews
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <Bot className="size-10 text-purple-600 mb-4" />
                <CardTitle>AI-Generated Replies</CardTitle>
                <CardDescription>
                  AI drafts responses with confidence scores, hallucination checks, and toxicity filtering
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <Shield className="size-10 text-green-600 mb-4" />
                <CardTitle>RBI Compliance</CardTitle>
                <CardDescription>
                  Track TAT deadlines, escalation levels, and generate MIS reports for regulatory compliance
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <BarChart3 className="size-10 text-orange-600 mb-4" />
                <CardTitle>Advanced Analytics</CardTitle>
                <CardDescription>
                  CSAT trends, sentiment analysis, root cause insights, and team performance metrics
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <TrendingUp className="size-10 text-red-600 mb-4" />
                <CardTitle>Churn Prediction</CardTitle>
                <CardDescription>
                  AI-powered churn risk scoring with explanations and proactive intervention recommendations
                </CardDescription>
              </CardHeader>
            </Card>

            <Card>
              <CardHeader>
                <Zap className="size-10 text-yellow-600 mb-4" />
                <CardTitle>Smart Automation</CardTitle>
                <CardDescription>
                  Auto-route complaints, trigger Slack alerts, and execute custom workflows based on rules
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* Who It's For */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <h2 className="text-3xl font-bold text-center mb-12">Built for Indian businesses</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Fintechs & NBFCs</CardTitle>
                <CardDescription>
                  Handle loan complaints, payment disputes, and RBI escalations with built-in TAT tracking
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>D2C Brands</CardTitle>
                <CardDescription>
                  Manage delivery issues, product returns, and billing complaints across WhatsApp and email
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>E-commerce Platforms</CardTitle>
                <CardDescription>
                  Scale customer support with AI assistance while maintaining personalized responses
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Banks & Financial Services</CardTitle>
                <CardDescription>
                  Meet RBI compliance requirements with automated MIS reporting and escalation management
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-16 px-4 bg-gray-50" id="pricing">
        <div className="container mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Simple, transparent pricing</h2>
          <p className="text-center text-gray-600 mb-12">
            Choose the plan that fits your business. All plans include 2 months free with annual billing.
          </p>
          
          <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {plans.map((plan) => (
              <Card key={plan.name} className={plan.popular ? "border-2 border-blue-600 relative" : ""}>
                {plan.popular && (
                  <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">Most Popular</Badge>
                )}
                <CardHeader>
                  <CardTitle>{plan.name}</CardTitle>
                  <div className="mt-4">
                    <span className="text-4xl font-bold">{plan.price}</span>
                    {plan.period && <span className="text-gray-600">{plan.period}</span>}
                  </div>
                  <div className="text-sm text-gray-600 mt-2">
                    <div>{plan.tickets}</div>
                    <div>{plan.seats}</div>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2">
                        <Check className="size-5 text-green-600 shrink-0 mt-0.5" />
                        <span className="text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Link to="/signup">
                    <Button className="w-full mt-6" variant={plan.popular ? "default" : "outline"}>
                      Get Started
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto text-center max-w-3xl">
          <h2 className="text-4xl font-bold mb-6">
            Ready to transform your complaint management?
          </h2>
          <p className="text-xl text-gray-600 mb-8">
            Join hundreds of Indian businesses using SynapFlow to handle complaints faster and smarter.
          </p>
          <Link to="/signup">
            <Button size="lg" className="text-lg px-8">
              Start Free Trial
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 px-4 bg-gray-50">
        <div className="container mx-auto text-center text-sm text-gray-600">
          <p>© 2026 SynapFlow. Built for Indian businesses.</p>
          <p className="mt-2">Not meant for collecting PII or securing sensitive personal data.</p>
        </div>
      </footer>
    </div>
  );
}

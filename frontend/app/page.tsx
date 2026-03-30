"use client"

import Link from 'next/link'
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock3,
  LineChart,
  ShieldCheck,
  Users,
} from 'lucide-react'

import { Logo } from '@/components/logo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const features = [
  {
    icon: Bot,
    title: 'AI triage and response drafting',
    description:
      'Classify, prioritize, and draft replies in seconds so teams can focus on judgment instead of manual queue cleanup.',
  },
  {
    icon: ShieldCheck,
    title: 'Compliance-first workflows',
    description:
      'Track RBI and SLA obligations with audit-ready timelines, escalations, and oversight across every tenant.',
  },
  {
    icon: Users,
    title: 'Multi-tenant control',
    description:
      'Manage multiple business units or clients from one secure platform with isolated data and central visibility.',
  },
  {
    icon: Clock3,
    title: 'Faster first response',
    description:
      'Reduce turnaround time with automated routing, priority scoring, and approval-aware AI assistance.',
  },
  {
    icon: LineChart,
    title: 'Executive visibility',
    description:
      'Spot complaint spikes, response bottlenecks, and churn risks before they become recurring fires.',
  },
]

const pricing = [
  {
    name: 'Starter',
    price: 'INR 1,499',
    cadence: '/month',
    href: '/signup',
    cta: 'Start free trial',
    featured: false,
    points: ['50 tickets per month', 'AI auto-reply drafts', 'Basic queue management', 'Up to 2 team members'],
  },
  {
    name: 'Growth',
    price: 'INR 9,999',
    cadence: '/month',
    href: '/signup',
    cta: 'Start with Growth',
    featured: true,
    points: ['500 tickets per month', 'SLA workflows', 'RBI compliance support', 'Customer 360 and analytics'],
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    cadence: 'Tailored rollout',
    href: '/signup',
    cta: 'Schedule a demo',
    featured: false,
    points: ['Unlimited volume', 'Custom integrations', 'Dedicated onboarding', 'Priority support'],
  },
]

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f7f4ed_0%,#fffdf8_28%,#ffffff_100%)] text-slate-900">
      <div className="pointer-events-none fixed inset-x-0 top-0 h-[32rem] bg-[radial-gradient(circle_at_top_left,rgba(9,105,218,0.14),transparent_38%),radial-gradient(circle_at_top_right,rgba(180,83,9,0.14),transparent_34%)]" />

      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <Logo />
          <nav className="hidden items-center gap-8 text-sm text-slate-600 md:flex">
            <a href="#features" className="transition hover:text-slate-900">
              Features
            </a>
            <a href="#pricing" className="transition hover:text-slate-900">
              Pricing
            </a>
            <a href="#results" className="transition hover:text-slate-900">
              Outcomes
            </a>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" className="text-slate-700">
                Log in
              </Button>
            </Link>
            <Link href="/signup">
              <Button className="bg-slate-900 text-white hover:bg-slate-800">
                Start free trial
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden px-4 pb-20 pt-16 sm:px-6 lg:px-8 lg:pb-24 lg:pt-24">
        <div className="mx-auto grid max-w-7xl gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div>
            <Badge className="mb-6 rounded-full bg-amber-100 px-4 py-1 text-amber-900 hover:bg-amber-100">
              AI-powered complaint management for regulated teams
            </Badge>
            <h1 className="max-w-3xl text-5xl font-semibold tracking-tight text-slate-950 sm:text-6xl">
              Turn complaint operations into a measurable competitive edge.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600 sm:text-xl">
              SynapFlow helps support and compliance teams classify complaints, route work,
              enforce SLAs, and draft high-confidence replies without losing human control.
            </p>
            <div className="mt-8 flex flex-col gap-4 sm:flex-row">
              <Link href="/signup">
                <Button size="lg" className="w-full bg-slate-900 text-white hover:bg-slate-800 sm:w-auto">
                  Start free trial
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <a href="#pricing">
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full border-slate-300 bg-white/80 text-slate-900 hover:bg-slate-50 sm:w-auto"
                >
                  View pricing
                </Button>
              </a>
            </div>
            <div className="mt-8 flex flex-col gap-3 text-sm text-slate-600 sm:flex-row sm:gap-6">
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                14-day free trial
              </span>
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                No credit card required
              </span>
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Built for RBI-aware workflows
              </span>
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-6 rounded-[2rem] bg-[radial-gradient(circle_at_top,rgba(249,115,22,0.18),transparent_45%),radial-gradient(circle_at_bottom_right,rgba(37,99,235,0.16),transparent_40%)] blur-2xl" />
            <div className="relative overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-[0_30px_90px_rgba(15,23,42,0.14)]">
              <div className="border-b border-slate-200 bg-slate-950 px-6 py-4 text-slate-50">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Operations cockpit</p>
                <h2 className="mt-1 text-xl font-semibold">Daily complaint flow</h2>
              </div>
              <div className="grid gap-4 p-6 sm:grid-cols-2">
                <Card className="border-slate-200 bg-[#fcfbf7] shadow-none">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-slate-500">SLA on track</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-4xl font-semibold text-slate-950">96.4%</div>
                    <p className="mt-2 text-sm text-slate-500">Across all active complaint queues this month</p>
                  </CardContent>
                </Card>
                <Card className="border-slate-200 bg-[#f5f9ff] shadow-none">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-slate-500">AI-assisted replies</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-4xl font-semibold text-slate-950">84%</div>
                    <p className="mt-2 text-sm text-slate-500">Draft acceptance rate with human review controls</p>
                  </CardContent>
                </Card>
                <div className="rounded-3xl border border-slate-200 bg-white p-5 sm:col-span-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-slate-500">Queue pressure snapshot</p>
                      <p className="mt-1 text-lg font-semibold text-slate-950">Escalations reduced week over week</p>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700">
                      -32%
                    </span>
                  </div>
                  <div className="mt-5 space-y-3">
                    {[
                      ['Payments', '18 open', '78%'],
                      ['Cards', '9 open', '54%'],
                      ['Fraud', '4 escalated', '28%'],
                    ].map(([label, value, width]) => (
                      <div key={label}>
                        <div className="mb-2 flex items-center justify-between text-sm text-slate-600">
                          <span>{label}</span>
                          <span>{value}</span>
                        </div>
                        <div className="h-2 rounded-full bg-slate-100">
                          <div className="h-2 rounded-full bg-slate-900" style={{ width }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="results" className="px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-4 rounded-[2rem] border border-slate-200 bg-white/80 p-6 shadow-sm backdrop-blur sm:grid-cols-3 lg:p-8">
          {[
            ['10x faster', 'First-response turnaround'],
            ['85%+', 'High-confidence AI draft coverage'],
            ['1 platform', 'Tenant, compliance, and ops visibility'],
          ].map(([value, label]) => (
            <div key={label} className="rounded-2xl bg-slate-50 p-5">
              <div className="text-3xl font-semibold text-slate-950">{value}</div>
              <p className="mt-2 text-sm text-slate-600">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-amber-700">What teams get</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
              A complaint platform that helps operators move faster without losing control.
            </h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {features.map((feature) => {
              const Icon = feature.icon
              return (
                <Card key={feature.title} className="h-full rounded-[1.75rem] border-slate-200 bg-white/90 shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                  <CardHeader>
                    <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <CardTitle className="text-xl text-slate-950">{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-base leading-7 text-slate-600">{feature.description}</p>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      </section>

      <section id="pricing" className="bg-slate-950 px-4 py-20 text-white sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-amber-300">Pricing</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
              Start lean, scale into deeper automation when your volume grows.
            </h2>
            <p className="mt-5 text-lg text-slate-300">
              Transparent pricing for teams that want AI acceleration and compliance guardrails from day one.
            </p>
          </div>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {pricing.map((plan) => (
              <Card
                key={plan.name}
                className={`rounded-[1.8rem] border ${
                  plan.featured
                    ? 'border-amber-300 bg-[linear-gradient(180deg,#fffdf8_0%,#fff3cf_100%)] text-slate-950'
                    : 'border-white/10 bg-white/5'
                } ${plan.featured ? '' : 'text-white'} shadow-none`}
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-2xl">{plan.name}</CardTitle>
                    {plan.featured ? (
                      <Badge className="rounded-full border-0 bg-amber-300 text-slate-950 hover:bg-amber-300">
                        Most recommended
                      </Badge>
                    ) : null}
                  </div>
                  <div className="pt-6">
                    <div className="text-4xl font-semibold">{plan.price}</div>
                    <p className={`mt-2 text-sm ${plan.featured ? 'text-slate-600' : 'text-slate-300'}`}>{plan.cadence}</p>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className={`space-y-3 text-sm ${plan.featured ? 'text-slate-700' : 'text-slate-200'}`}>
                    {plan.points.map((point) => (
                      <li key={point} className="flex items-start gap-3">
                        <CheckCircle2 className={`mt-0.5 h-4 w-4 shrink-0 ${plan.featured ? 'text-emerald-600' : 'text-emerald-300'}`} />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href={plan.href} className="mt-8 block">
                    <Button
                      className={`w-full ${
                        plan.featured
                          ? 'bg-amber-300 text-slate-950 hover:bg-amber-200'
                          : 'bg-white text-slate-950 hover:bg-slate-100'
                      }`}
                    >
                      {plan.cta}
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 rounded-[2rem] border border-slate-200 bg-[linear-gradient(135deg,#10243a_0%,#1e3a5f_45%,#7c2d12_100%)] px-6 py-10 text-white shadow-2xl lg:flex-row lg:items-center lg:justify-between lg:px-10">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-amber-200">Ready when you are</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight">
              Give your support and compliance teams a system they can actually trust.
            </h2>
            <p className="mt-4 text-lg text-slate-200">
              Start a free trial for tenant teams or use the platform admin console to oversee growth across accounts.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/signup">
              <Button size="lg" className="w-full bg-white text-slate-950 hover:bg-slate-100 sm:w-auto">
                Start free trial
              </Button>
            </Link>
            <a href="#pricing">
              <Button
                size="lg"
                variant="outline"
                className="w-full border-white/40 bg-transparent text-white hover:bg-white/10 sm:w-auto"
              >
                Compare plans
              </Button>
            </a>
          </div>
        </div>
      </section>
    </main>
  )
}

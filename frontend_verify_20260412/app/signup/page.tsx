"use client"

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowRight, Building2, CheckCircle2, Mail, Phone, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

import { Logo } from '@/components/logo'
import { COMPANY_SECTOR_OPTIONS } from '@/lib/company-profile'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export default function SignupPage() {
  const router = useRouter()
  const [companyName, setCompanyName] = useState('')
  const [email, setEmail] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [businessSector, setBusinessSector] = useState('not_rbi_regulated')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)

    try {
      const response = await fetch('/api/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_name: companyName,
          email,
          phone_number: phoneNumber,
          business_sector: businessSector,
          password,
        }),
      })

      const payload = (await response.json().catch(() => ({}))) as { detail?: string }
      if (!response.ok) {
        throw new Error(payload.detail || 'Failed to create account')
      }

      toast.success('Free workspace created', {
        description: 'You can now sign in with your new SynapFlow account.',
      })
      router.push('/login')
    } catch (error) {
      toast.error('Signup failed', {
        description: error instanceof Error ? error.message : 'Please try again.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f8f5ef_0%,#ffffff_100%)] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
        <section className="space-y-6">
          <Link href="/" className="inline-block">
            <Logo />
          </Link>
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-amber-700">Start for free</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
              Launch a SynapFlow workspace in minutes.
            </h1>
            <p className="mt-4 text-lg leading-8 text-slate-600">
              Give your support and compliance teams a shared complaint command center with AI assistance, SLA tracking, and clear plan limits. RBI compliance tools are available on Scale and Enterprise for eligible RBI-regulated financial institutions.
            </p>
          </div>
          <div className="grid gap-4">
            {[
              'Provisioned with the Free plan',
              'No credit card required to begin',
              'Fast upgrade path to Starter, Pro, Max, Scale, or Enterprise',
            ].map((item) => (
              <div key={item} className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white/80 p-4">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                <span className="text-slate-700">{item}</span>
              </div>
            ))}
          </div>
        </section>

        <Card className="rounded-[2rem] border-slate-200 bg-white shadow-xl">
          <CardHeader className="space-y-3">
            <CardTitle className="text-3xl text-slate-950">Create your account</CardTitle>
            <CardDescription className="text-base text-slate-600">
              Your workspace will be created through the existing SynapFlow public signup flow.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-5" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="companyName">Company name</Label>
                <div className="relative">
                  <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="companyName"
                    value={companyName}
                    onChange={(event) => setCompanyName(event.target.value)}
                    placeholder="Acme Financial Services"
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Work email</Label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="ops@company.com"
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="phoneNumber">Phone number</Label>
                <div className="relative">
                  <Phone className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="phoneNumber"
                    type="tel"
                    value={phoneNumber}
                    onChange={(event) => setPhoneNumber(event.target.value)}
                    placeholder="+91 98765 43210"
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="businessSector">Company category</Label>
                <Select value={businessSector} onValueChange={setBusinessSector}>
                  <SelectTrigger id="businessSector" className="w-full">
                    <SelectValue placeholder="Select your company category" />
                  </SelectTrigger>
                  <SelectContent>
                    {COMPANY_SECTOR_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-slate-500">
                  We use this to determine whether RBI compliance workflows can be enabled in your workspace when you're on Scale or Enterprise.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  minLength={8}
                  required
                />
              </div>

              <div className="hidden rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-slate-900" />
                  <p>
                    By signing up, you’ll create a tenant workspace on the Starter plan and can upgrade later from inside the app.
                  </p>
                </div>
              </div>

              <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-slate-900" />
                  <p>
                    By signing up, you'll create a tenant workspace on the Free plan. If you select an RBI-regulated financial company category, the RBI compliance workspace can be enabled after you upgrade to Scale or Enterprise.
                  </p>
                </div>
              </div>

              <Button type="submit" className="w-full bg-slate-900 text-white hover:bg-slate-800" disabled={isSubmitting}>
                {isSubmitting ? 'Creating workspace...' : 'Create account'}
                {!isSubmitting ? <ArrowRight className="ml-2 h-4 w-4" /> : null}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-600">
              Already have an account?{' '}
              <Link href="/login" className="font-medium text-slate-950 underline underline-offset-4">
                Log in
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

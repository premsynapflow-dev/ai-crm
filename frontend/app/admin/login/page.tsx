"use client"

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AlertTriangle, ArrowRight, Shield } from 'lucide-react'

import { Logo } from '@/components/logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const ADMIN_TOKEN_KEY = 'admin_token'

export default function AdminLoginPage() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const token = window.localStorage.getItem(ADMIN_TOKEN_KEY)
    if (token) {
      router.replace('/admin')
    }
  }, [router])

  const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await fetch('/api/admin/dashboard/overview', {
        headers: {
          Authorization: `Bearer ${password}`,
        },
      })

      if (!response.ok) {
        throw new Error('Invalid admin credentials')
      }

      window.localStorage.setItem(ADMIN_TOKEN_KEY, password)
      router.push('/admin')
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : 'Unable to verify admin access')
      window.localStorage.removeItem(ADMIN_TOKEN_KEY)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#0f172a_0%,#1e293b_100%)] px-4 py-10 text-white sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_0.95fr] lg:items-center">
        <section className="space-y-6">
          <Link href="/" className="inline-block">
            <Logo />
          </Link>
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-blue-200">Platform administration</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
              Admin access for platform-wide oversight.
            </h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-300">
              Use the protected admin console to review tenant growth, system usage, AI reply performance, and SLA health across the platform.
            </p>
          </div>
          <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 text-sm text-slate-300">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
              <p>
                The current admin flow uses the configured `ADMIN_PASSWORD` bearer token for MVP access. Swap this for role-based JWT auth before production hardening.
              </p>
            </div>
          </div>
        </section>

        <Card className="rounded-[2rem] border-white/10 bg-white text-slate-950 shadow-2xl">
          <CardHeader className="space-y-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-950 text-white">
              <Shield className="h-6 w-6" />
            </div>
            <CardTitle className="text-3xl">Admin login</CardTitle>
            <CardDescription className="text-base text-slate-600">
              Enter the platform admin password to access the protected SynapFlow admin dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="admin-password">Admin password</Label>
                <Input
                  id="admin-password"
                  type="password"
                  placeholder="Enter your admin password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>

              {error ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {error}
                </div>
              ) : null}

              <Button type="submit" className="w-full bg-slate-950 text-white hover:bg-slate-800" disabled={loading}>
                {loading ? 'Verifying access...' : 'Access admin dashboard'}
                {!loading ? <ArrowRight className="ml-2 h-4 w-4" /> : null}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

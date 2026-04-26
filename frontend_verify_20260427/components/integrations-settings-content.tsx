"use client"

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import Link from 'next/link'
import { AlertCircle, CheckCircle2, ChevronLeft, Copy, Loader2, Mail, MessageSquareText, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { integrationsAPI, type IntegrationConnection } from '@/lib/api/integrations'
import { cn } from '@/lib/utils'

const DEFAULT_FORWARDING_ADDRESS = 'support@inbound.synapflow.com'

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as Record<string, unknown>).message)
  }
  return fallback
}

function formatChannelLabel(channel: string) {
  switch (channel) {
    case 'gmail':
      return 'Gmail'
    case 'email':
      return 'Email Forwarding'
    case 'whatsapp':
      return 'WhatsApp'
    default:
      return channel.charAt(0).toUpperCase() + channel.slice(1)
  }
}

function statusPresentation(status?: string | null) {
  const normalized = (status ?? '').toLowerCase()
  if (normalized === 'active' || normalized === 'connected') {
    return {
      label: 'Connected',
      className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      dotClassName: 'bg-emerald-500',
    }
  }

  return {
    label: 'Not Connected',
    className: 'border-rose-200 bg-rose-50 text-rose-700',
    dotClassName: 'bg-rose-500',
  }
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return 'Just now'
  }

  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function IntegrationsSettingsContent() {
  const [connections, setConnections] = useState<IntegrationConnection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isConnectingGmail, setIsConnectingGmail] = useState(false)
  const [isConnectingWhatsApp, setIsConnectingWhatsApp] = useState(false)
  const [whatsAppForm, setWhatsAppForm] = useState({
    phoneNumberId: '',
    businessAccountId: '',
    accessToken: '',
  })

  const refreshConnections = async (background = false) => {
    if (background) {
      setIsRefreshing(true)
    } else {
      setIsLoading(true)
    }

    try {
      const response = await integrationsAPI.list()
      setConnections(response)
      setLoadError(null)
    } catch {
      setLoadError('Unable to load integration channels right now.')
    } finally {
      if (background) {
        setIsRefreshing(false)
      } else {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    void refreshConnections()
  }, [])

  const gmailConnection = useMemo(
    () => connections.find((connection) => connection.channel === 'gmail'),
    [connections],
  )
  const whatsappConnection = useMemo(
    () => connections.find((connection) => connection.channel === 'whatsapp'),
    [connections],
  )
  const emailConnection = useMemo(
    () => connections.find((connection) => connection.channel === 'email'),
    [connections],
  )

  const forwardingAddress = emailConnection?.account_identifier || DEFAULT_FORWARDING_ADDRESS
  const gmailStatus = statusPresentation(gmailConnection?.status)
  const whatsappStatus = statusPresentation(whatsappConnection?.status)

  const handleCopy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast.success(`${label} copied to clipboard`)
    } catch {
      toast.error(`Unable to copy ${label.toLowerCase()}`)
    }
  }

  const handleGmailConnect = async () => {
    setIsConnectingGmail(true)
    try {
      const response = await integrationsAPI.connectGmail()
      if (!response.auth_url) {
        throw new Error('Missing auth URL')
      }
      window.location.assign(response.auth_url)
    } catch (error) {
      toast.error(getErrorMessage(error, 'Unable to start Gmail OAuth right now'))
      setIsConnectingGmail(false)
    }
  }

  const handleWhatsAppConnect = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsConnectingWhatsApp(true)

    try {
      const response = await integrationsAPI.connectWhatsApp({
        phone_number_id: whatsAppForm.phoneNumberId.trim(),
        business_account_id: whatsAppForm.businessAccountId.trim() || undefined,
        access_token: whatsAppForm.accessToken.trim(),
      })

      toast.success('WhatsApp connected successfully')
      setWhatsAppForm((current) => ({
        ...current,
        accessToken: '',
        phoneNumberId: response.phone_number_id || current.phoneNumberId,
      }))
      await refreshConnections(true)
    } catch {
      toast.error('Unable to connect WhatsApp')
    } finally {
      setIsConnectingWhatsApp(false)
    }
  }

  if (isLoading) {
    return <div className="flex h-96 items-center justify-center text-sm text-muted-foreground">Loading integrations...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <Link
            href="/settings"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
            Back to settings
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Integrations & Channels</h1>
            <p className="mt-1 text-muted-foreground">
              Connect customer-facing channels so SynapFlow can ingest, triage, and reply from the original source.
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          onClick={() => void refreshConnections(true)}
          disabled={isRefreshing}
          className="gap-2 self-start md:self-auto"
        >
          {isRefreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </Button>
      </div>

      {loadError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Could not load integrations</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <Card className="border-border/70 shadow-sm">
            <CardHeader className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-emerald-700">
                    <Mail className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle>Gmail Integration</CardTitle>
                    <CardDescription>
                      Connect a Gmail inbox for direct intake, threaded replies, and live message sync.
                    </CardDescription>
                  </div>
                </div>
                <Badge className={gmailStatus.className}>
                  <span className={cn('mr-1.5 inline-block h-1.5 w-1.5 rounded-full', gmailStatus.dotClassName)} />
                  {gmailStatus.label}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 rounded-2xl border border-border/60 bg-muted/20 p-4 md:grid-cols-2">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Connected Email</p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {gmailConnection?.account_identifier || 'No Gmail inbox connected yet'}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Last Synced State</p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {gmailConnection ? formatDateTime(gmailConnection.created_at) : 'Waiting for connection'}
                  </p>
                </div>
              </div>

              <Button onClick={() => void handleGmailConnect()} disabled={isConnectingGmail} className="gap-2">
                {isConnectingGmail ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                Connect Gmail
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/70 shadow-sm">
            <CardHeader className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-2xl border border-sky-200 bg-sky-50 p-3 text-sky-700">
                    <MessageSquareText className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle>WhatsApp Integration</CardTitle>
                    <CardDescription>
                      Connect your WhatsApp Cloud API number to receive and reply from SynapFlow.
                    </CardDescription>
                  </div>
                </div>
                <Badge className={whatsappStatus.className}>
                  <span className={cn('mr-1.5 inline-block h-1.5 w-1.5 rounded-full', whatsappStatus.dotClassName)} />
                  {whatsappStatus.label}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 rounded-2xl border border-border/60 bg-muted/20 p-4 md:grid-cols-2">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Connected Number</p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {whatsappConnection?.account_identifier || 'No WhatsApp number connected yet'}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Connection Status</p>
                  <div className="mt-2 flex items-center gap-2 text-sm font-medium text-foreground">
                    {whatsappConnection?.status === 'active' ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-rose-500" />
                    )}
                    {whatsappStatus.label}
                  </div>
                </div>
              </div>

              <form className="space-y-4" onSubmit={(event) => void handleWhatsAppConnect(event)}>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="phone-number-id" className="text-sm font-medium text-foreground">
                      Phone Number ID
                    </label>
                    <Input
                      id="phone-number-id"
                      value={whatsAppForm.phoneNumberId}
                      onChange={(event) => setWhatsAppForm((current) => ({ ...current, phoneNumberId: event.target.value }))}
                      placeholder="123456789012345"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="business-account-id" className="text-sm font-medium text-foreground">
                      Business Account ID
                    </label>
                    <Input
                      id="business-account-id"
                      value={whatsAppForm.businessAccountId}
                      onChange={(event) => setWhatsAppForm((current) => ({ ...current, businessAccountId: event.target.value }))}
                      placeholder="Optional but recommended"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="access-token" className="text-sm font-medium text-foreground">
                    Access Token
                  </label>
                  <Input
                    id="access-token"
                    type="password"
                    value={whatsAppForm.accessToken}
                    onChange={(event) => setWhatsAppForm((current) => ({ ...current, accessToken: event.target.value }))}
                    placeholder="EAAG..."
                    required
                  />
                </div>

                <Button type="submit" disabled={isConnectingWhatsApp} className="gap-2">
                  {isConnectingWhatsApp ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquareText className="h-4 w-4" />}
                  Connect WhatsApp
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="border-border/70 shadow-sm">
            <CardHeader>
              <CardTitle>Email Forwarding</CardTitle>
              <CardDescription>Forward your support inbox to the inbound address below.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border border-border/60 bg-slate-950 px-4 py-4 text-slate-50 shadow-inner">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Inbound Address</p>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <code className="text-sm font-medium sm:text-[15px]">{forwardingAddress}</code>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="gap-2 self-start sm:self-auto"
                    onClick={() => void handleCopy(forwardingAddress, 'Forwarding address')}
                  >
                    <Copy className="h-4 w-4" />
                    Copy
                  </Button>
                </div>
              </div>
              <Alert>
                <Mail className="h-4 w-4" />
                <AlertTitle>Forward your support emails to this address</AlertTitle>
                <AlertDescription>
                  Messages sent to your forwarded inbox will land in SynapFlow for triage, routing, and reply generation.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          <Card className="border-border/70 shadow-sm">
            <CardHeader>
              <CardTitle>Connected Channels</CardTitle>
              <CardDescription>Live channel connections currently stored for this workspace.</CardDescription>
            </CardHeader>
            <CardContent>
              {connections.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
                  No channels are connected yet.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Channel</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Account</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {connections.map((connection) => {
                      const status = statusPresentation(connection.status)
                      return (
                        <TableRow key={connection.id}>
                          <TableCell className="font-medium">{formatChannelLabel(connection.channel)}</TableCell>
                          <TableCell>
                            <Badge className={status.className}>
                              <span className={cn('mr-1.5 inline-block h-1.5 w-1.5 rounded-full', status.dotClassName)} />
                              {status.label}
                            </Badge>
                          </TableCell>
                          <TableCell className="max-w-[220px] truncate text-sm text-muted-foreground">
                            {connection.account_identifier || 'Not available'}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

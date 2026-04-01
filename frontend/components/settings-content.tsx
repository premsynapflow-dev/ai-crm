"use client"

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  User,
  Building2,
  Key,
  Webhook,
  Bell,
  Users,
  Copy,
  Eye,
  EyeOff,
  Check,
  Loader2,
} from 'lucide-react'
import { getCompanySectorLabel, isRbiEligibleCompany } from '@/lib/company-profile'
import { settingsAPI, type SettingsSummary } from '@/lib/api/settings'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth-context'

function formatDate(value?: string | null) {
  if (!value) {
    return 'Not available'
  }

  return new Date(value).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function SettingsContent() {
  const { user } = useAuth()
  const [summary, setSummary] = useState<SettingsSummary | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [webhookUrl, setWebhookUrl] = useState('')
  const [isSavingWebhook, setIsSavingWebhook] = useState(false)
  const [isTestingWebhook, setIsTestingWebhook] = useState(false)

  useEffect(() => {
    let active = true

    settingsAPI.getSummary()
      .then((response) => {
        if (active) {
          setSummary(response)
          setWebhookUrl(response.webhooks[0]?.url ?? '')
        }
      })
      .catch(() => {
        if (active) {
          setSummary(null)
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  const handleCopy = (value: string, label: string) => {
    navigator.clipboard.writeText(value)
    toast.success(`${label} copied to clipboard`)
  }

  const handleSaveWebhook = async () => {
    setIsSavingWebhook(true)
    try {
      const response = await settingsAPI.updateSlackWebhook(webhookUrl)
      setSummary((current) => current ? {
        ...current,
        webhooks: response.webhook ? [response.webhook] : [],
      } : current)
      setWebhookUrl(response.webhook?.url ?? '')
      toast.success('Slack webhook saved')
    } catch {
      toast.error('Failed to save Slack webhook')
    } finally {
      setIsSavingWebhook(false)
    }
  }

  const handleTestWebhook = async () => {
    setIsTestingWebhook(true)
    try {
      await settingsAPI.testSlackWebhook(webhookUrl)
      toast.success('Test alert sent to Slack')
    } catch {
      toast.error('Failed to send test alert')
    } finally {
      setIsTestingWebhook(false)
    }
  }

  if (isLoading) {
    return <div className="flex h-96 items-center justify-center">Loading settings...</div>
  }

  if (!summary) {
    return <div className="flex h-96 items-center justify-center">Unable to load settings.</div>
  }

  const isBusinessPlan = new Set(['max', 'scale', 'enterprise']).has(summary.profile.plan_id ?? user?.plan ?? 'free')
  const isRbiEligible = isRbiEligibleCompany(summary.company.business_sector, summary.company.is_rbi_regulated)
  const initials = summary.profile.name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="mt-1 text-muted-foreground">View your live account, company, API, and integration details</p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="bg-muted/50 p-1">
          <TabsTrigger value="profile" className="gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="company" className="gap-2">
            <Building2 className="h-4 w-4" />
            Company
          </TabsTrigger>
          <TabsTrigger value="api" className="gap-2">
            <Key className="h-4 w-4" />
            API Keys
          </TabsTrigger>
          <TabsTrigger value="webhooks" className="gap-2">
            <Webhook className="h-4 w-4" />
            Webhooks
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="h-4 w-4" />
            Notifications
          </TabsTrigger>
          {(isBusinessPlan || summary.team_members.length > 1) && (
            <TabsTrigger value="team" className="gap-2">
              <Users className="h-4 w-4" />
              Team
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>Live account details for the current signed-in user</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-6">
                <Avatar className="h-20 w-20">
                  <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-2xl text-white">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-xl font-semibold">{summary.profile.name}</p>
                  <p className="text-muted-foreground">{summary.profile.email}</p>
                  <p className="text-sm text-muted-foreground">Joined {formatDate(summary.profile.created_at)}</p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-muted-foreground">Company</p>
                    <p className="mt-1 font-medium">{summary.profile.company}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-muted-foreground">Plan</p>
                    <p className="mt-1 font-medium capitalize">{summary.profile.plan_id}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-muted-foreground">Primary contact phone</p>
                    <p className="mt-1 font-medium">{summary.profile.company_phone || 'Not available'}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-muted-foreground">Company category</p>
                    <p className="mt-1 font-medium">{getCompanySectorLabel(summary.profile.business_sector)}</p>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="company">
          <Card>
            <CardHeader>
              <CardTitle>Company Details</CardTitle>
              <CardDescription>Account-level information currently stored in the database</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">Company Name</p>
                  <p className="mt-1 font-medium">{summary.company.name}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">Plan</p>
                  <p className="mt-1 font-medium capitalize">{summary.company.plan_id}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">Monthly Ticket Limit</p>
                  <p className="mt-1 font-medium">{summary.company.monthly_ticket_limit.toLocaleString()}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">Account Created</p>
                  <p className="mt-1 font-medium">{formatDate(summary.company.created_at)}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">Company contact phone</p>
                  <p className="mt-1 font-medium">{summary.company.contact_phone || 'Not available'}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">Company category</p>
                  <p className="mt-1 font-medium">{getCompanySectorLabel(summary.company.business_sector)}</p>
                </CardContent>
              </Card>
              <Card className="md:col-span-2">
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">RBI compliance eligibility</p>
                  <div className="mt-2 flex items-center gap-3">
                    <Badge className={isRbiEligible ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}>
                      {isRbiEligible ? 'Eligible' : 'Not eligible'}
                    </Badge>
                    <p className="text-sm text-muted-foreground">
                      RBI compliance tooling is shown only for companies identified as RBI-regulated financial institutions.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api">
          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>Your live client API key from the backend</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {!isBusinessPlan && (
                <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm text-orange-800">
                  API access is surfaced in the UI primarily for Business accounts, but the backend key shown below is the actual key currently stored for this client.
                </div>
              )}

              <div className="space-y-4 rounded-lg border p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Live API Key</p>
                    <p className="text-sm text-muted-foreground">Use this key for backend integrations and authenticated API calls</p>
                  </div>
                  <Badge className="bg-green-100 text-green-700">Active</Badge>
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex-1 overflow-x-auto rounded-md bg-muted p-3 font-mono text-sm">
                    {showApiKey ? summary.api_key : summary.api_key.replace(/.(?=.{4})/g, '*')}
                  </div>
                  <Button variant="outline" size="icon" onClick={() => setShowApiKey(!showApiKey)}>
                    {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => handleCopy(summary.api_key, 'API key')}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="webhooks">
          <Card>
            <CardHeader>
              <CardTitle>Webhooks</CardTitle>
              <CardDescription>Manage the live Slack webhook used for escalations and complaint alerts.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4 rounded-lg border p-4">
                <div>
                  <p className="font-medium">Slack webhook endpoint</p>
                  <p className="text-sm text-muted-foreground">
                    Use an incoming Slack webhook to receive complaint-created, escalated, and resolved events.
                  </p>
                </div>
                <div className="flex flex-col gap-3 md:flex-row">
                  <Input
                    value={webhookUrl}
                    onChange={(event) => setWebhookUrl(event.target.value)}
                    placeholder="https://hooks.slack.com/services/..."
                    className="font-mono text-sm"
                  />
                  <Button onClick={() => void handleSaveWebhook()} disabled={isSavingWebhook}>
                    {isSavingWebhook ? 'Saving...' : 'Save webhook'}
                  </Button>
                  <Button variant="outline" onClick={() => void handleTestWebhook()} disabled={isTestingWebhook || !webhookUrl.trim()}>
                    {isTestingWebhook ? 'Testing...' : 'Send test'}
                  </Button>
                </div>
              </div>

              {summary.webhooks.length === 0 ? (
                <div className="rounded-lg bg-muted/50 p-8 text-center text-muted-foreground">
                  No webhooks are configured in the database yet.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>URL</TableHead>
                      <TableHead>Events</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {summary.webhooks.map((webhook) => (
                      <TableRow key={webhook.id}>
                        <TableCell className="max-w-[320px] truncate font-mono text-sm">{webhook.url}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {webhook.events.map((event) => (
                              <Badge key={event} variant="outline" className="text-xs">
                                {event}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-green-100 text-green-700">{webhook.status}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => handleCopy(webhook.url, 'Webhook URL')}>
                            <Copy className="mr-2 h-4 w-4" />
                            Copy
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>What is currently real vs not yet persisted in the schema</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-600" />
                    <p className="font-medium">Webhook delivery status is real</p>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    If a Slack webhook is configured, escalations and complaint notifications can be sent there by the backend.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 text-muted-foreground" />
                    <p className="font-medium">Per-user notification toggles are not stored yet</p>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    The old demo switches have been removed so the page only shows settings that actually exist in your current data model.
                  </p>
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        </TabsContent>

        {(isBusinessPlan || summary.team_members.length > 1) && (
          <TabsContent value="team">
            <Card>
              <CardHeader>
                <CardTitle>Team Members</CardTitle>
                <CardDescription>Users currently associated with this client account</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Member</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Joined</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {summary.team_members.map((member) => (
                      <TableRow key={member.id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-xs text-white">
                                {member.name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-medium">{member.name}</p>
                              <p className="text-sm text-muted-foreground">{member.email}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{member.role}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-green-100 text-green-700">{member.status}</Badge>
                        </TableCell>
                        <TableCell>{formatDate(member.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}


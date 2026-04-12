"use client"

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { AlertCircle, Loader2, Mail, RefreshCw, Server } from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { inboxesAPI, type InboxConnection } from '@/lib/api/inboxes'

const initialImapForm = {
  email: '',
  imap_host: '',
  imap_port: '993',
  username: '',
  password: '',
}

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

function formatProvider(provider: string): string {
  return provider === 'gmail' ? 'Gmail' : provider === 'imap' ? 'IMAP' : provider
}

function statusBadgeClass(status: string): string {
  return status === 'active'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
    : 'border-slate-200 bg-slate-100 text-slate-700'
}

function formatCreatedAt(value: string | null): string {
  if (!value) {
    return 'Just connected'
  }

  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function InboxConnectionsContent() {
  const [inboxes, setInboxes] = useState<InboxConnection[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isPreparingGmail, setIsPreparingGmail] = useState(false)
  const [isSubmittingImap, setIsSubmittingImap] = useState(false)
  const [isImapDialogOpen, setIsImapDialogOpen] = useState(false)
  const [imapForm, setImapForm] = useState(initialImapForm)

  const loadInboxes = async (background = false) => {
    if (background) {
      setIsRefreshing(true)
    } else {
      setIsLoading(true)
    }

    try {
      const response = await inboxesAPI.list()
      setInboxes(response)
      setLoadError(null)
    } catch (error) {
      setLoadError(getErrorMessage(error, 'Unable to load connected inboxes right now.'))
    } finally {
      if (background) {
        setIsRefreshing(false)
      } else {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    void loadInboxes()
  }, [])

  const handleConnectGmail = async () => {
    setIsPreparingGmail(true)
    try {
      const response = await inboxesAPI.getGmailConnectUrl()
      window.location.assign(response.connect_url)
    } catch (error) {
      toast.error(getErrorMessage(error, 'Unable to start Gmail OAuth right now'))
      setIsPreparingGmail(false)
    }
  }

  const handleImapFieldChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target
    setImapForm((current) => ({ ...current, [name]: value }))
  }

  const handleConnectImap = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const parsedPort = Number(imapForm.imap_port)

    if (!Number.isInteger(parsedPort) || parsedPort < 1 || parsedPort > 65535) {
      toast.error('Enter a valid IMAP port')
      return
    }

    setIsSubmittingImap(true)
    try {
      await inboxesAPI.connectImap({
        email: imapForm.email.trim(),
        imap_host: imapForm.imap_host.trim(),
        imap_port: parsedPort,
        username: imapForm.username.trim(),
        password: imapForm.password,
      })
      toast.success('IMAP inbox connected successfully')
      setImapForm(initialImapForm)
      setIsImapDialogOpen(false)
      await loadInboxes(true)
    } catch (error) {
      toast.error(getErrorMessage(error, 'Unable to connect this IMAP inbox'))
    } finally {
      setIsSubmittingImap(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Connections</h1>
          <p className="mt-1 text-muted-foreground">
            Connect Gmail with OAuth or add another inbox over IMAP.
          </p>
        </div>

        <Button
          variant="outline"
          onClick={() => void loadInboxes(true)}
          disabled={isRefreshing || isLoading}
          className="gap-2 self-start md:self-auto"
        >
          {isRefreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </Button>
      </div>

      {loadError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Could not load inboxes</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-border/70 shadow-sm">
          <CardHeader>
            <div className="flex items-start gap-3">
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-emerald-700">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Connect Gmail</CardTitle>
                <CardDescription>
                  Authorize Gmail read access and attach the inbox to this tenant.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Uses Google OAuth with Gmail read-only access and your Google account email scope.
            </p>
            <Button onClick={() => void handleConnectGmail()} disabled={isPreparingGmail} className="gap-2">
              {isPreparingGmail ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
              Connect Gmail
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardHeader>
            <div className="flex items-start gap-3">
              <div className="rounded-2xl border border-sky-200 bg-sky-50 p-3 text-sky-700">
                <Server className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Connect Other Email</CardTitle>
                <CardDescription>
                  Validate an IMAP inbox before saving it to the workspace.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              IMAP passwords are encrypted before storage and are never returned in API responses.
            </p>
            <Button variant="outline" onClick={() => setIsImapDialogOpen(true)} className="gap-2">
              <Server className="h-4 w-4" />
              Connect Other Email
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/70 shadow-sm">
        <CardHeader>
          <CardTitle>Connected Inboxes</CardTitle>
          <CardDescription>Email connections stored for this tenant.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
              Loading inboxes...
            </div>
          ) : inboxes.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
              No inboxes are connected yet.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Connected</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {inboxes.map((inbox) => (
                  <TableRow key={inbox.id}>
                    <TableCell className="font-medium">{inbox.email}</TableCell>
                    <TableCell>{formatProvider(inbox.provider)}</TableCell>
                    <TableCell>
                      <Badge className={statusBadgeClass(inbox.status)}>
                        {inbox.status === 'active' ? 'Active' : 'Inactive'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatCreatedAt(inbox.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={isImapDialogOpen} onOpenChange={setIsImapDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connect Other Email</DialogTitle>
            <DialogDescription>
              Enter your IMAP server details. We will test the connection before saving it.
            </DialogDescription>
          </DialogHeader>

          <form className="space-y-4" onSubmit={(event) => void handleConnectImap(event)}>
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-foreground">
                Email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                value={imapForm.email}
                onChange={handleImapFieldChange}
                placeholder="support@example.com"
                required
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="imap_host" className="text-sm font-medium text-foreground">
                  IMAP Host
                </label>
                <Input
                  id="imap_host"
                  name="imap_host"
                  value={imapForm.imap_host}
                  onChange={handleImapFieldChange}
                  placeholder="imap.example.com"
                  required
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="imap_port" className="text-sm font-medium text-foreground">
                  Port
                </label>
                <Input
                  id="imap_port"
                  name="imap_port"
                  inputMode="numeric"
                  value={imapForm.imap_port}
                  onChange={handleImapFieldChange}
                  placeholder="993"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium text-foreground">
                Username
              </label>
              <Input
                id="username"
                name="username"
                value={imapForm.username}
                onChange={handleImapFieldChange}
                placeholder="support@example.com"
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-foreground">
                Password
              </label>
              <Input
                id="password"
                name="password"
                type="password"
                value={imapForm.password}
                onChange={handleImapFieldChange}
                placeholder="App password or mailbox password"
                required
              />
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsImapDialogOpen(false)} disabled={isSubmittingImap}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmittingImap} className="gap-2">
                {isSubmittingImap ? <Loader2 className="h-4 w-4 animate-spin" /> : <Server className="h-4 w-4" />}
                Save IMAP Inbox
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}


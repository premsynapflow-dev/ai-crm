"use client"

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowLeft, Loader2, MessageSquare, Tag, Ticket, TrendingDown } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Customer360Skeleton } from '@/components/ui/skeletons'
import { customersAPI, type Customer360Response, type CustomerTimelineItem } from '@/lib/api/customers'

function formatDate(value?: string | null) {
  if (!value) {
    return 'Not available'
  }

  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatResponseTime(value?: number | null) {
  if (value === null || value === undefined) {
    return 'Not tracked'
  }

  if (value < 60) {
    return `${Math.round(value)}s`
  }
  if (value < 3600) {
    return `${Math.round(value / 60)}m`
  }
  return `${(value / 3600).toFixed(1)}h`
}

function sentimentTone(label: string) {
  if (label === 'negative') {
    return 'bg-rose-100 text-rose-700 border-rose-200'
  }
  if (label === 'positive') {
    return 'bg-emerald-100 text-emerald-700 border-emerald-200'
  }
  return 'bg-slate-100 text-slate-700 border-slate-200'
}

function churnTone(level: string) {
  if (level === 'high') {
    return 'bg-rose-600 text-white'
  }
  if (level === 'medium') {
    return 'bg-amber-500 text-white'
  }
  return 'bg-emerald-600 text-white'
}

function timelineIcon(item: CustomerTimelineItem) {
  if (item.type === 'ticket') {
    return <Ticket className="h-4 w-4" />
  }
  if (item.type === 'action') {
    return <Tag className="h-4 w-4" />
  }
  return <MessageSquare className="h-4 w-4" />
}

interface Customer360PageProps {
  customerId: string
}

export function Customer360Page({ customerId }: Customer360PageProps) {
  const [data, setData] = useState<Customer360Response | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSavingTags, setIsSavingTags] = useState(false)
  const [isSavingNotes, setIsSavingNotes] = useState(false)
  const [pendingTag, setPendingTag] = useState('')
  const [draftNotes, setDraftNotes] = useState('')

  useEffect(() => {
    let active = true

    async function loadCustomer360() {
      setIsLoading(true)
      try {
        const response = await customersAPI.get360(customerId)
        if (!active) {
          return
        }
        setData(response)
        setDraftNotes(response.identity.notes ?? '')
      } catch {
        if (active) {
          setData(null)
          toast.error('Failed to load customer intelligence')
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadCustomer360()

    return () => {
      active = false
    }
  }, [customerId])

  const refresh = async () => {
    const response = await customersAPI.get360(customerId)
    setData(response)
    setDraftNotes(response.identity.notes ?? '')
  }

  const handleAddTag = async () => {
    const nextTag = pendingTag.trim()
    if (!data || !nextTag) {
      return
    }

    const nextTags = Array.from(new Set([...data.identity.tags, nextTag]))
    setIsSavingTags(true)
    try {
      await customersAPI.update(customerId, { tags: nextTags })
      await refresh()
      setPendingTag('')
      toast.success('Customer tag updated')
    } catch {
      toast.error('Failed to update customer tags')
    } finally {
      setIsSavingTags(false)
    }
  }

  const handleSaveNotes = async () => {
    if (!data) {
      return
    }

    setIsSavingNotes(true)
    try {
      await customersAPI.update(customerId, { notes: draftNotes })
      await refresh()
      toast.success('Customer notes saved')
    } catch {
      toast.error('Failed to save customer notes')
    } finally {
      setIsSavingNotes(false)
    }
  }

  if (isLoading) {
    return <Customer360Skeleton />
  }

  if (!data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Customer not available</CardTitle>
          <CardDescription>The requested customer profile could not be loaded.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link href="/customers">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to customers
            </Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-4">
          <Button asChild variant="ghost" className="px-0 text-muted-foreground hover:bg-transparent">
            <Link href="/customers">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to customer directory
            </Link>
          </Button>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-bold text-foreground">
                {data.identity.name || data.identity.primary_email || 'Customer 360'}
              </h1>
              <Badge className={sentimentTone(data.sentiment.label)}>
                {data.sentiment.label} sentiment
              </Badge>
              <Badge className={churnTone(data.churn_risk)}>
                {data.churn_risk} churn risk
              </Badge>
            </div>
            <p className="text-muted-foreground">{data.identity.primary_email || 'No primary email on record'}</p>
            <div className="flex flex-wrap gap-2">
              {data.identity.tags.length === 0 ? (
                <Badge variant="outline">No tags yet</Badge>
              ) : (
                data.identity.tags.map((tag) => (
                  <Badge key={tag} variant="outline" className="rounded-full px-3 py-1">
                    {tag}
                  </Badge>
                ))
              )}
            </div>
          </div>
        </div>

        <Card className="w-full max-w-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Tag customer</CardTitle>
            <CardDescription>Highlight VIP, risky, billing-watch, or renewal-ready accounts.</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Input
              value={pendingTag}
              onChange={(event) => setPendingTag(event.target.value)}
              placeholder="Add a tag"
            />
            <Button onClick={() => void handleAddTag()} disabled={isSavingTags || !pendingTag.trim()}>
              {isSavingTags ? 'Saving...' : 'Add'}
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground">Total tickets</p>
            <p className="mt-2 text-3xl font-semibold">{data.metrics.total_tickets}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground">Open tickets</p>
            <p className="mt-2 text-3xl font-semibold">{data.metrics.open_tickets}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground">Total messages</p>
            <p className="mt-2 text-3xl font-semibold">{data.metrics.total_messages}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground">Last contacted</p>
            <p className="mt-2 text-base font-semibold">{formatDate(data.metrics.last_contacted_at)}</p>
            <p className="mt-2 text-xs text-muted-foreground">Avg response {formatResponseTime(data.metrics.avg_response_time)}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Active Tickets</CardTitle>
              <CardDescription>Open customer work that may need immediate ownership.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.active_tickets.length === 0 ? (
                <div className="rounded-2xl border border-dashed p-6 text-sm text-muted-foreground">
                  No active tickets for this customer.
                </div>
              ) : (
                data.active_tickets.map((ticket) => (
                  <div key={ticket.id} className="rounded-2xl border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{ticket.ticket_number}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{ticket.summary}</p>
                      </div>
                      <div className="flex gap-2">
                        <Badge variant="outline">{ticket.resolution_status}</Badge>
                        <Badge variant="outline">{ticket.assigned_to || 'Unassigned'}</Badge>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>{ticket.category}</span>
                      <span>{ticket.source}</span>
                      <span>{formatDate(ticket.created_at)}</span>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Unified Timeline</CardTitle>
              <CardDescription>Messages, tickets, and internal actions merged into one stream.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.timeline.length === 0 ? (
                <div className="rounded-2xl border border-dashed p-6 text-sm text-muted-foreground">
                  No linked activity yet.
                </div>
              ) : (
                data.timeline.map((item) => (
                  <div key={item.id} className="rounded-2xl border p-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-1 rounded-full bg-slate-100 p-2 text-slate-700">
                        {timelineIcon(item)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">{item.title}</p>
                            <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{item.type}</p>
                          </div>
                          <Badge variant="outline">{item.status || 'recorded'}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">{item.body}</p>
                        <p className="mt-3 text-xs text-muted-foreground">{formatDate(item.timestamp)}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Insights</CardTitle>
              <CardDescription>Signals generated from recent activity and support history.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.insights.length === 0 ? (
                <div className="rounded-2xl border border-dashed p-6 text-sm text-muted-foreground">
                  No notable customer signals yet.
                </div>
              ) : (
                data.insights.map((insight) => (
                  <div key={insight} className="flex items-start gap-3 rounded-2xl border p-4">
                    <div className="rounded-full bg-amber-100 p-2 text-amber-700">
                      {insight.toLowerCase().includes('churn') ? (
                        <AlertTriangle className="h-4 w-4" />
                      ) : (
                        <TrendingDown className="h-4 w-4" />
                      )}
                    </div>
                    <p className="text-sm">{insight}</p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Customer Notes</CardTitle>
              <CardDescription>Keep a persistent internal summary on the profile itself.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={draftNotes}
                onChange={(event) => setDraftNotes(event.target.value)}
                placeholder="Capture account context, escalations, or relationship details"
                className="min-h-36"
              />
              <Button onClick={() => void handleSaveNotes()} disabled={isSavingNotes}>
                {isSavingNotes ? 'Saving...' : 'Save notes'}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

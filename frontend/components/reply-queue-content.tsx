"use client"

import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { UpgradePrompt } from '@/components/upgrade-prompt'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { getFeatureGateDetail } from '@/lib/api-error'
import { replyQueueAPI, type ReplyQueueItem } from '@/lib/api/reply-queue'

function formatDate(value?: string | null) {
  if (!value) {
    return 'Not available'
  }
  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ReplyQueueContent() {
  const [status, setStatus] = useState('pending')
  const [items, setItems] = useState<ReplyQueueItem[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [processingId, setProcessingId] = useState<string | null>(null)
  const [featureLocked, setFeatureLocked] = useState(false)

  useEffect(() => {
    let active = true

    async function loadQueue() {
      setLoading(true)
      try {
        const response = await replyQueueAPI.list(status)
        if (!active) {
          return
        }
        setItems(response.items)
        setDrafts(
          Object.fromEntries(
            response.items.map((item) => [item.id, item.edited_reply || item.generated_reply || ''])
          )
        )
        setFeatureLocked(false)
      } catch (error) {
        if (!active) {
          return
        }
        setItems([])
        setFeatureLocked(Boolean(getFeatureGateDetail(error)))
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadQueue()

    return () => {
      active = false
    }
  }, [status])

  const handleApprove = async (item: ReplyQueueItem) => {
    setProcessingId(item.id)
    try {
      await replyQueueAPI.approve(item.id, drafts[item.id])
      toast.success('AI reply approved and dispatched')
      setItems((current) => current.filter((entry) => entry.id !== item.id))
    } catch {
      toast.error('Failed to approve reply')
    } finally {
      setProcessingId(null)
    }
  }

  const handleReject = async (item: ReplyQueueItem) => {
    setProcessingId(item.id)
    try {
      await replyQueueAPI.reject(item.id, 'Needs manual handling')
      toast.success('AI reply rejected')
      setItems((current) => current.filter((entry) => entry.id !== item.id))
    } catch {
      toast.error('Failed to reject reply')
    } finally {
      setProcessingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">AI Reply Queue</h1>
        <p className="mt-1 text-muted-foreground">Review, edit, approve, or reject drafted replies before they go out.</p>
      </div>

      {featureLocked ? (
        <UpgradePrompt
          title="Unlock AI approval queue"
          description="Use the human-in-the-loop review flow for generated customer replies."
          requiredPlan="Starter"
        />
      ) : (
        <Tabs value={status} onValueChange={setStatus} className="space-y-6">
          <TabsList>
            <TabsTrigger value="pending">Pending</TabsTrigger>
            <TabsTrigger value="approved">Approved</TabsTrigger>
            <TabsTrigger value="rejected">Rejected</TabsTrigger>
          </TabsList>

          <TabsContent value={status} className="space-y-4">
            {loading ? (
              <div className="flex h-64 items-center justify-center gap-3 rounded-2xl border bg-card">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-muted-foreground">Loading AI reply queue...</span>
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-2xl border border-dashed p-10 text-center text-sm text-muted-foreground">
                No {status} queue items right now.
              </div>
            ) : (
              items.map((item) => (
                <Card key={item.id}>
                  <CardHeader>
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <CardTitle>{item.ticket_number || 'Unnumbered ticket'}</CardTitle>
                        <CardDescription>{item.ticket_summary || 'No ticket summary available'}</CardDescription>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">{item.status}</Badge>
                        <Badge className="bg-blue-100 text-blue-700">
                          Confidence {Math.round((item.confidence_score || 0) * 100)}%
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      <div className="rounded-xl bg-slate-50 p-4 text-sm">
                        <p className="font-medium text-slate-900">Generated at</p>
                        <p className="mt-2 text-muted-foreground">{formatDate(item.created_at)}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4 text-sm">
                        <p className="font-medium text-slate-900">Factual consistency</p>
                        <p className="mt-2 text-muted-foreground">{item.factual_consistency_score ?? 'Not scored'}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4 text-sm">
                        <p className="font-medium text-slate-900">Safety checks</p>
                        <p className="mt-2 text-muted-foreground">
                          {item.hallucination_check_passed ? 'Passed hallucination checks' : 'Needs review'}
                        </p>
                      </div>
                    </div>

                    <div>
                      <p className="mb-2 text-sm font-medium text-slate-900">Draft reply</p>
                      <Textarea
                        value={drafts[item.id] ?? ''}
                        onChange={(event) => setDrafts((current) => ({ ...current, [item.id]: event.target.value }))}
                        rows={7}
                        disabled={status !== 'pending'}
                      />
                    </div>

                    {status === 'pending' ? (
                      <div className="flex flex-wrap gap-3">
                        <Button onClick={() => void handleApprove(item)} disabled={processingId === item.id}>
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                          {processingId === item.id ? 'Approving...' : 'Approve & send'}
                        </Button>
                        <Button variant="outline" onClick={() => void handleReject(item)} disabled={processingId === item.id}>
                          <AlertTriangle className="mr-2 h-4 w-4" />
                          Reject for manual follow-up
                        </Button>
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                        <span className="inline-flex items-center gap-2">
                          {status === 'approved' ? <ShieldCheck className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                          Reviewed by {item.reviewed_by || 'system'}
                        </span>
                        <span>{formatDate(item.reviewed_at)}</span>
                        {item.rejection_reason ? <span>Reason: {item.rejection_reason}</span> : null}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}

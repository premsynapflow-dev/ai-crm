"use client"

import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Loader2,
  Mail,
  MessageSquareText,
  Paperclip,
  Phone,
  Send,
  Sparkles,
  User,
} from 'lucide-react'

import { UpgradePrompt } from '@/components/upgrade-prompt'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/lib/auth-context'
import { complaintsAPI, type Complaint, type ComplaintDetail, type ComplaintThreadMessage } from '@/lib/api/complaints'
import { planIncludesFeature } from '@/lib/plan-features'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface ComplaintDetailModalProps {
  complaint: Complaint | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onComplaintUpdated?: (complaint: Complaint) => void
}

const priorityColors: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

const sentimentColors: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-700',
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-amber-100 text-amber-700',
  resolved: 'bg-green-100 text-green-700',
  escalated: 'bg-red-100 text-red-700',
}

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as Record<string, unknown>).message)
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

function formatDateTime(value?: string | null): string {
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

function waitingLabel(value?: string): string {
  if (value === 'customer') {
    return 'Waiting on customer'
  }
  return 'Waiting on support'
}

function MessageBubble({ message }: { message: ComplaintThreadMessage }) {
  const isOutbound = message.direction === 'outbound'
  const attachmentNames = (message.attachments ?? [])
    .map((attachment) => attachment.filename)
    .filter((filename): filename is string => Boolean(filename))

  return (
    <div className={cn('flex', isOutbound ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[min(920px,84%)] rounded-2xl border px-4 py-3 shadow-sm',
          isOutbound
            ? 'border-sky-200 bg-sky-50 text-slate-800'
            : 'border-slate-200 bg-white text-slate-900',
        )}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <Badge variant="outline" className="border-slate-200 bg-white/70">
            {isOutbound ? 'Support' : 'Customer'}
          </Badge>
          <span className="font-medium text-slate-700">{message.senderName}</span>
          <span>{formatDateTime(message.timestamp)}</span>
        </div>
        <div className="whitespace-pre-wrap break-words text-sm leading-6">{message.messageText || 'No message body available.'}</div>
        {attachmentNames.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {attachmentNames.map((filename) => (
              <span
                key={filename}
                className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600"
              >
                <Paperclip className="h-3 w-3" />
                {filename}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function ComplaintDetailModal({
  complaint,
  open,
  onOpenChange,
  onComplaintUpdated,
}: ComplaintDetailModalProps) {
  const { user } = useAuth()
  const [currentComplaint, setCurrentComplaint] = useState<ComplaintDetail | null>(null)
  const [reply, setReply] = useState('')
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isEscalating, setIsEscalating] = useState(false)
  const [isResolving, setIsResolving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    if (!complaint) {
      setCurrentComplaint(null)
      setReply('')
      setLoadError(null)
      return
    }
    setCurrentComplaint({
      ...complaint,
      threadMessages: [],
      conversationSummary: undefined,
    })
    setReply(complaint.suggestedResponse ?? '')
    setLoadError(null)
  }, [complaint])

  useEffect(() => {
    if (!open || !complaint) {
      return
    }

    let active = true
    setIsLoadingDetail(true)
    setLoadError(null)

    complaintsAPI.getById(complaint.id)
      .then((detail) => {
        if (!active) {
          return
        }
        setCurrentComplaint(detail)
      })
      .catch((error) => {
        if (!active) {
          return
        }
        setLoadError(getErrorMessage(error, 'Failed to load the full conversation thread'))
      })
      .finally(() => {
        if (active) {
          setIsLoadingDetail(false)
        }
      })

    return () => {
      active = false
    }
  }, [open, complaint])

  if (!currentComplaint) {
    return null
  }

  const applyUpdate = (updatedComplaint: Complaint) => {
    setCurrentComplaint((current) => {
      if (!current) {
        return {
          ...(updatedComplaint as ComplaintDetail),
          threadMessages: [],
          conversationSummary: undefined,
        }
      }
      return {
        ...current,
        ...updatedComplaint,
        threadMessages: 'threadMessages' in updatedComplaint ? (updatedComplaint as ComplaintDetail).threadMessages : current.threadMessages,
        conversationSummary: 'conversationSummary' in updatedComplaint ? (updatedComplaint as ComplaintDetail).conversationSummary : current.conversationSummary,
      }
    })
    onComplaintUpdated?.(updatedComplaint)
  }

  const handleRegenerate = async () => {
    if (!planIncludesFeature(user?.plan_id, 'ai_suggested_responses')) {
      toast.error('AI suggested responses require the Pro plan or higher')
      return
    }

    setIsRegenerating(true)
    try {
      const suggestion = await complaintsAPI.suggestReply(currentComplaint.id)
      setCurrentComplaint((current) => current ? { ...current, suggestedResponse: suggestion.suggestedResponse } : current)
      setReply(suggestion.suggestedResponse ?? '')
      toast.success('Reply generated from the full thread')
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to generate a reply'))
    } finally {
      setIsRegenerating(false)
    }
  }

  const handleSendReply = async () => {
    if (!reply.trim()) {
      toast.error('Please enter a reply')
      return
    }

    setIsSending(true)
    try {
      const updatedComplaint = await complaintsAPI.reply(currentComplaint.id, reply)
      applyUpdate(updatedComplaint)
      setReply('')
      toast.success('Reply sent successfully')
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to send reply'))
    } finally {
      setIsSending(false)
    }
  }

  const handleEscalate = async () => {
    setIsEscalating(true)
    try {
      const updatedComplaint = await complaintsAPI.escalate(currentComplaint.id)
      applyUpdate(updatedComplaint)
      toast.success('Complaint escalated')
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to escalate complaint'))
    } finally {
      setIsEscalating(false)
    }
  }

  const handleMarkResolved = async () => {
    setIsResolving(true)
    try {
      const updatedComplaint = await complaintsAPI.markResolved(currentComplaint.id)
      applyUpdate(updatedComplaint)
      toast.success('Complaint marked as resolved')
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to mark complaint as resolved'))
    } finally {
      setIsResolving(false)
    }
  }

  const hasSuggestedResponses = planIncludesFeature(user?.plan_id, 'ai_suggested_responses')
  const threadMessages = currentComplaint.threadMessages.length > 0
    ? currentComplaint.threadMessages
    : [{
        id: `${currentComplaint.id}-fallback`,
        direction: 'inbound',
        channel: 'email',
        senderName: currentComplaint.customerName,
        senderId: currentComplaint.customerEmail,
        messageText: currentComplaint.message,
        timestamp: currentComplaint.createdAt,
        status: 'received',
        attachments: [],
      }]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[95vh] overflow-hidden p-0 sm:max-w-[calc(100vw-2.5rem)] xl:max-w-[1500px] 2xl:max-w-[1650px]">
        <DialogHeader className="border-b border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(241,245,249,0.94))] px-6 py-5 pr-16 xl:px-8 xl:py-6">
          <DialogTitle className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-xs uppercase tracking-[0.18em] text-slate-500">
                {currentComplaint.ticketId ?? 'Ticket pending'}
              </span>
              <Separator orientation="vertical" className="hidden h-4 sm:block" />
              <span className="max-w-[min(100%,1000px)] break-words text-[clamp(1.35rem,2vw,2.3rem)] leading-[1.15] text-slate-950">
                {currentComplaint.subject}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className={cn('capitalize', statusColors[currentComplaint.status])}>
                {currentComplaint.status.replace('-', ' ')}
              </Badge>
              <Badge className={cn('capitalize', priorityColors[currentComplaint.priority])}>
                {currentComplaint.priority}
              </Badge>
              <Badge className={cn('capitalize', sentimentColors[currentComplaint.sentiment])}>
                {currentComplaint.sentiment}
              </Badge>
              <Badge variant="outline" className="capitalize">
                {currentComplaint.category}
              </Badge>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="grid h-[calc(95vh-128px)] gap-0 xl:grid-cols-[minmax(0,1.7fr)_minmax(420px,0.95fr)] 2xl:grid-cols-[minmax(0,1.9fr)_minmax(480px,560px)]">
          <div className="flex min-h-0 flex-col border-b border-slate-200 xl:border-b-0 xl:border-r">
            <div className="flex flex-wrap gap-4 px-6 py-4 xl:px-8">
              <div className="flex items-center gap-2 text-sm text-slate-700">
                <User className="h-4 w-4 text-slate-500" />
                <span className="font-medium">{currentComplaint.customerName}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Mail className="h-4 w-4 text-slate-500" />
                <span>{currentComplaint.customerEmail || 'No email provided'}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Phone className="h-4 w-4 text-slate-500" />
                <span>{currentComplaint.customerPhone || 'No phone provided'}</span>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col px-6 pb-6 xl:px-8 xl:pb-8">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Conversation thread</p>
                  <p className="text-sm text-slate-500">Full message history for this complaint.</p>
                </div>
                {isLoadingDetail && (
                  <div className="inline-flex items-center gap-2 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading thread
                  </div>
                )}
              </div>

              {loadError ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {loadError}
                </div>
              ) : (
                <ScrollArea className="min-h-0 flex-1 rounded-3xl border border-slate-200 bg-slate-50/80">
                  <div className="space-y-5 p-4 xl:p-6">
                    {threadMessages.map((message) => (
                      <MessageBubble key={message.id} message={message} />
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          </div>

          <div className="flex min-h-0 flex-col gap-5 overflow-y-auto px-6 py-6 xl:px-8 xl:py-8">
            <Card className="gap-4 border-slate-200 bg-white/95 shadow-[0_20px_50px_-35px_rgba(15,23,42,0.35)]">
              <CardHeader className="gap-1">
                <CardTitle className="flex items-center gap-2 text-base">
                  <MessageSquareText className="h-4 w-4 text-sky-600" />
                  Conversation summary
                </CardTitle>
                <CardDescription>Important points from this thread only.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Waiting on</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">
                      {waitingLabel(currentComplaint.conversationSummary?.waitingOn)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Updated</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">
                      {formatDateTime(currentComplaint.conversationSummary?.lastUpdatedAt ?? currentComplaint.updatedAt)}
                    </p>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 px-3 py-3 text-center">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Messages</p>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {currentComplaint.conversationSummary?.messageCount ?? threadMessages.length}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 px-3 py-3 text-center">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Customer</p>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {currentComplaint.conversationSummary?.customerMessageCount ?? threadMessages.filter((message) => message.direction !== 'outbound').length}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 px-3 py-3 text-center">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Support</p>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {currentComplaint.conversationSummary?.supportMessageCount ?? threadMessages.filter((message) => message.direction === 'outbound').length}
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  {(currentComplaint.conversationSummary?.keyPoints ?? [currentComplaint.message]).map((point) => (
                    <div key={point} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-700">
                      {point}
                    </div>
                  ))}
                </div>

                {(currentComplaint.conversationSummary?.attachments?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {(currentComplaint.conversationSummary?.attachments ?? []).map((attachment) => (
                      <span
                        key={attachment}
                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600"
                      >
                        <Paperclip className="h-3 w-3" />
                        {attachment}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="gap-4 border-slate-200 bg-white/95 shadow-[0_20px_50px_-35px_rgba(15,23,42,0.35)]">
              <CardHeader className="gap-1">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Bot className="h-4 w-4 text-sky-600" />
                      Draft reply
                    </CardTitle>
                    <CardDescription>Generate a reply using the full conversation above.</CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRegenerate}
                    disabled={isRegenerating || !hasSuggestedResponses}
                    className="gap-2"
                  >
                    {isRegenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    Generate Reply
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {!hasSuggestedResponses && (
                  <UpgradePrompt
                    compact
                    title="Unlock AI generated replies"
                    description="Generate replies from the full complaint thread without switching context."
                    requiredPlan="Pro"
                  />
                )}

                <Textarea
                  placeholder="Generate a reply or write one manually..."
                  value={reply}
                  onChange={(event) => setReply(event.target.value)}
                  rows={10}
                  className="resize-none rounded-2xl border-slate-200"
                />

                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={handleSendReply}
                    disabled={isSending}
                    className="gap-2 bg-slate-950 text-white hover:bg-slate-800"
                  >
                    {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    Send Reply
                  </Button>
                  <Button variant="outline" onClick={handleEscalate} disabled={isEscalating} className="gap-2">
                    {isEscalating ? <Loader2 className="h-4 w-4 animate-spin" /> : <AlertTriangle className="h-4 w-4" />}
                    Escalate
                  </Button>
                  <Button variant="outline" onClick={handleMarkResolved} disabled={isResolving} className="gap-2">
                    {isResolving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                    Mark Resolved
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card className="gap-4 border-slate-200 bg-white/95">
              <CardHeader className="gap-1">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Clock3 className="h-4 w-4 text-sky-600" />
                  Ticket details
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Created</p>
                  <p className="mt-1 font-medium text-slate-900">{formatDateTime(currentComplaint.createdAt)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">First response</p>
                  <p className="mt-1 font-medium text-slate-900">{formatDateTime(currentComplaint.firstResponseAt)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">AI confidence</p>
                  <p className="mt-1 font-medium text-slate-900">{currentComplaint.aiConfidence}%</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Thread</p>
                  <p className="mt-1 break-all font-medium text-slate-900">{currentComplaint.threadId || 'Not available'}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}


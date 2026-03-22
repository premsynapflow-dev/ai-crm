"use client"

import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import {
  User,
  Mail,
  Phone,
  Brain,
  Sparkles,
  Send,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
} from 'lucide-react'
import { complaintsAPI, type Complaint } from '@/lib/api/complaints'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth-context'
import { planIncludesFeature } from '@/lib/plan-features'
import { UpgradePrompt } from '@/components/upgrade-prompt'

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

export function ComplaintDetailModal({
  complaint,
  open,
  onOpenChange,
  onComplaintUpdated,
}: ComplaintDetailModalProps) {
  const { user } = useAuth()
  const [currentComplaint, setCurrentComplaint] = useState<Complaint | null>(complaint)
  const [reply, setReply] = useState('')
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isEscalating, setIsEscalating] = useState(false)
  const [isResolving, setIsResolving] = useState(false)

  useEffect(() => {
    setCurrentComplaint(complaint)
    setReply(complaint?.suggestedResponse ?? '')
  }, [complaint])

  if (!currentComplaint) {
    return null
  }

  const applyUpdate = (updatedComplaint: Complaint) => {
    setCurrentComplaint(updatedComplaint)
    onComplaintUpdated?.(updatedComplaint)
  }

  const handleUseAISuggestion = () => {
    if (currentComplaint.suggestedResponse) {
      setReply(currentComplaint.suggestedResponse)
      toast.success('AI suggestion applied')
    }
  }

  const handleRegenerate = async () => {
    if (!planIncludesFeature(user?.plan_id, 'ai_suggested_responses')) {
      toast.error('AI suggested responses require the Pro plan or higher')
      return
    }

    setIsRegenerating(true)
    try {
      const suggestion = await complaintsAPI.suggestReply(currentComplaint.id)
      const updatedComplaint = {
        ...currentComplaint,
        suggestedResponse: suggestion.suggestedResponse,
      }
      applyUpdate(updatedComplaint)
      setReply(suggestion.suggestedResponse ?? '')
      toast.success('New response generated')
    } catch {
      toast.error('Failed to generate a new response')
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
      onOpenChange(false)
    } catch {
      toast.error('Failed to send reply')
    } finally {
      setIsSending(false)
    }
  }

  const handleEscalate = async () => {
    setIsEscalating(true)
    try {
      const updatedComplaint = await complaintsAPI.escalate(currentComplaint.id)
      applyUpdate(updatedComplaint)
      toast.success('Complaint escalated to manager')
      onOpenChange(false)
    } catch {
      toast.error('Failed to escalate complaint')
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
      onOpenChange(false)
    } catch {
      toast.error('Failed to mark complaint as resolved')
    } finally {
      setIsResolving(false)
    }
  }

  const timeline = [
    { time: currentComplaint.createdAt, action: 'Complaint received', icon: Mail },
    { time: currentComplaint.createdAt, action: 'AI analysis completed', icon: Brain },
    { time: currentComplaint.updatedAt, action: 'Status updated', icon: Clock },
  ]
  const hasSuggestedResponses = planIncludesFeature(user?.plan_id, 'ai_suggested_responses')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="font-mono text-sm text-muted-foreground">{currentComplaint.id}</span>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-xl">{currentComplaint.subject}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          <div className="flex flex-wrap gap-4 rounded-lg bg-muted/50 p-4">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{currentComplaint.customerName}</span>
            </div>
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{currentComplaint.customerEmail || 'No email provided'}</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{currentComplaint.customerPhone || 'No phone provided'}</span>
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold">Complaint Details</h4>
            <p className="rounded-lg border bg-card p-4 leading-relaxed text-muted-foreground">
              {currentComplaint.message}
            </p>
          </div>

          <div className="rounded-lg border border-blue-100 bg-gradient-to-br from-blue-50 to-purple-50 p-4">
            <div className="mb-4 flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              <h4 className="font-semibold text-primary">AI Analysis</h4>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Category</p>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="capitalize">
                    {currentComplaint.category}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {currentComplaint.aiConfidence}% confidence
                  </span>
                </div>
                <Progress value={currentComplaint.aiConfidence} className="mt-2 h-1" />
              </div>

              <div>
                <p className="mb-1 text-xs text-muted-foreground">Priority</p>
                <div className="flex items-center gap-2">
                  <Badge className={cn('capitalize', priorityColors[currentComplaint.priority])}>
                    {currentComplaint.priority}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {Math.max(currentComplaint.aiConfidence - 3, 0)}% confidence
                  </span>
                </div>
                <Progress value={Math.max(currentComplaint.aiConfidence - 3, 0)} className="mt-2 h-1" />
              </div>

              <div>
                <p className="mb-1 text-xs text-muted-foreground">Sentiment</p>
                <div className="flex items-center gap-2">
                  <Badge className={cn('capitalize', sentimentColors[currentComplaint.sentiment])}>
                    {currentComplaint.sentiment}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {Math.min(currentComplaint.aiConfidence + 2, 100)}% confidence
                  </span>
                </div>
                <Progress value={Math.min(currentComplaint.aiConfidence + 2, 100)} className="mt-2 h-1" />
              </div>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h4 className="text-sm font-semibold">AI Suggested Response</h4>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRegenerate}
                disabled={isRegenerating || !hasSuggestedResponses}
              >
                {isRegenerating ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Sparkles className="mr-1 h-4 w-4" />}
                Refresh
              </Button>
            </div>
            {!hasSuggestedResponses && (
              <div className="mb-3">
                <UpgradePrompt
                  compact
                  title="Unlock AI suggested responses"
                  description="Use similar resolved complaints to draft empathetic replies faster."
                  requiredPlan="Pro"
                />
              </div>
            )}
            <div className="rounded-lg border bg-muted/50 p-4 text-sm whitespace-pre-line">
              {hasSuggestedResponses
                ? (currentComplaint.suggestedResponse || 'No AI suggestion available yet.')
                : 'Upgrade to Pro or higher to generate AI suggested responses.'}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={handleUseAISuggestion}
              disabled={!currentComplaint.suggestedResponse || !hasSuggestedResponses}
            >
              <Sparkles className="mr-1 h-4 w-4" />
              Use This Response
            </Button>
          </div>

          <div>
            <h4 className="mb-3 text-sm font-semibold">Timeline</h4>
            <div className="space-y-3">
              {timeline.map((item, index) => (
                <div key={index} className="flex items-start gap-3">
                  <div className="rounded-full bg-muted p-2">
                    <item.icon className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{item.action}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(item.time).toLocaleString('en-IN', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold">Send Reply</h4>
            <Textarea
              placeholder="Type your response..."
              value={reply}
              onChange={(event) => setReply(event.target.value)}
              rows={4}
              className="resize-none"
            />
          </div>

          <div className="flex flex-wrap gap-3 pt-2">
            <Button
              onClick={handleSendReply}
              disabled={isSending}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              <Send className="mr-2 h-4 w-4" />
              {isSending ? 'Sending...' : 'Send Reply'}
            </Button>
            <Button variant="outline" onClick={handleEscalate} disabled={isEscalating}>
              <AlertTriangle className="mr-2 h-4 w-4" />
              {isEscalating ? 'Escalating...' : 'Escalate to Manager'}
            </Button>
            <Button
              variant="outline"
              onClick={handleMarkResolved}
              disabled={isResolving}
              className="text-green-600 hover:text-green-700"
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {isResolving ? 'Updating...' : 'Mark as Resolved'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}


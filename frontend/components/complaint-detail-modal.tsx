"use client"

import { useState } from 'react'
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
  RefreshCw,
  Send,
  AlertTriangle,
  CheckCircle2,
  Clock
} from 'lucide-react'
import { type Complaint } from '@/lib/api/complaints'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface ComplaintDetailModalProps {
  complaint: Complaint | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const priorityColors: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700'
}

const sentimentColors: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-700'
}

export function ComplaintDetailModal({ complaint, open, onOpenChange }: ComplaintDetailModalProps) {
  const [reply, setReply] = useState('')
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [isSending, setIsSending] = useState(false)

  if (!complaint) return null

  const handleUseAISuggestion = () => {
    if (complaint.suggestedResponse) {
      setReply(complaint.suggestedResponse)
      toast.success('AI suggestion applied')
    }
  }

  const handleRegenerate = async () => {
    setIsRegenerating(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    setIsRegenerating(false)
    toast.success('New response generated')
  }

  const handleSendReply = async () => {
    if (!reply.trim()) {
      toast.error('Please enter a reply')
      return
    }
    setIsSending(true)
    await new Promise(resolve => setTimeout(resolve, 1000))
    setIsSending(false)
    setReply('')
    toast.success('Reply sent successfully')
    onOpenChange(false)
  }

  const handleEscalate = () => {
    toast.success('Complaint escalated to manager')
    onOpenChange(false)
  }

  const handleMarkResolved = () => {
    toast.success('Complaint marked as resolved')
    onOpenChange(false)
  }

  const timeline = [
    { time: complaint.createdAt, action: 'Complaint received', icon: Mail },
    { time: complaint.createdAt, action: 'AI analysis completed', icon: Brain },
    { time: complaint.updatedAt, action: 'Status updated', icon: Clock }
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="font-mono text-sm text-muted-foreground">{complaint.id}</span>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-xl">{complaint.subject}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Customer Info */}
          <div className="flex flex-wrap gap-4 p-4 bg-muted/50 rounded-lg">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{complaint.customerName}</span>
            </div>
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{complaint.customerEmail}</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{complaint.customerPhone}</span>
            </div>
          </div>

          {/* Complaint Message */}
          <div>
            <h4 className="text-sm font-semibold mb-2">Complaint Details</h4>
            <p className="text-muted-foreground leading-relaxed p-4 bg-card border rounded-lg">
              {complaint.message}
            </p>
          </div>

          {/* AI Analysis */}
          <div className="p-4 bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg border border-blue-100">
            <div className="flex items-center gap-2 mb-4">
              <Brain className="h-5 w-5 text-primary" />
              <h4 className="font-semibold text-primary">AI Analysis</h4>
            </div>
            
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Category</p>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="capitalize">
                    {complaint.category}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {complaint.aiConfidence}% confidence
                  </span>
                </div>
                <Progress value={complaint.aiConfidence} className="h-1 mt-2" />
              </div>
              
              <div>
                <p className="text-xs text-muted-foreground mb-1">Priority</p>
                <div className="flex items-center gap-2">
                  <Badge className={cn("capitalize", priorityColors[complaint.priority])}>
                    {complaint.priority}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {complaint.aiConfidence - 3}% confidence
                  </span>
                </div>
                <Progress value={complaint.aiConfidence - 3} className="h-1 mt-2" />
              </div>
              
              <div>
                <p className="text-xs text-muted-foreground mb-1">Sentiment</p>
                <div className="flex items-center gap-2">
                  <Badge className={cn("capitalize", sentimentColors[complaint.sentiment])}>
                    {complaint.sentiment === 'positive' ? '😊' : complaint.sentiment === 'negative' ? '😠' : '😐'}{' '}
                    {complaint.sentiment}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {complaint.aiConfidence + 2}% confidence
                  </span>
                </div>
                <Progress value={Math.min(complaint.aiConfidence + 2, 100)} className="h-1 mt-2" />
              </div>
            </div>
          </div>

          {/* AI Suggested Response */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h4 className="text-sm font-semibold">AI Suggested Response</h4>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRegenerate}
                disabled={isRegenerating}
              >
                <RefreshCw className={cn("h-4 w-4 mr-1", isRegenerating && "animate-spin")} />
                Regenerate
              </Button>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg border text-sm whitespace-pre-line">
              {complaint.suggestedResponse}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={handleUseAISuggestion}
            >
              <Sparkles className="h-4 w-4 mr-1" />
              Use This Response
            </Button>
          </div>

          {/* Timeline */}
          <div>
            <h4 className="text-sm font-semibold mb-3">Timeline</h4>
            <div className="space-y-3">
              {timeline.map((item, index) => (
                <div key={index} className="flex items-start gap-3">
                  <div className="p-2 bg-muted rounded-full">
                    <item.icon className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{item.action}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(item.time).toLocaleString('en-IN', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reply Section */}
          <div>
            <h4 className="text-sm font-semibold mb-2">Send Reply</h4>
            <Textarea
              placeholder="Type your response..."
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              rows={4}
              className="resize-none"
            />
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-3 pt-2">
            <Button
              onClick={handleSendReply}
              disabled={isSending}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              <Send className="h-4 w-4 mr-2" />
              {isSending ? 'Sending...' : 'Send Reply'}
            </Button>
            <Button variant="outline" onClick={handleEscalate}>
              <AlertTriangle className="h-4 w-4 mr-2" />
              Escalate to Manager
            </Button>
            <Button variant="outline" onClick={handleMarkResolved} className="text-green-600 hover:text-green-700">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Mark as Resolved
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

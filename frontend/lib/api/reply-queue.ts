import api from '../api'

export interface ReplyQueueItem {
  id: string
  ticket_id: string
  ticket_number: string | null
  ticket_summary: string | null
  draft_id: string | null
  draft_subject: string | null
  draft_body: string | null
  draft_status: string | null
  customer_id: string | null
  generated_reply: string
  edited_reply: string | null
  confidence_score: number | null
  generation_strategy: string | null
  generation_metadata: Record<string, unknown>
  status: string
  reviewed_by: string | null
  reviewed_at: string | null
  rejection_reason: string | null
  hallucination_check_passed: boolean | null
  toxicity_score: number | null
  factual_consistency_score: number | null
  created_at: string | null
  expires_at: string | null
}

export const replyQueueAPI = {
  list: async (status = 'pending') => {
    const response = await api.get('/api/v1/reply-queue', { params: { status } })
    return response.data as { items: ReplyQueueItem[] }
  },

  approve: async (queueId: string, editedSubject?: string, editedReply?: string) => {
    const response = await api.post(`/api/v1/reply-queue/${queueId}/approve`, {
      edited_subject: editedSubject,
      edited_reply: editedReply,
    })
    return response.data as { success: boolean; item: ReplyQueueItem }
  },

  reject: async (queueId: string, reason: string) => {
    const response = await api.post(`/api/v1/reply-queue/${queueId}/reject`, { reason })
    return response.data as { success: boolean; item: ReplyQueueItem }
  },
}

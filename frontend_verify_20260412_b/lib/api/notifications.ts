import api from '../api'

export interface NotificationItem {
  id: string
  event_type: string
  title: string
  message: string
  severity: 'info' | 'medium' | 'high' | 'success'
  created_at: string | null
  ticket_id?: string | null
  complaint_id?: string | null
  href: string
}

export const notificationsAPI = {
  list: async (limit = 15): Promise<NotificationItem[]> => {
    const response = await api.get('/api/v1/notifications', {
      params: { limit },
    })
    return Array.isArray(response.data?.items) ? response.data.items : []
  },
}

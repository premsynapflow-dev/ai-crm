import api from '../api'

export interface QueueHealth {
  pending: number
  processing: number
  completed: number
  failed: number
  total?: number
}

export const queueHealthAPI = {
  get: async (): Promise<QueueHealth> => {
    const response = await api.get('/api/v1/queue/health')
    const d = response.data ?? {}
    return {
      pending: Number(d.pending ?? 0),
      processing: Number(d.processing ?? 0),
      completed: Number(d.completed ?? 0),
      failed: Number(d.failed ?? 0),
      total: Number(d.total ?? 0),
    }
  },
}

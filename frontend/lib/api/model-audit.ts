import api from '../api'

export interface ModelAuditEntry {
  id: string
  provider: string
  model: string
  taskType: string
  confidenceScore?: number | null
  latencyMs?: number | null
  status: 'succeeded' | 'failed' | string
  errorMessage?: string | null
  promptPreview?: string | null
  outputPreview?: string | null
  createdAt: string
}

interface ModelAuditApiRow {
  id: string
  provider?: string
  model?: string
  task_type?: string
  confidence_score?: number | null
  latency_ms?: number | null
  status?: string
  error_message?: string | null
  prompt_preview?: string | null
  output_preview?: string | null
  created_at?: string
}

function normalizeEntry(row: ModelAuditApiRow): ModelAuditEntry {
  return {
    id: row.id,
    provider: row.provider ?? 'gemini',
    model: row.model ?? 'unknown',
    taskType: row.task_type ?? 'unknown',
    confidenceScore: row.confidence_score ?? null,
    latencyMs: row.latency_ms ?? null,
    status: row.status ?? 'succeeded',
    errorMessage: row.error_message ?? null,
    promptPreview: row.prompt_preview ?? null,
    outputPreview: row.output_preview ?? null,
    createdAt: row.created_at ?? new Date().toISOString(),
  }
}

export interface ModelAuditStats {
  avgConfidence: number
  avgLatencyMs: number
  errorRate: number
  totalCount: number
}

export const modelAuditAPI = {
  list: async (limit = 50, taskType?: string): Promise<ModelAuditEntry[]> => {
    const params = new URLSearchParams()
    params.append('limit', String(limit))
    if (taskType && taskType !== 'all') params.append('task_type', taskType)
    const response = await api.get(`/api/v1/model-audit?${params.toString()}`)
    const rows: ModelAuditApiRow[] = Array.isArray(response.data) ? response.data : response.data.items ?? []
    return rows.map(normalizeEntry)
  },

  stats: async (): Promise<ModelAuditStats> => {
    const entries = await modelAuditAPI.list(200)
    if (!entries.length) return { avgConfidence: 0, avgLatencyMs: 0, errorRate: 0, totalCount: 0 }
    const failed = entries.filter(e => e.status === 'failed').length
    const withConf = entries.filter(e => e.confidenceScore != null)
    const withLat = entries.filter(e => e.latencyMs != null)
    return {
      avgConfidence: withConf.length
        ? Math.round((withConf.reduce((s, e) => s + (e.confidenceScore ?? 0), 0) / withConf.length) * 100)
        : 0,
      avgLatencyMs: withLat.length
        ? Math.round(withLat.reduce((s, e) => s + (e.latencyMs ?? 0), 0) / withLat.length)
        : 0,
      errorRate: Math.round((failed / entries.length) * 100),
      totalCount: entries.length,
    }
  },
}

import api from '../api'

export interface KnowledgeSnippet {
  id: string
  clientId: string
  title: string
  content: string
  category: string | null
  keywords: string[]
  sourceType: string
  status: 'active' | 'archived'
  createdBy: string | null
  createdAt: string
  updatedAt: string
}

export interface CreateSnippetPayload {
  title: string
  content: string
  category?: string
  keywords?: string[]
  created_by?: string
}

export interface UpdateSnippetPayload {
  title?: string
  content?: string
  category?: string
  keywords?: string[]
}

function normalizeSnippet(raw: Record<string, unknown>): KnowledgeSnippet {
  return {
    id: raw.id as string,
    clientId: (raw.client_id ?? '') as string,
    title: (raw.title ?? '') as string,
    content: (raw.content ?? '') as string,
    category: (raw.category ?? null) as string | null,
    keywords: (raw.keywords ?? []) as string[],
    sourceType: (raw.source_type ?? 'manual') as string,
    status: (raw.status ?? 'active') as 'active' | 'archived',
    createdBy: (raw.created_by ?? null) as string | null,
    createdAt: (raw.created_at ?? '') as string,
    updatedAt: (raw.updated_at ?? '') as string,
  }
}

export const knowledgeAPI = {
  list: async (): Promise<KnowledgeSnippet[]> => {
    const res = await api.get('/api/v1/knowledge')
    return (res.data?.items ?? []).map(normalizeSnippet)
  },

  search: async (q: string, limit = 10): Promise<KnowledgeSnippet[]> => {
    const res = await api.get('/api/v1/knowledge/search', { params: { q, limit } })
    return (res.data?.items ?? []).map(normalizeSnippet)
  },

  create: async (payload: CreateSnippetPayload): Promise<KnowledgeSnippet> => {
    const res = await api.post('/api/v1/knowledge', payload)
    return normalizeSnippet(res.data.item)
  },

  update: async (id: string, payload: UpdateSnippetPayload): Promise<KnowledgeSnippet> => {
    const res = await api.patch(`/api/v1/knowledge/${id}`, payload)
    return normalizeSnippet(res.data.item)
  },

  updateStatus: async (id: string, status: 'active' | 'archived'): Promise<KnowledgeSnippet> => {
    const res = await api.patch(`/api/v1/knowledge/${id}/status`, null, { params: { status } })
    return normalizeSnippet(res.data.item)
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/knowledge/${id}`)
  },
}

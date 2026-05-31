import api from '../api'

export interface ClientPromptConfig {
  custom_prompt_enabled: boolean
  tone: 'professional' | 'friendly' | 'empathetic' | 'formal'
  industry: 'ecommerce' | 'saas' | 'healthcare' | 'finance' | 'education' | 'general'
  focus_areas: string[]
  reply_guidelines: string
  updated_at?: string | null
}

export interface ClientPromptConfigUpdate {
  enabled: boolean
  tone: string
  industry: string
  focus_areas: string[]
  reply_guidelines: string
}

export const promptsAPI = {
  get: async (): Promise<ClientPromptConfig> => {
    const response = await api.get('/api/v1/settings/prompts')
    return response.data as ClientPromptConfig
  },

  update: async (payload: ClientPromptConfigUpdate): Promise<ClientPromptConfig & { status: string }> => {
    const response = await api.put('/api/v1/settings/prompts', payload)
    return response.data
  },
}

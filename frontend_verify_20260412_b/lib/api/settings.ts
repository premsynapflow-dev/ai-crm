import api from '../api'

export interface SettingsProfile {
  id: string
  email: string
  name: string
  company: string
  company_phone?: string | null
  business_sector?: string | null
  is_rbi_regulated?: boolean
  plan_id: string
  created_at?: string | null
}

export interface SettingsCompany {
  name: string
  plan_id: string
  monthly_ticket_limit: number
  contact_phone?: string | null
  business_sector?: string | null
  is_rbi_regulated?: boolean
  created_at?: string | null
}

export interface SettingsWebhook {
  id: string
  url: string
  events: string[]
  status: string
}

export interface SettingsTeamMember {
  id: string
  name: string
  email: string
  role: string
  status: string
  created_at?: string | null
}

export interface SettingsSummary {
  profile: SettingsProfile
  company: SettingsCompany
  api_key: string
  webhooks: SettingsWebhook[]
  team_members: SettingsTeamMember[]
}

export const settingsAPI = {
  getSummary: async (): Promise<SettingsSummary> => {
    const response = await api.get('/api/settings')
    return response.data
  },

  updateSlackWebhook: async (slackWebhookUrl: string) => {
    const response = await api.put('/api/settings/webhooks/slack', {
      slack_webhook_url: slackWebhookUrl,
    })
    return response.data as {
      success: boolean
      webhook: SettingsWebhook | null
    }
  },

  testSlackWebhook: async (slackWebhookUrl?: string) => {
    const response = await api.post('/api/settings/webhooks/slack/test', {
      slack_webhook_url: slackWebhookUrl,
    })
    return response.data as { success: boolean }
  },
}

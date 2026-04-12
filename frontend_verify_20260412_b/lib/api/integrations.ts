import api from '../api'

export interface IntegrationConnection {
  id: string
  channel: 'gmail' | 'email' | 'whatsapp' | string
  status: 'active' | 'expired' | 'error' | string
  account_identifier: string | null
  created_at: string | null
  metadata: Record<string, unknown>
}

export interface GmailConnectResponse {
  auth_url: string
}

export interface WhatsAppConnectPayload {
  phone_number_id: string
  business_account_id?: string
  access_token: string
}

export interface WhatsAppConnectResponse {
  status: string
  connection_id: string
  account_identifier: string
  phone_number_id: string
}

export const integrationsAPI = {
  list: async (): Promise<IntegrationConnection[]> => {
    const response = await api.get('/integrations/list')
    return response.data
  },

  connectGmail: async (): Promise<GmailConnectResponse> => {
    const response = await api.get('/integrations/gmail/connect')
    return response.data
  },

  connectWhatsApp: async (payload: WhatsAppConnectPayload): Promise<WhatsAppConnectResponse> => {
    const response = await api.post('/integrations/whatsapp/connect', payload)
    return response.data
  },
}

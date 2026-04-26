import api from '../api'

export interface InboxConnection {
  id: string
  email: string
  provider: 'gmail' | 'imap' | string
  status: 'active' | 'inactive' | string
  created_at: string | null
}

export interface GmailConnectUrlResponse {
  connect_url: string
}

export interface ConnectImapPayload {
  email: string
  imap_host: string
  imap_port: number
  username: string
  password: string
}

export const inboxesAPI = {
  list: async (): Promise<InboxConnection[]> => {
    const response = await api.get('/inboxes')
    return response.data
  },

  getGmailConnectUrl: async (): Promise<GmailConnectUrlResponse> => {
    const response = await api.get('/inboxes/gmail/connect-url')
    return response.data
  },

  connectImap: async (payload: ConnectImapPayload): Promise<InboxConnection> => {
    const response = await api.post('/inboxes/connect-imap', payload)
    return response.data
  },
}


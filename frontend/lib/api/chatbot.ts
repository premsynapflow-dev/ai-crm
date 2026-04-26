export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  reply: string
  escalate: boolean
  summary: string | null
  ticket_id: string
}

export const chatbotAPI = {
  sendMessage: async (
    apiKey: string,
    message: string,
    context: Record<string, any>,
    conversationHistory: ChatMessage[]
  ): Promise<ChatResponse> => {
    // For local dev preview we use relative path. In real embed, this would point to the absolute API URL.
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || ''
    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
      },
      body: JSON.stringify({
        message,
        context,
        conversation_history: conversationHistory,
      }),
    })

    if (!response.ok) {
      if (response.status === 401) {
         throw new Error('Invalid or missing API key')
      }
      if (response.status === 402) {
         throw new Error('Usage limit exceeded for this plan.')
      }
      throw new Error(`Failed to send message: ${response.statusText}`)
    }

    return response.json()
  },
}

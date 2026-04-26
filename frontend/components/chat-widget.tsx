"use client"

import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, User, Bot, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { chatbotAPI, type ChatMessage } from '@/lib/api/chatbot'

interface ChatWidgetProps {
  apiKey: string
  companyName: string
  initialMessage?: string
  isEmbed?: boolean
}

export function ChatWidget({ apiKey, companyName, initialMessage = "How can we help you today?", isEmbed = false }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: initialMessage }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [escalated, setEscalated] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isEmbed) {
      window.parent.postMessage({ type: 'SYNAPFLOW_WIDGET_RESIZE', isOpen }, '*')
    }
  }, [isOpen, isEmbed])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isLoading])

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading || escalated || !apiKey) return

    const userMsg = inputValue.trim()
    setInputValue('')
    
    const newMessages: ChatMessage[] = [...messages, { role: 'user', content: userMsg }]
    setMessages(newMessages)
    setIsLoading(true)

    try {
      // Exclude the very first greeting from history context if desired, or send all.
      // We will send all previous history.
      const historyToSend = messages.filter(m => m.content !== initialMessage)

      const response = await chatbotAPI.sendMessage(
        apiKey,
        userMsg,
        {
          source: 'widget',
        },
        historyToSend
      )

      if (response.escalate) {
        setEscalated(true)
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: response.reply || "I've passed this conversation on to our human team. Someone will be in touch with you shortly!" 
        }])
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: response.reply }])
      }
    } catch (error: any) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Error: ${error.message || 'Failed to connect.'}` 
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend()
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end">
      {isOpen && (
        <div className="mb-4 w-[350px] overflow-hidden rounded-2xl border border-border shadow-xl bg-background flex flex-col h-[500px] animate-in slide-in-from-bottom-4 fade-in duration-200">
          {/* Header */}
          <div className="bg-primary px-4 py-3 flex items-center justify-between text-primary-foreground">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              <div>
                <h3 className="font-semibold text-sm">{companyName} Support</h3>
                <p className="text-[10px] opacity-80">{escalated ? 'Human intervention required' : 'Powered by AI'}</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-primary/20 text-primary-foreground" onClick={() => setIsOpen(false)}>
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Messages */}
          <ScrollArea className="flex-1 p-4 bg-muted/10">
            <div className="space-y-4" ref={scrollRef}>
              {messages.map((msg, i) => (
                <div key={i} className={cn("flex gap-2", msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                  {msg.role === 'assistant' && (
                    <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="h-3.5 w-3.5 text-primary" />
                    </div>
                  )}
                  <div className={cn(
                    "px-3 py-2 rounded-2xl text-sm max-w-[80%]",
                    msg.role === 'user' 
                      ? 'bg-primary text-primary-foreground rounded-tr-sm' 
                      : 'bg-muted rounded-tl-sm'
                  )}>
                    {msg.content}
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="flex gap-2 justify-start">
                  <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <div className="px-3 py-2 rounded-2xl bg-muted rounded-tl-sm flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce" />
                    <span className="w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce delay-75" />
                    <span className="w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce delay-150" />
                  </div>
                </div>
              )}

              {escalated && (
                <div className="flex items-center gap-2 justify-center py-2 text-xs text-amber-600 bg-amber-50 rounded-lg border border-amber-100">
                  <AlertCircle className="w-4 h-4" />
                  Agent handoff triggered
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="p-3 border-t bg-background">
            <div className="flex gap-2">
              <Input 
                placeholder={escalated ? "Chat paused..." : "Type your message..."}
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading || escalated || !apiKey}
                className="rounded-full focus-visible:ring-1"
              />
              <Button 
                size="icon" 
                className="shrink-0 rounded-full h-10 w-10" 
                disabled={!inputValue.trim() || isLoading || escalated || !apiKey}
                onClick={handleSend}
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4 ml-0.5" />}
              </Button>
            </div>
            {!apiKey && (
              <p className="text-[10px] text-destructive text-center mt-2">API Key missing. Cannot send messages.</p>
            )}
          </div>
        </div>
      )}

      {/* Toggle Button */}
      <Button
        size="icon"
        className={cn("h-14 w-14 rounded-full shadow-2xl transition-transform hover:scale-105", isOpen ? "bg-muted hover:bg-muted text-foreground" : "bg-primary")}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageSquare className="h-6 w-6" />}
      </Button>
    </div>
  )
}

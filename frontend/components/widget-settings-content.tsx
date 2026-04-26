"use client"

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronLeft, Code, Copy, Info } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { settingsAPI, type SettingsSummary } from '@/lib/api/settings'
import { ChatWidget } from '@/components/chat-widget'

export function WidgetSettingsContent() {
  const [settings, setSettings] = useState<SettingsSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    settingsAPI.getSummary()
      .then(setSettings)
      .catch(() => toast.error('Failed to load settings'))
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) {
    return <div className="flex h-96 items-center justify-center text-sm text-muted-foreground">Loading widget settings...</div>
  }

  const apiKey = settings?.api_key || ''
  const companyName = settings?.company.name || 'Your Company'

  const embedCode = `
<script src="https://synapflow.up.railway.app/widget.js" defer></script>
<script>
  window.synapflowWidget = {
    apiKey: "${apiKey}",
    companyName: "${companyName}",
    theme: "light"
  };
</script>`.trim()

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(embedCode)
      toast.success('Embed code copied to clipboard')
    } catch {
      toast.error('Failed to copy code')
    }
  }

  return (
    <div className="space-y-6 relative pb-24"> {/* padding bottom so widget doesn't block content */}
      <div className="space-y-2">
        <Link
          href="/settings"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to settings
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Live Chat Widget</h1>
          <p className="mt-1 text-muted-foreground">
            Embed an AI-powered live chat widget directly onto your website to intercept and resolve support queries.
          </p>
        </div>
      </div>

      <Alert className="bg-primary/5 border-primary/20 text-primary">
        <Info className="h-4 w-4 text-primary" />
        <AlertTitle>Try it out!</AlertTitle>
        <AlertDescription>
          The widget preview is active in the bottom right corner of this page. You can interact with it using your real production AI Agent settings.
        </AlertDescription>
      </Alert>

      <Card className="border-border/70 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5 text-muted-foreground" />
            Embed Code
          </CardTitle>
          <CardDescription>
            Copy and paste this code snippet right before the closing <code>&lt;/body&gt;</code> tag of your website.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative rounded-lg bg-slate-950 p-4 border border-border overflow-x-auto text-slate-50">
            <pre className="text-sm font-mono whitespace-pre-wrap">{embedCode}</pre>
            <Button
              size="sm"
              variant="secondary"
              className="absolute top-4 right-4 gap-2"
              onClick={handleCopy}
            >
              <Copy className="h-4 w-4" />
              Copy
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Your widget is securely tied to your workspace using your API key. Make sure to only embed this script on authorized domains.
          </p>
        </CardContent>
      </Card>

      {/* Render the actual widget bound to this account */}
      {settings && <ChatWidget apiKey={apiKey} companyName={companyName} />}
    </div>
  )
}

"use client"

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { ChatWidget } from '@/components/chat-widget'

function EmbedContent() {
  const searchParams = useSearchParams()
  const apiKey = searchParams.get('apiKey') || ''
  const companyName = searchParams.get('companyName') || 'Support'

  return <ChatWidget apiKey={apiKey} companyName={companyName} isEmbed={true} />
}

export default function EmbedPage() {
  return (
    <Suspense fallback={null}>
      <EmbedContent />
    </Suspense>
  )
}

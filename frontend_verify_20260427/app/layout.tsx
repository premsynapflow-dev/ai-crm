import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { Toaster } from '@/components/ui/sonner'

import { AuthProvider } from '@/lib/auth-context'
import './globals.css'

const enableVercelAnalytics = process.env.VERCEL === '1' || Boolean(process.env.VERCEL_ENV)

export const metadata: Metadata = {
  title: 'SynapFlow - AI-Powered Complaint Intelligence',
  description: 'Transform your customer complaints into actionable insights with SynapFlow by SynapTec Pvt. Ltd.',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  themeColor: '#3B82F6',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <AuthProvider>
          {children}
        </AuthProvider>
        <Toaster position="top-right" richColors />
        {enableVercelAnalytics ? <Analytics /> : null}
      </body>
    </html>
  )
}

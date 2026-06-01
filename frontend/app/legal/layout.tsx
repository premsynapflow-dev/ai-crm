import Link from 'next/link'
import { Logo } from '@/components/logo'

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b border-slate-200 px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <Link href="/"><Logo /></Link>
          <nav className="flex gap-6 text-sm text-slate-600">
            <Link href="/legal/privacy-policy" className="hover:text-slate-900">Privacy Policy</Link>
            <Link href="/legal/terms-of-service" className="hover:text-slate-900">Terms of Service</Link>
            <Link href="/legal/cookie-policy" className="hover:text-slate-900">Cookie Policy</Link>
            <Link href="/legal/dpa" className="hover:text-slate-900">DPA</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-12">
        {children}
      </main>
      <footer className="border-t border-slate-200 px-6 py-6 text-center text-sm text-slate-500">
        © 2026 SynapTec Pvt. Ltd. · <Link href="/legal/privacy-policy" className="underline">Privacy</Link> · <Link href="/legal/terms-of-service" className="underline">Terms</Link>
      </footer>
    </div>
  )
}

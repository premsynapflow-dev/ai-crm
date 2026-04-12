import Link from 'next/link'

export function generateStaticParams() {
  return [{ id: 'legacy-customer-route' }]
}

export default async function LegacyCustomerPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-lg rounded-3xl border bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">Route updated</p>
        <h1 className="mt-3 text-3xl font-semibold text-slate-900">Customer 360 moved</h1>
        <p className="mt-3 text-sm text-slate-600">
          Open the customer profile from the new static route that works with the exported frontend build.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`/customer?id=${encodeURIComponent(id)}`}
            className="inline-flex items-center justify-center rounded-full bg-slate-900 px-5 py-2 text-sm font-medium text-white"
          >
            Open customer
          </Link>
          <Link
            href="/customers"
            className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-2 text-sm font-medium text-slate-700"
          >
            Back to directory
          </Link>
        </div>
      </div>
    </main>
  )
}

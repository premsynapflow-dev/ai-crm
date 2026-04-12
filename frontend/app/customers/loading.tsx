import { AuthProvider } from '@/lib/auth-context'
import { DashboardLayout } from '@/components/dashboard-layout'
import { CustomerListSkeleton } from '@/components/ui/skeletons'

export default function CustomersLoading() {
  return (
    <AuthProvider>
      <DashboardLayout>
        <div className="space-y-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between mb-8">
            <div className="w-full max-w-sm space-y-3">
               <div className="h-9 w-48 animate-pulse rounded-md bg-accent" />
               <div className="h-4 w-72 animate-pulse rounded-md bg-accent" />
            </div>
            <div className="h-10 w-full max-w-md animate-pulse rounded-md bg-accent" />
          </div>
          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.35fr]">
            <div className="rounded-xl border bg-card p-6 shadow-sm">
                <div className="space-y-3 mb-6">
                    <div className="h-6 w-32 animate-pulse bg-accent rounded-md" />
                    <div className="h-4 w-48 animate-pulse bg-accent rounded-md" />
                </div>
                <CustomerListSkeleton />
            </div>
            <div className="rounded-xl border bg-card/60 shadow-sm animate-pulse min-h-[70vh]" />
          </div>
        </div>
      </DashboardLayout>
    </AuthProvider>
  )
}

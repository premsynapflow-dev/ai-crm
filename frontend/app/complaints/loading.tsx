import { AuthProvider } from '@/lib/auth-context'
import { DashboardLayout } from '@/components/dashboard-layout'
import { TableSkeleton } from '@/components/ui/skeletons'

export default function ComplaintsLoading() {
  return (
    <AuthProvider>
      <DashboardLayout>
        <div className="space-y-6">
          <div className="h-32 w-full animate-pulse rounded-[28px] bg-accent" />
          <div className="h-20 w-full animate-pulse rounded-xl bg-accent mt-6" />
          <div className="mt-6 flex gap-4">
             {Array.from({ length: 3 }).map((_, i) => (
               <div key={i} className="h-9 w-32 animate-pulse rounded-md bg-accent" />
             ))}
          </div>
          <div className="h-[60vh] w-full mt-6 rounded-xl border bg-card p-4 shadow-sm">
             <div className="h-8 w-40 animate-pulse bg-accent rounded-md mb-6" />
             <TableSkeleton rows={10} />
          </div>
        </div>
      </DashboardLayout>
    </AuthProvider>
  )
}

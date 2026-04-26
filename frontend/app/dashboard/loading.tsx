import { AuthProvider } from '@/lib/auth-context'
import { DashboardLayout } from '@/components/dashboard-layout'
import { DashboardSkeleton } from '@/components/ui/skeletons'

export default function DashboardLoading() {
  return (
    <>
      <DashboardLayout>
        <DashboardSkeleton />
      </DashboardLayout>
    </>
  )
}

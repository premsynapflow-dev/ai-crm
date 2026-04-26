import { DashboardLayout } from '@/components/dashboard-layout'
import { DashboardSkeleton } from '@/components/ui/skeletons'

export default function UsageLoading() {
  return (
    <DashboardLayout>
      <DashboardSkeleton />
    </DashboardLayout>
  )
}

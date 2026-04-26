import { DashboardLayout } from '@/components/dashboard-layout'
import { Customer360Skeleton } from '@/components/ui/skeletons'

export default function CustomerLoading() {
  return (
    <DashboardLayout>
      <Customer360Skeleton />
    </DashboardLayout>
  )
}

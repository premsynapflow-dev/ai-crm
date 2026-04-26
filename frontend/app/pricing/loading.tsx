import { DashboardLayout } from '@/components/dashboard-layout'
import { DashboardSkeleton } from '@/components/ui/skeletons'

export default function PricingLoading() {
  return (
    <DashboardLayout>
      <DashboardSkeleton />
    </DashboardLayout>
  )
}

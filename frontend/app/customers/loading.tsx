import { DashboardLayout } from '@/components/dashboard-layout'
import { CustomerListSkeleton } from '@/components/ui/skeletons'

export default function CustomersLoading() {
  return (
    <DashboardLayout>
      <CustomerListSkeleton />
    </DashboardLayout>
  )
}

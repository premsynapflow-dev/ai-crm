import { DashboardLayout } from '@/components/dashboard-layout'
import { TableSkeleton } from '@/components/ui/skeletons'

export default function AssignmentsLoading() {
  return (
    <DashboardLayout>
      <TableSkeleton rows={10} />
    </DashboardLayout>
  )
}

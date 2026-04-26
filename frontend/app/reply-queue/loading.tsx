import { DashboardLayout } from '@/components/dashboard-layout'
import { TableSkeleton } from '@/components/ui/skeletons'

export default function ReplyqueueLoading() {
  return (
    <DashboardLayout>
      <TableSkeleton rows={10} />
    </DashboardLayout>
  )
}

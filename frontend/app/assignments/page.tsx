"use client"

import { DashboardLayout } from '@/components/dashboard-layout'
import { AssignmentDashboard } from '@/components/assignment-dashboard'

export default function AssignmentsPage() {
  return (
    <DashboardLayout>
      <AssignmentDashboard />
    </DashboardLayout>
  )
}

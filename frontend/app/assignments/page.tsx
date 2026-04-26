"use client"


import { DashboardLayout } from '@/components/dashboard-layout'
import { AssignmentDashboard } from '@/components/assignment-dashboard'
import { AuthProvider } from '@/lib/auth-context'

export default function AssignmentsPage() {
  return (
    <>
      <DashboardLayout>
        <AssignmentDashboard />
      </DashboardLayout>
    </>
  )
}

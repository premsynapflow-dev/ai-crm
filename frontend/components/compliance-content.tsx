"use client"

import { useEffect, useState } from 'react'
import { AlertTriangle, Building2, Loader2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

import { UpgradePrompt } from '@/components/upgrade-prompt'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { getFeatureGateDetail } from '@/lib/api-error'
import { complaintsAPI, type Complaint } from '@/lib/api/complaints'
import { complianceAPI, type RBIComplaintCategory, type RBIComplaintDetail, type RBIMisReport } from '@/lib/api/compliance'
import { useAuth } from '@/lib/auth-context'
import { planIncludesFeature } from '@/lib/plan-features'

function formatDate(value?: string | null) {
  if (!value) {
    return 'Not available'
  }

  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function tatTone(status: string) {
  if (status === 'breached') {
    return 'bg-rose-100 text-rose-700'
  }
  if (status === 'approaching_breach') {
    return 'bg-amber-100 text-amber-700'
  }
  if (status === 'within_tat' || status === 'resolved') {
    return 'bg-emerald-100 text-emerald-700'
  }
  return 'bg-slate-100 text-slate-700'
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function ComplianceContent() {
  const { user } = useAuth()
  const [categories, setCategories] = useState<RBIComplaintCategory[]>([])
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [selectedComplaintId, setSelectedComplaintId] = useState<string | null>(null)
  const [selectedComplaint, setSelectedComplaint] = useState<RBIComplaintDetail | null>(null)
  const [report, setReport] = useState<RBIMisReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [featureLocked, setFeatureLocked] = useState(false)
  const [isEscalating, setIsEscalating] = useState(false)

  useEffect(() => {
    let active = true

    async function loadCompliance() {
      setLoading(true)
      try {
        const now = new Date()
        const [categoriesResponse, reportResponse, complaintsResponse] = await Promise.all([
          complianceAPI.getCategories(),
          complianceAPI.getMisReport(now.getFullYear(), now.getMonth() + 1),
          complaintsAPI.list({ page: 1, pageSize: 20 }),
        ])

        if (!active) {
          return
        }

        setCategories(categoriesResponse.items)
        setReport(reportResponse)
        setComplaints(complaintsResponse.items)
        setSelectedComplaintId((current) => current ?? complaintsResponse.items[0]?.id ?? null)
        setFeatureLocked(false)
      } catch (error) {
        if (!active) {
          return
        }
        setCategories([])
        setReport(null)
        setComplaints([])
        setSelectedComplaintId(null)
        setFeatureLocked(Boolean(getFeatureGateDetail(error)))
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadCompliance()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true

    async function loadComplaintDetail() {
      if (!selectedComplaintId) {
        setSelectedComplaint(null)
        return
      }
      setDetailLoading(true)
      try {
        const response = await complianceAPI.getComplaint(selectedComplaintId)
        if (active) {
          setSelectedComplaint(response)
        }
      } catch {
        if (active) {
          setSelectedComplaint(null)
        }
      } finally {
        if (active) {
          setDetailLoading(false)
        }
      }
    }

    void loadComplaintDetail()

    return () => {
      active = false
    }
  }, [selectedComplaintId])

  const handleEscalate = async () => {
    if (!selectedComplaintId) {
      return
    }
    setIsEscalating(true)
    try {
      await complianceAPI.escalateInternally(selectedComplaintId)
      const refreshed = await complianceAPI.getComplaint(selectedComplaintId)
      setSelectedComplaint(refreshed)
      toast.success('Complaint escalated to Internal Ombudsman')
    } catch {
      toast.error('Failed to escalate complaint internally')
    } finally {
      setIsEscalating(false)
    }
  }

  const planLocked = !planIncludesFeature(user?.plan_id, 'rbi_compliance')
  const showUpgradePrompt = featureLocked || planLocked

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">RBI Compliance</h1>
        <p className="mt-1 text-muted-foreground">Track complaint taxonomy, TAT status, MIS totals, and escalation readiness.</p>
      </div>

      {showUpgradePrompt ? (
        <UpgradePrompt
          title="Unlock RBI compliance"
          description="Classify complaints against RBI taxonomy, monitor TAT status, and generate MIS reporting."
          requiredPlan="Scale"
        />
      ) : loading ? (
        <div className="flex h-64 items-center justify-center gap-3 rounded-2xl border bg-card">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm text-muted-foreground">Loading compliance workspace...</span>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-5">
            <Card>
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">MIS month</p>
                <p className="mt-2 text-2xl font-semibold">
                  {new Date().toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">Total complaints</p>
                <p className="mt-2 text-2xl font-semibold">{report?.total_complaints ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">Resolved within TAT</p>
                <p className="mt-2 text-2xl font-semibold">{report?.resolved_within_tat ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">Breached complaints</p>
                <p className="mt-2 text-2xl font-semibold">{report?.breached_complaints ?? report?.tat_breach_count ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">Internal escalations</p>
                <p className="mt-2 text-2xl font-semibold">{report?.escalations_count ?? report?.escalated_to_ombudsman ?? 0}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_1.15fr]">
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Recent Complaint Mapping</CardTitle>
                  <CardDescription>Select a complaint to inspect its RBI status and escalation path.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {complaints.map((complaint) => (
                    <button
                      key={complaint.id}
                      type="button"
                      onClick={() => setSelectedComplaintId(complaint.id)}
                      className={`w-full rounded-2xl border p-4 text-left transition ${
                        selectedComplaintId === complaint.id ? 'border-slate-900 bg-slate-50' : 'hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-900">{complaint.ticketId || complaint.id}</p>
                          <p className="text-sm text-muted-foreground">{complaint.subject}</p>
                        </div>
                        <Badge variant="outline">{complaint.category}</Badge>
                      </div>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>RBI Taxonomy Snapshot</CardTitle>
                  <CardDescription>Active category and subcategory mappings available to the classifier.</CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Category</TableHead>
                        <TableHead>Subcategory</TableHead>
                        <TableHead>TAT days</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {categories.slice(0, 10).map((category) => (
                        <TableRow key={category.id}>
                          <TableCell>{category.category_code}</TableCell>
                          <TableCell>{category.subcategory_name}</TableCell>
                          <TableCell>{category.tat_days}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Complaint Compliance Detail</CardTitle>
                <CardDescription>Live RBI record and escalation state for the selected complaint.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {detailLoading ? (
                  <div className="flex h-48 items-center justify-center gap-3">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Loading complaint compliance data...</span>
                  </div>
                ) : !selectedComplaint ? (
                  <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed text-sm text-muted-foreground">
                    Select a complaint to view RBI compliance details.
                  </div>
                ) : (
                  <>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-sm text-muted-foreground">RBI reference</p>
                        <p className="mt-2 font-semibold">{selectedComplaint.rbi_reference_number}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-sm text-muted-foreground">TAT status</p>
                        <div className="mt-2">
                          <Badge className={tatTone(selectedComplaint.tat_status)}>{selectedComplaint.tat_status}</Badge>
                        </div>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-sm text-muted-foreground">Category</p>
                        <p className="mt-2 font-semibold">
                          {selectedComplaint.category_name || selectedComplaint.category_code}
                          {' / '}
                          {selectedComplaint.subcategory_name || selectedComplaint.subcategory_code}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-sm text-muted-foreground">TAT due</p>
                        <p className="mt-2 font-semibold">{formatDate(selectedComplaint.tat_due_at ?? selectedComplaint.tat_due_date)}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-sm text-muted-foreground">Breach state</p>
                        <p className="mt-2 font-semibold">{selectedComplaint.breached ? 'Breached' : 'Within TAT'}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-sm text-muted-foreground">Breached at</p>
                        <p className="mt-2 font-semibold">{formatDate(selectedComplaint.tat_breached_at)}</p>
                      </div>
                    </div>

                    <div className="rounded-2xl border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-slate-900">Escalation state</p>
                          <p className="text-sm text-muted-foreground">
                            Level {selectedComplaint.escalation_level ?? 0} · {selectedComplaint.escalation_status ?? 'Not escalated'}
                          </p>
                        </div>
                        <Button onClick={() => void handleEscalate()} disabled={isEscalating || selectedComplaint.escalation_history.length > 0}>
                          {selectedComplaint.escalation_history.length > 0 ? (
                            <>
                              <ShieldCheck className="mr-2 h-4 w-4" />
                              Escalated
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="mr-2 h-4 w-4" />
                              {isEscalating ? 'Escalating...' : 'Escalate internally'}
                            </>
                          )}
                        </Button>
                      </div>
                      <div className="mt-4 space-y-3">
                        {selectedComplaint.escalation_history.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No internal escalation has been triggered yet.</p>
                        ) : (
                          selectedComplaint.escalation_history.map((entry) => (
                            <div key={entry.id} className="rounded-xl bg-slate-50 p-3 text-sm">
                              <p className="font-medium text-slate-900">Level {entry.level} → {entry.escalated_to}</p>
                              <p className="mt-1 text-muted-foreground">{entry.reason || 'No reason recorded'}</p>
                              <p className="mt-1 text-xs text-slate-500">{formatDate(entry.created_at)}</p>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    <div className="rounded-2xl border p-4">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-slate-500" />
                        <p className="font-medium text-slate-900">Audit trail</p>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-3">
                        <Button variant="outline" size="sm" onClick={() => downloadJson(`mis-report-${new Date().toISOString().slice(0, 10)}.json`, report)}>
                          Export MIS JSON
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => downloadJson(`rbi-audit-${selectedComplaint.complaint_id}.json`, selectedComplaint.audit_log)}>
                          Export audit log
                        </Button>
                      </div>
                      <div className="mt-3 space-y-3">
                        {selectedComplaint.audit_log.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No audit entries recorded yet.</p>
                        ) : (
                          selectedComplaint.audit_log.map((entry, index) => (
                            <pre key={index} className="overflow-auto rounded-xl bg-slate-50 p-3 text-xs text-slate-700">
                              {JSON.stringify(entry, null, 2)}
                            </pre>
                          ))
                        )}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

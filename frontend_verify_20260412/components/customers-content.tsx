"use client"

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowRight, Loader2, Mail, Phone, Search, StickyNote } from 'lucide-react'
import { toast } from 'sonner'

import { UpgradePrompt } from '@/components/upgrade-prompt'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { getFeatureGateDetail } from '@/lib/api-error'
import { customersAPI, type CustomerDetailResponse, type CustomerDuplicateCandidate, type CustomerSummary } from '@/lib/api/customers'

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

function riskTone(score: number) {
  if (score >= 75) {
    return 'bg-rose-100 text-rose-700'
  }
  if (score >= 45) {
    return 'bg-amber-100 text-amber-700'
  }
  return 'bg-emerald-100 text-emerald-700'
}

export function CustomersContent() {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [customers, setCustomers] = useState<CustomerSummary[]>([])
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)
  const [detail, setDetail] = useState<CustomerDetailResponse | null>(null)
  const [duplicates, setDuplicates] = useState<CustomerDuplicateCandidate[]>([])
  const [noteContent, setNoteContent] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [isSavingNote, setIsSavingNote] = useState(false)
  const [featureLocked, setFeatureLocked] = useState(false)

  useEffect(() => {
    let active = true

    async function loadCustomers() {
      setIsLoading(true)
      try {
        const response = await customersAPI.list({ search: query, limit: 50 })
        if (!active) {
          return
        }
        setCustomers(response.items)
        setFeatureLocked(false)
        setSelectedCustomerId((current) => current ?? response.items[0]?.id ?? null)
      } catch (error) {
        if (!active) {
          return
        }
        setCustomers([])
        setSelectedCustomerId(null)
        setFeatureLocked(Boolean(getFeatureGateDetail(error)))
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadCustomers()

    return () => {
      active = false
    }
  }, [query])

  useEffect(() => {
    let active = true

    async function loadCustomerDetail() {
      if (!selectedCustomerId) {
        setDetail(null)
        setDuplicates([])
        return
      }

      setIsDetailLoading(true)
      try {
        const [detailResponse, duplicateResponse] = await Promise.all([
          customersAPI.getById(selectedCustomerId),
          customersAPI.getDuplicates(selectedCustomerId),
        ])

        if (!active) {
          return
        }

        setDetail(detailResponse)
        setDuplicates(duplicateResponse.potential_duplicates)
      } catch {
        if (active) {
          setDetail(null)
          setDuplicates([])
        }
      } finally {
        if (active) {
          setIsDetailLoading(false)
        }
      }
    }

    void loadCustomerDetail()

    return () => {
      active = false
    }
  }, [selectedCustomerId])

  const handleSaveNote = async () => {
    if (!selectedCustomerId || !noteContent.trim()) {
      return
    }

    setIsSavingNote(true)
    try {
      await customersAPI.addNote(selectedCustomerId, {
        content: noteContent.trim(),
        note_type: 'general',
        pinned: false,
      })
      const refreshed = await customersAPI.getById(selectedCustomerId)
      setDetail(refreshed)
      setNoteContent('')
      toast.success('Customer note added')
    } catch {
      toast.error('Failed to save customer note')
    } finally {
      setIsSavingNote(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Customer 360</h1>
          <p className="mt-1 text-muted-foreground">Search customer history, relationships, notes, and churn signals.</p>
        </div>
        <div className="flex w-full max-w-md gap-2">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, email, company, phone"
          />
          <Button onClick={() => setQuery(search)}>
            <Search className="mr-2 h-4 w-4" />
            Search
          </Button>
        </div>
      </div>

      {featureLocked ? (
        <UpgradePrompt
          title="Unlock Customer 360"
          description="View full customer history, notes, duplicates, and relationships from one workspace."
          requiredPlan="Pro"
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.35fr]">
          <Card>
            <CardHeader>
              <CardTitle>Customer Directory</CardTitle>
              <CardDescription>Live customer profiles synced from complaint activity.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {isLoading ? (
                <div className="flex h-48 items-center justify-center gap-3 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading customers...
                </div>
              ) : customers.length === 0 ? (
                <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No customer profiles matched this search yet.
                </div>
              ) : (
                customers.map((customer) => (
                  <button
                    key={customer.id}
                    type="button"
                    onClick={() => setSelectedCustomerId(customer.id)}
                    className={`w-full rounded-2xl border p-4 text-left transition ${
                      selectedCustomerId === customer.id ? 'border-slate-900 bg-slate-50' : 'hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{customer.name || customer.full_name || customer.primary_email || 'Customer'}</p>
                        <p className="text-sm text-muted-foreground">{customer.company_name || 'Individual profile'}</p>
                      </div>
                      <Badge className={riskTone(customer.churn_risk_score)}>
                        Risk {customer.churn_risk_score.toFixed(0)}
                      </Badge>
                    </div>
                    <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
                      <span className="flex items-center gap-2">
                        <Mail className="h-4 w-4" />
                        {customer.primary_email || 'No email'}
                      </span>
                      <span className="flex items-center gap-2">
                        <Phone className="h-4 w-4" />
                        {customer.primary_phone || 'No phone'}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            {isDetailLoading ? (
              <div className="flex h-64 items-center justify-center gap-3 rounded-2xl border bg-card">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-muted-foreground">Loading customer profile...</span>
              </div>
            ) : !detail ? (
              <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed bg-card text-sm text-muted-foreground">
                Select a customer to inspect their full history.
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-4">
                  <Card>
                    <CardContent className="p-4">
                      <p className="text-sm text-muted-foreground">Tickets</p>
                      <p className="mt-2 text-2xl font-semibold">{detail.stats.total_tickets}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <p className="text-sm text-muted-foreground">Interactions</p>
                      <p className="mt-2 text-2xl font-semibold">{detail.stats.total_interactions}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <p className="text-sm text-muted-foreground">Avg satisfaction</p>
                      <p className="mt-2 text-2xl font-semibold">{detail.stats.avg_satisfaction ?? '-'}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <p className="text-sm text-muted-foreground">Churn risk</p>
                      <p className="mt-2 text-2xl font-semibold">{detail.stats.churn_risk.toFixed(0)}</p>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                    <CardHeader className="flex flex-row items-start justify-between gap-4">
                      <div>
                        <CardTitle>{detail.profile.name || detail.profile.full_name || detail.profile.primary_email || 'Customer profile'}</CardTitle>
                        <CardDescription>
                          Last activity {formatDate(detail.profile.last_contacted_at || detail.profile.last_interaction_at)}
                        </CardDescription>
                      </div>
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/customer?id=${encodeURIComponent(detail.profile.id)}`}>
                          Open 360
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Link>
                      </Button>
                    </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-2">
                    <div>
                      <p className="text-sm text-muted-foreground">Primary email</p>
                      <p className="mt-1 font-medium">{detail.profile.primary_email || 'Not available'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Primary phone</p>
                      <p className="mt-1 font-medium">{detail.profile.primary_phone || 'Not available'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Company</p>
                      <p className="mt-1 font-medium">{detail.profile.company_name || 'Not available'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Created</p>
                      <p className="mt-1 font-medium">{formatDate(detail.profile.created_at)}</p>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Recent Tickets</CardTitle>
                      <CardDescription>Complaint history linked to this customer.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Ticket</TableHead>
                            <TableHead>Category</TableHead>
                            <TableHead>Status</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {detail.recent_tickets.slice(0, 8).map((ticket) => (
                            <TableRow key={ticket.id}>
                              <TableCell>
                                <div>
                                  <p className="font-medium">{ticket.ticket_number}</p>
                                  <p className="text-xs text-muted-foreground">{ticket.summary}</p>
                                </div>
                              </TableCell>
                              <TableCell>{ticket.category}</TableCell>
                              <TableCell>
                                <Badge variant="outline">{ticket.resolution_status}</Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Interaction Timeline</CardTitle>
                      <CardDescription>Recent touchpoints across channels.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {detail.interaction_timeline.slice(0, 8).map((interaction) => (
                        <div key={interaction.id} className="rounded-xl border p-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium capitalize">{interaction.interaction_type}</p>
                            <Badge variant="outline">{interaction.interaction_channel || 'unknown'}</Badge>
                          </div>
                          <p className="mt-2 text-sm text-muted-foreground">{interaction.summary || 'No summary available'}</p>
                          <p className="mt-2 text-xs text-muted-foreground">{formatDate(interaction.created_at)}</p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>

                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Notes</CardTitle>
                      <CardDescription>Save context for the next support conversation.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="space-y-3">
                        <Textarea
                          placeholder="Add an internal customer note"
                          value={noteContent}
                          onChange={(event) => setNoteContent(event.target.value)}
                        />
                        <Button onClick={() => void handleSaveNote()} disabled={isSavingNote || !noteContent.trim()}>
                          <StickyNote className="mr-2 h-4 w-4" />
                          {isSavingNote ? 'Saving...' : 'Add note'}
                        </Button>
                      </div>
                      <div className="space-y-3">
                        {detail.notes.length === 0 ? (
                          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                            No internal notes yet.
                          </div>
                        ) : (
                          detail.notes.map((note) => (
                            <div key={note.id} className="rounded-xl border p-3">
                              <div className="flex items-center justify-between gap-3">
                                <Badge variant="outline">{note.note_type}</Badge>
                                <span className="text-xs text-muted-foreground">{formatDate(note.created_at)}</span>
                              </div>
                              <p className="mt-2 text-sm text-slate-700">{note.content}</p>
                              <p className="mt-2 text-xs text-muted-foreground">{note.author_email}</p>
                            </div>
                          ))
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  <div className="space-y-6">
                    <Card>
                      <CardHeader>
                        <CardTitle>Possible Duplicates</CardTitle>
                        <CardDescription>Matches suggested by customer deduplication.</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {duplicates.length === 0 ? (
                          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                            No strong duplicates detected.
                          </div>
                        ) : (
                          duplicates.map((candidate) => (
                            <div key={candidate.customer.id} className="rounded-xl border p-3">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium">{candidate.customer.full_name || candidate.customer.primary_email || 'Customer'}</p>
                                <Badge className="bg-blue-100 text-blue-700">
                                  Match {(candidate.confidence_score * 100).toFixed(0)}%
                                </Badge>
                              </div>
                              <p className="mt-2 text-sm text-muted-foreground">
                                {candidate.customer.primary_email || candidate.customer.primary_phone || 'No identity data'}
                              </p>
                            </div>
                          ))
                        )}
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle>Relationships & Churn Signals</CardTitle>
                        <CardDescription>Context that helps teams prioritize outreach.</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {detail.relationships.length === 0 ? (
                          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                            No relationships recorded yet.
                          </div>
                        ) : (
                          detail.relationships.map((relationship) => (
                            <div key={relationship.id} className="rounded-xl border p-3 text-sm">
                              <p className="font-medium capitalize">{relationship.relationship_type}</p>
                              <p className="mt-1 text-muted-foreground">{relationship.role_title || 'Role not specified'}</p>
                            </div>
                          ))
                        )}
                        <div className="rounded-xl bg-slate-50 p-4 text-sm text-muted-foreground">
                          <p className="font-medium text-slate-900">Recent signal summary</p>
                          <pre className="mt-2 overflow-auto whitespace-pre-wrap font-sans">
                            {JSON.stringify(detail.churn_indicators, null, 2)}
                          </pre>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

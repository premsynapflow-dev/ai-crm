"use client"

import { useDeferredValue, useEffect, useState } from 'react'
import type { CheckedState } from '@radix-ui/react-checkbox'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import {
  Search,
  Eye,
  MessageSquare,
  AlertTriangle,
  Trash2,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import { analyticsAPI } from '@/lib/api/analytics'
import { complaintsAPI, type Complaint } from '@/lib/api/complaints'
import { cn } from '@/lib/utils'
import { ComplaintDetailModal } from '@/components/complaint-detail-modal'
import { toast } from 'sonner'

const priorityColors: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

const sentimentColors: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-700',
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-purple-100 text-purple-700',
  resolved: 'bg-green-100 text-green-700',
  escalated: 'bg-red-100 text-red-700',
}

const ITEMS_PER_PAGE = 20

export function ComplaintsInbox() {
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [totalComplaints, setTotalComplaints] = useState(0)
  const [categories, setCategories] = useState<string[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set<string>())
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isMutating, setIsMutating] = useState(false)
  const deferredSearch = useDeferredValue(searchQuery)

  const loadComplaints = async (page: number = currentPage): Promise<void> => {
    setIsLoading(true)
    try {
      const response = await complaintsAPI.list({
        page,
        pageSize: ITEMS_PER_PAGE,
        category: categoryFilter === 'all' ? undefined : categoryFilter,
        priority: priorityFilter === 'all' ? undefined : priorityFilter,
        status: statusFilter === 'all' ? undefined : statusFilter,
        search: deferredSearch.trim() || undefined,
      })
      setComplaints(response.items)
      setTotalComplaints(response.total)
      setSelectedIds(new Set<string>())

      if (response.items.length === 0 && page > 1 && response.total > 0) {
        setCurrentPage(page - 1)
      }
    } catch {
      setComplaints([])
      setTotalComplaints(0)
      toast.error('Failed to load complaints')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadComplaints(currentPage)
  }, [currentPage, categoryFilter, priorityFilter, statusFilter, deferredSearch])

  useEffect(() => {
    let active = true

    analyticsAPI.getCategoryBreakdown()
      .then((items) => {
        if (!active) {
          return
        }
        const nextCategories: string[] = Array.from(
          new Set(
            (items ?? [])
              .map((item) => item.category)
              .filter((category): category is string => Boolean(category)),
          ),
        )
        setCategories(nextCategories)
      })
      .catch(() => {
        if (active) {
          setCategories([])
        }
      })

    return () => {
      active = false
    }
  }, [])

  const totalPages = Math.max(Math.ceil(totalComplaints / ITEMS_PER_PAGE), 1)

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(complaints.map((complaint) => complaint.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const handleSelectOne = (id: string, checked: boolean) => {
    const nextSelection = new Set(selectedIds)
    if (checked) {
      nextSelection.add(id)
    } else {
      nextSelection.delete(id)
    }
    setSelectedIds(nextSelection)
  }

  const handleBulkResolve = async () => {
    setIsMutating(true)
    try {
      await Promise.all(Array.from(selectedIds).map((id) => complaintsAPI.markResolved(id)))
      toast.success(`${selectedIds.size} complaints marked as resolved`)
      await loadComplaints(currentPage)
    } catch {
      toast.error('Failed to resolve selected complaints')
    } finally {
      setIsMutating(false)
    }
  }

  const handleBulkEscalate = async () => {
    setIsMutating(true)
    try {
      await Promise.all(Array.from(selectedIds).map((id) => complaintsAPI.escalate(id)))
      toast.success(`${selectedIds.size} complaints escalated`)
      await loadComplaints(currentPage)
    } catch {
      toast.error('Failed to escalate selected complaints')
    } finally {
      setIsMutating(false)
    }
  }

  const handleBulkDelete = async () => {
    setIsMutating(true)
    try {
      await Promise.all(Array.from(selectedIds).map((id) => complaintsAPI.delete(id)))
      toast.success(`${selectedIds.size} complaints deleted`)
      await loadComplaints(currentPage)
    } catch {
      toast.error('Failed to delete selected complaints')
    } finally {
      setIsMutating(false)
    }
  }

  const handleSingleEscalate = async (complaintId: string) => {
    setIsMutating(true)
    try {
      const updatedComplaint = await complaintsAPI.escalate(complaintId)
      setComplaints((current) => current.map((item) => (item.id === updatedComplaint.id ? updatedComplaint : item)))
      toast.success('Complaint escalated')
    } catch {
      toast.error('Failed to escalate complaint')
    } finally {
      setIsMutating(false)
    }
  }

  const handleViewDetails = (complaint: Complaint) => {
    setSelectedComplaint(complaint)
    setModalOpen(true)
  }

  const handleComplaintUpdated = (updatedComplaint: Complaint) => {
    setComplaints((current) => current.map((item) => (item.id === updatedComplaint.id ? updatedComplaint : item)))
    setSelectedComplaint(updatedComplaint)
  }

  const allSelected = complaints.length > 0 && complaints.every((complaint) => selectedIds.has(complaint.id))
  const showingFrom = totalComplaints === 0 ? 0 : (currentPage - 1) * ITEMS_PER_PAGE + 1
  const showingTo = Math.min(currentPage * ITEMS_PER_PAGE, totalComplaints)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Complaints Inbox</h1>
        <p className="mt-1 text-muted-foreground">Manage and respond to customer complaints</p>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4">
            <div className="min-w-[200px] flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by ID, customer, or subject..."
                  value={searchQuery}
                  onChange={(event) => {
                    setSearchQuery(event.target.value)
                    setCurrentPage(1)
                  }}
                  className="pl-10"
                />
              </div>
            </div>

            <Select value={categoryFilter} onValueChange={(value) => { setCategoryFilter(value); setCurrentPage(1) }}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map((category) => (
                  <SelectItem key={category} value={category}>
                    {category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={priorityFilter} onValueChange={(value) => { setPriorityFilter(value); setCurrentPage(1) }}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All Priorities" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value); setCurrentPage(1) }}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="in-progress">In Progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.size === 0 || isMutating}
          onClick={handleBulkResolve}
          className="gap-2"
        >
          <CheckCircle2 className="h-4 w-4" />
          Mark as Resolved
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.size === 0 || isMutating}
          onClick={handleBulkEscalate}
          className="gap-2"
        >
          <AlertTriangle className="h-4 w-4" />
          Escalate Selected
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.size === 0 || isMutating}
          onClick={handleBulkDelete}
          className="gap-2 text-red-600 hover:text-red-700"
        >
          <Trash2 className="h-4 w-4" />
          Delete
        </Button>
        {isMutating && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        {selectedIds.size > 0 && (
          <span className="text-sm text-muted-foreground">
            {selectedIds.size} selected
          </span>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Complaints</span>
            <span className="text-sm font-normal text-muted-foreground">
              Showing {showingFrom}-{showingTo} of {totalComplaints}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox
                      checked={allSelected}
                      onCheckedChange={handleSelectAll}
                    />
                  </TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Sentiment</TableHead>
                  <TableHead>AI Conf.</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={12} className="h-32 text-center text-muted-foreground">
                      <div className="inline-flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading complaints...
                      </div>
                    </TableCell>
                  </TableRow>
                ) : complaints.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={12} className="h-32 text-center text-muted-foreground">
                      No complaints found for the selected filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  complaints.map((complaint) => (
                    <TableRow key={complaint.id} className="hover:bg-muted/50">
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(complaint.id)}
                          onCheckedChange={(checked) => handleSelectOne(complaint.id, checked as boolean)}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-sm">{complaint.id}</TableCell>
                      <TableCell className="font-medium">{complaint.customerName}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{complaint.customerEmail || '-'}</TableCell>
                      <TableCell className="max-w-[180px] truncate">{complaint.subject}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {complaint.category}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', priorityColors[complaint.priority])}>
                          {complaint.priority}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', sentimentColors[complaint.sentiment])}>
                          {complaint.sentiment}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm font-medium">{complaint.aiConfidence}%</span>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn('capitalize', statusColors[complaint.status])}>
                          {complaint.status.replace('-', ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(complaint.createdAt).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleViewDetails(complaint)}
                            className="h-8 w-8"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleViewDetails(complaint)}
                            className="h-8 w-8"
                          >
                            <MessageSquare className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => void handleSingleEscalate(complaint.id)}
                            className="h-8 w-8"
                            disabled={isMutating}
                          >
                            <AlertTriangle className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-6">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(event) => {
                      event.preventDefault()
                      if (currentPage > 1) {
                        setCurrentPage(currentPage - 1)
                      }
                    }}
                    className={currentPage === 1 ? 'pointer-events-none opacity-50' : ''}
                  />
                </PaginationItem>

                {Array.from({ length: Math.min(5, totalPages) }, (_, index) => {
                  let page: number
                  if (totalPages <= 5) {
                    page = index + 1
                  } else if (currentPage <= 3) {
                    page = index + 1
                  } else if (currentPage >= totalPages - 2) {
                    page = totalPages - 4 + index
                  } else {
                    page = currentPage - 2 + index
                  }

                  return (
                    <PaginationItem key={page}>
                      <PaginationLink
                        href="#"
                        onClick={(event) => {
                          event.preventDefault()
                          setCurrentPage(page)
                        }}
                        isActive={currentPage === page}
                      >
                        {page}
                      </PaginationLink>
                    </PaginationItem>
                  )
                })}

                {totalPages > 5 && currentPage < totalPages - 2 && (
                  <PaginationItem>
                    <PaginationEllipsis />
                  </PaginationItem>
                )}

                <PaginationItem>
                  <PaginationNext
                    href="#"
                    onClick={(event) => {
                      event.preventDefault()
                      if (currentPage < totalPages) {
                        setCurrentPage(currentPage + 1)
                      }
                    }}
                    className={currentPage === totalPages ? 'pointer-events-none opacity-50' : ''}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        </CardContent>
      </Card>

      <ComplaintDetailModal
        complaint={selectedComplaint}
        open={modalOpen}
        onOpenChange={setModalOpen}
        onComplaintUpdated={handleComplaintUpdated}
      />
    </div>
  )
}

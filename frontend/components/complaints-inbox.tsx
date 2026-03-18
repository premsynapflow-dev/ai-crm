"use client"

import { useState, useEffect, useMemo } from 'react'
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
  Calendar
} from 'lucide-react'
import { generateComplaints, type Complaint } from '@/lib/sample-data'
import { cn } from '@/lib/utils'
import { ComplaintDetailModal } from '@/components/complaint-detail-modal'
import { toast } from 'sonner'

const priorityColors: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700'
}

const sentimentColors: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral: 'bg-gray-100 text-gray-700',
  negative: 'bg-red-100 text-red-700'
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-purple-100 text-purple-700',
  resolved: 'bg-green-100 text-green-700',
  escalated: 'bg-red-100 text-red-700'
}

const ITEMS_PER_PAGE = 20

export function ComplaintsInbox() {
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    setComplaints(generateComplaints(156))
  }, [])

  const filteredComplaints = useMemo(() => {
    return complaints.filter(complaint => {
      const matchesSearch = searchQuery === '' ||
        complaint.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        complaint.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        complaint.id.toLowerCase().includes(searchQuery.toLowerCase())

      const matchesCategory = categoryFilter === 'all' || complaint.category === categoryFilter
      const matchesPriority = priorityFilter === 'all' || complaint.priority === priorityFilter
      const matchesStatus = statusFilter === 'all' || complaint.status === statusFilter

      return matchesSearch && matchesCategory && matchesPriority && matchesStatus
    })
  }, [complaints, searchQuery, categoryFilter, priorityFilter, statusFilter])

  const totalPages = Math.ceil(filteredComplaints.length / ITEMS_PER_PAGE)
  const paginatedComplaints = filteredComplaints.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  )

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(paginatedComplaints.map(c => c.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds)
    if (checked) {
      newSelected.add(id)
    } else {
      newSelected.delete(id)
    }
    setSelectedIds(newSelected)
  }

  const handleBulkResolve = () => {
    setComplaints(prev =>
      prev.map(c =>
        selectedIds.has(c.id) ? { ...c, status: 'resolved' as const } : c
      )
    )
    toast.success(`${selectedIds.size} complaints marked as resolved`)
    setSelectedIds(new Set())
  }

  const handleBulkEscalate = () => {
    setComplaints(prev =>
      prev.map(c =>
        selectedIds.has(c.id) ? { ...c, status: 'escalated' as const } : c
      )
    )
    toast.success(`${selectedIds.size} complaints escalated`)
    setSelectedIds(new Set())
  }

  const handleBulkDelete = () => {
    setComplaints(prev => prev.filter(c => !selectedIds.has(c.id)))
    toast.success(`${selectedIds.size} complaints deleted`)
    setSelectedIds(new Set())
  }

  const handleViewDetails = (complaint: Complaint) => {
    setSelectedComplaint(complaint)
    setModalOpen(true)
  }

  const allSelected = paginatedComplaints.length > 0 && paginatedComplaints.every(c => selectedIds.has(c.id))

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Complaints Inbox</h1>
        <p className="text-muted-foreground mt-1">Manage and respond to customer complaints</p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by ID, customer, or subject..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="pl-10"
                />
              </div>
            </div>

            <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setCurrentPage(1) }}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All Categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="billing">Billing</SelectItem>
                <SelectItem value="technical">Technical</SelectItem>
                <SelectItem value="general">General</SelectItem>
                <SelectItem value="feedback">Feedback</SelectItem>
              </SelectContent>
            </Select>

            <Select value={priorityFilter} onValueChange={(v) => { setPriorityFilter(v); setCurrentPage(1) }}>
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

            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setCurrentPage(1) }}>
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

            <Button variant="outline" className="gap-2">
              <Calendar className="h-4 w-4" />
              Date Range
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.size === 0}
          onClick={handleBulkResolve}
          className="gap-2"
        >
          <CheckCircle2 className="h-4 w-4" />
          Mark as Resolved
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.size === 0}
          onClick={handleBulkEscalate}
          className="gap-2"
        >
          <AlertTriangle className="h-4 w-4" />
          Escalate Selected
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.size === 0}
          onClick={handleBulkDelete}
          className="gap-2 text-red-600 hover:text-red-700"
        >
          <Trash2 className="h-4 w-4" />
          Delete
        </Button>
        {selectedIds.size > 0 && (
          <span className="text-sm text-muted-foreground">
            {selectedIds.size} selected
          </span>
        )}
      </div>

      {/* Complaints Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Complaints</span>
            <span className="text-sm font-normal text-muted-foreground">
              Showing {((currentPage - 1) * ITEMS_PER_PAGE) + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, filteredComplaints.length)} of {filteredComplaints.length}
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
                {paginatedComplaints.map((complaint) => (
                  <TableRow key={complaint.id} className="hover:bg-muted/50">
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.has(complaint.id)}
                        onCheckedChange={(checked) => handleSelectOne(complaint.id, checked as boolean)}
                      />
                    </TableCell>
                    <TableCell className="font-mono text-sm">{complaint.id}</TableCell>
                    <TableCell className="font-medium">{complaint.customerName}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{complaint.customerEmail}</TableCell>
                    <TableCell className="max-w-[180px] truncate">{complaint.subject}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {complaint.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("capitalize", priorityColors[complaint.priority])}>
                        {complaint.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("capitalize", sentimentColors[complaint.sentiment])}>
                        {complaint.sentiment === 'positive' ? '😊' : complaint.sentiment === 'negative' ? '😠' : '😐'}{' '}
                        {complaint.sentiment}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm font-medium">{complaint.aiConfidence}%</span>
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("capitalize", statusColors[complaint.status])}>
                        {complaint.status.replace('-', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(complaint.createdAt).toLocaleDateString('en-IN', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
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
                          onClick={() => {
                            toast.success('Complaint escalated')
                          }}
                          className="h-8 w-8"
                        >
                          <AlertTriangle className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="mt-6">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (currentPage > 1) setCurrentPage(currentPage - 1)
                    }}
                    className={currentPage === 1 ? 'pointer-events-none opacity-50' : ''}
                  />
                </PaginationItem>
                
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let page: number
                  if (totalPages <= 5) {
                    page = i + 1
                  } else if (currentPage <= 3) {
                    page = i + 1
                  } else if (currentPage >= totalPages - 2) {
                    page = totalPages - 4 + i
                  } else {
                    page = currentPage - 2 + i
                  }
                  
                  return (
                    <PaginationItem key={page}>
                      <PaginationLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
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
                    onClick={(e) => {
                      e.preventDefault()
                      if (currentPage < totalPages) setCurrentPage(currentPage + 1)
                    }}
                    className={currentPage === totalPages ? 'pointer-events-none opacity-50' : ''}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        </CardContent>
      </Card>

      {/* Complaint Detail Modal */}
      <ComplaintDetailModal
        complaint={selectedComplaint}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  )
}

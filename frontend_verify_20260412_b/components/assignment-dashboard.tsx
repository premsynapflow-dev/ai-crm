"use client"

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, ArrowRightLeft, Loader2, Users } from 'lucide-react'
import { toast } from 'sonner'

import {
  assignmentDashboardAPI,
  type AssignmentTeam,
  type AssignmentTeamMember,
  type AssignmentTicket,
} from '@/lib/api/assignment-dashboard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { cn } from '@/lib/utils'

const priorityColors: Record<AssignmentTicket['priority'], string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-rose-100 text-rose-700',
  critical: 'bg-red-100 text-red-700',
}

const statusColors: Record<AssignmentTicket['status'], string> = {
  new: 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-violet-100 text-violet-700',
  resolved: 'bg-emerald-100 text-emerald-700',
  escalated: 'bg-rose-100 text-rose-700',
}

function formatDateTime(value: string | null) {
  if (!value) {
    return 'Just now'
  }

  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function cloneTeams(teams: AssignmentTeam[]): AssignmentTeam[] {
  return teams.map((team) => ({
    ...team,
    members: team.members.map((member) => ({ ...member })),
  }))
}

function cloneTickets(tickets: AssignmentTicket[]): AssignmentTicket[] {
  return tickets.map((ticket) => ({ ...ticket }))
}

function applyOptimisticReassignment(
  teams: AssignmentTeam[],
  tickets: AssignmentTicket[],
  ticketId: string,
  member: AssignmentTeamMember,
  team: AssignmentTeam,
) {
  const nextTeams = cloneTeams(teams)
  const nextTickets = cloneTickets(tickets)
  const ticket = nextTickets.find((item) => item.id === ticketId)
  if (!ticket) {
    return { teams: nextTeams, tickets: nextTickets }
  }

  const previousTeam = nextTeams.find((item) => item.id === ticket.teamId)
  const previousMember = previousTeam?.members.find((item) => item.userId === ticket.assignedUserId)
  if (previousMember && previousMember.userId !== member.userId) {
    previousMember.activeTasks = Math.max(previousMember.activeTasks - 1, 0)
  }

  const nextMember = nextTeams
    .find((item) => item.id === team.id)
    ?.members.find((item) => item.userId === member.userId)
  if (nextMember) {
    const shouldIncrement = ticket.assignedUserId !== member.userId
    nextMember.activeTasks = shouldIncrement ? nextMember.activeTasks + 1 : nextMember.activeTasks
  }

  ticket.assignedTo = member.name
  ticket.assignedUserId = member.userId
  ticket.teamId = team.id
  ticket.teamName = team.name

  return { teams: nextTeams, tickets: nextTickets }
}

export function AssignmentDashboard() {
  const [teams, setTeams] = useState<AssignmentTeam[]>([])
  const [tickets, setTickets] = useState<AssignmentTicket[]>([])
  const [teamFilter, setTeamFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [isLoading, setIsLoading] = useState(true)
  const [reassigningTicketId, setReassigningTicketId] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    const loadAssignments = async () => {
      setIsLoading(true)
      try {
        const payload = await assignmentDashboardAPI.getAssignments()
        if (!active) {
          return
        }
        setTeams(payload.teams)
        setTickets(payload.tickets)
      } catch {
        if (active) {
          setTeams([])
          setTickets([])
          toast.error('Failed to load assignment dashboard')
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadAssignments()

    return () => {
      active = false
    }
  }, [])

  const teamMembersByUserId = useMemo(() => {
    const map = new Map<string, { team: AssignmentTeam; member: AssignmentTeamMember }>()
    teams.forEach((team) => {
      team.members.forEach((member) => {
        if (!member.isActive) {
          return
        }
        if (!map.has(member.userId)) {
          map.set(member.userId, { team, member })
        }
      })
    })
    return map
  }, [teams])

  const assignableUsers = useMemo(() => Array.from(teamMembersByUserId.values()), [teamMembersByUserId])

  const filteredTickets = useMemo(() => {
    return tickets.filter((ticket) => {
      if (teamFilter !== 'all' && ticket.teamId !== teamFilter) {
        return false
      }
      if (statusFilter !== 'all' && ticket.status !== statusFilter) {
        return false
      }
      if (priorityFilter !== 'all' && ticket.priority !== priorityFilter) {
        return false
      }
      return true
    })
  }, [tickets, priorityFilter, statusFilter, teamFilter])

  const handleReassign = async (ticketId: string, userId: string) => {
    const selection = teamMembersByUserId.get(userId)
    if (!selection) {
      return
    }

    const previousTeams = cloneTeams(teams)
    const previousTickets = cloneTickets(tickets)
    const optimistic = applyOptimisticReassignment(teams, tickets, ticketId, selection.member, selection.team)
    setTeams(optimistic.teams)
    setTickets(optimistic.tickets)
    setReassigningTicketId(ticketId)

    try {
      const updatedTicket = await assignmentDashboardAPI.reassignTicket(ticketId, userId)
      setTickets((current) => current.map((ticket) => (ticket.id === ticketId ? { ...ticket, ...updatedTicket } : ticket)))
      toast.success('Ticket reassigned')
    } catch {
      setTeams(previousTeams)
      setTickets(previousTickets)
      toast.error('Failed to reassign ticket')
    } finally {
      setReassigningTicketId(null)
    }
  }

  if (isLoading) {
    return (
      <Card className="border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
        <CardContent className="flex h-60 items-center justify-center">
          <div className="flex items-center gap-3 rounded-full border bg-white px-5 py-3 shadow-sm">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="text-sm font-medium text-muted-foreground">Loading assignment dashboard...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[0.95fr_1.55fr]">
      <Card className="border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
        <CardHeader className="border-b bg-slate-50/70">
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>Team workload</CardTitle>
              <CardDescription>Live capacity and task pressure by team member.</CardDescription>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href="/settings/teams">Manage teams</Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-6">
          {teams.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm text-muted-foreground">
              Create your first team in settings to start routing and workload tracking.
            </div>
          ) : (
            teams.map((team) => (
              <div key={team.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">{team.name}</h3>
                    <p className="text-xs text-muted-foreground">{team.members.length} members</p>
                  </div>
                  <Badge variant="outline" className="border-slate-200 bg-white text-slate-700">
                    {team.members.reduce((sum, member) => sum + member.activeTasks, 0)} active
                  </Badge>
                </div>
                <div className="mt-4 space-y-3">
                  {team.members.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-200 bg-white/70 px-3 py-4 text-sm text-muted-foreground">
                      No members assigned yet.
                    </div>
                  ) : (
                    team.members.map((member) => {
                      const overloaded = member.activeTasks >= member.capacity && member.capacity > 0
                      return (
                        <div
                          key={member.id}
                          className={cn(
                            "rounded-xl border px-3 py-3",
                            overloaded
                              ? "border-rose-200 bg-rose-50/90"
                              : "border-slate-200 bg-white/80",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium text-slate-900">{member.name}</p>
                              <p className="text-xs text-muted-foreground">
                                {member.role} · {member.isActive ? 'active' : 'inactive'}
                              </p>
                            </div>
                            <Badge
                              className={cn(
                                overloaded
                                  ? 'bg-rose-100 text-rose-700'
                                  : 'bg-slate-100 text-slate-700',
                              )}
                            >
                              {member.activeTasks}/{member.capacity}
                            </Badge>
                          </div>
                          {overloaded && (
                            <div className="mt-2 flex items-center gap-2 text-xs font-medium text-rose-700">
                              <AlertTriangle className="h-3.5 w-3.5" />
                              Capacity reached
                            </div>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
        <CardHeader className="border-b bg-slate-50/70">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <CardTitle>Assignment dashboard</CardTitle>
              <CardDescription>Manual overrides for active tickets with client-safe reassignment.</CardDescription>
            </div>
            <div className="flex flex-wrap gap-3">
              <Select value={teamFilter} onValueChange={setTeamFilter}>
                <SelectTrigger className="w-[170px] bg-white">
                  <SelectValue placeholder="All teams" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All teams</SelectItem>
                  {teams.map((team) => (
                    <SelectItem key={team.id} value={team.id}>
                      {team.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[170px] bg-white">
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="in-progress">In progress</SelectItem>
                  <SelectItem value="escalated">Escalated</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
              <Select value={priorityFilter} onValueChange={setPriorityFilter}>
                <SelectTrigger className="w-[170px] bg-white">
                  <SelectValue placeholder="All priorities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All priorities</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Subject</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Assigned To</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead className="w-[210px]">Reassign</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredTickets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7}>
                    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                      <Users className="h-8 w-8 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-slate-900">No tickets match the current filters</p>
                        <p className="text-sm text-muted-foreground">Try widening the team, status, or priority view.</p>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filteredTickets.map((ticket) => (
                  <TableRow key={ticket.id}>
                    <TableCell>
                      <div className="space-y-1">
                        <p className="font-medium text-slate-900">{ticket.subject}</p>
                        <p className="text-xs text-muted-foreground">{ticket.ticketId ?? ticket.id}</p>
                      </div>
                    </TableCell>
                    <TableCell className="capitalize">{ticket.category}</TableCell>
                    <TableCell>
                      <Badge className={priorityColors[ticket.priority]}>{ticket.priority}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={statusColors[ticket.status]}>{ticket.status}</Badge>
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const assignedMember = ticket.assignedUserId ? teamMembersByUserId.get(ticket.assignedUserId) : null
                        const assignedLabel = assignedMember?.member.name ?? ticket.assignedTo ?? 'Unassigned'
                        const assignedTeamName = assignedMember?.team.name ?? ticket.teamName ?? 'No team'
                        return (
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-slate-900">{assignedLabel}</p>
                        <p className="text-xs text-muted-foreground">{assignedTeamName}</p>
                      </div>
                        )
                      })()}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDateTime(ticket.createdAt)}</TableCell>
                    <TableCell>
                      <Select
                        value={ticket.assignedUserId ?? undefined}
                        onValueChange={(value) => void handleReassign(ticket.id, value)}
                        disabled={reassigningTicketId === ticket.id}
                      >
                        <SelectTrigger className="w-full bg-white">
                          <SelectValue placeholder="Pick teammate" />
                        </SelectTrigger>
                        <SelectContent>
                          {assignableUsers.map(({ team, member }) => (
                            <SelectItem key={member.userId} value={member.userId}>
                              {member.name} · {team.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {reassigningTicketId === ticket.id && (
                        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <ArrowRightLeft className="h-3.5 w-3.5 animate-pulse" />
                          Updating assignment...
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  )
}

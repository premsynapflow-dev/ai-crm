import api from '../api'

export interface AssignmentTeamMember {
  id: string
  userId: string
  name: string
  email: string
  role: 'agent' | 'manager'
  activeTasks: number
  capacity: number
  isActive: boolean
}

export interface AssignmentTeam {
  id: string
  name: string
  members: AssignmentTeamMember[]
}

export interface AssignmentTicket {
  id: string
  subject: string
  category: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  status: 'new' | 'in-progress' | 'resolved' | 'escalated'
  assignedTo: string | null
  assignedUserId: string | null
  teamId: string | null
  teamName: string | null
  createdAt: string | null
  ticketId: string | null
}

interface AssignmentTeamMemberApiPayload {
  id: string
  user_id?: string
  name?: string
  email?: string
  role?: string
  active_tasks?: number
  capacity?: number
  is_active?: boolean
}

interface AssignmentTeamApiPayload {
  id: string
  name?: string
  members?: AssignmentTeamMemberApiPayload[]
}

interface AssignmentTicketApiPayload {
  id: string
  subject?: string
  category?: string
  priority?: string
  status?: string
  assigned_to?: string | null
  assigned_user_id?: string | null
  team_id?: string | null
  team_name?: string | null
  created_at?: string | null
  ticket_id?: string | null
}

interface AssignmentPatchResponse {
  success: boolean
  ticket: {
    id: string
    ticket_id?: string
    summary?: string
    category?: string
    priority?: number | null
    created_at?: string | null
    resolution_status?: string | null
    status?: string | null
    assigned_to?: string | null
    assigned_user_id?: string | null
    assigned_team?: string | null
    team_id?: string | null
    state?: string | null
  }
}

function normalizeMember(payload: AssignmentTeamMemberApiPayload): AssignmentTeamMember {
  return {
    id: payload.id,
    userId: String(payload.user_id ?? ''),
    name: payload.name ?? 'SynapFlow User',
    email: payload.email ?? '',
    role: (payload.role ?? 'agent') as AssignmentTeamMember['role'],
    activeTasks: Number(payload.active_tasks ?? 0),
    capacity: Number(payload.capacity ?? 0),
    isActive: Boolean(payload.is_active ?? true),
  }
}

function normalizeTeam(payload: AssignmentTeamApiPayload): AssignmentTeam {
  return {
    id: payload.id,
    name: payload.name ?? 'Team',
    members: (payload.members ?? []).map(normalizeMember),
  }
}

function normalizeTicket(payload: AssignmentTicketApiPayload): AssignmentTicket {
  return {
    id: payload.id,
    subject: payload.subject ?? 'Ticket',
    category: payload.category ?? 'general',
    priority: (payload.priority ?? 'medium') as AssignmentTicket['priority'],
    status: (payload.status ?? 'new') as AssignmentTicket['status'],
    assignedTo: payload.assigned_to ?? null,
    assignedUserId: payload.assigned_user_id ?? null,
    teamId: payload.team_id ?? null,
    teamName: payload.team_name ?? null,
    createdAt: payload.created_at ?? null,
    ticketId: payload.ticket_id ?? null,
  }
}

export const assignmentDashboardAPI = {
  getAssignments: async (): Promise<{ teams: AssignmentTeam[]; tickets: AssignmentTicket[] }> => {
    const response = await api.get('/api/v1/dashboard/assignments')
    return {
      teams: (response.data?.teams ?? []).map(normalizeTeam),
      tickets: (response.data?.tickets ?? []).map(normalizeTicket),
    }
  },

  reassignTicket: async (ticketId: string, userId: string): Promise<AssignmentTicket> => {
    const response = await api.patch<AssignmentPatchResponse>(`/api/v1/tickets/${ticketId}/assign`, {
      user_id: userId,
    })
    const ticket = response.data.ticket
    return {
      id: ticket.id,
      subject: ticket.summary ?? 'Ticket',
      category: ticket.category ?? 'general',
      priority:
        ticket.priority == null || ticket.priority <= 1
          ? 'low'
          : ticket.priority === 2
            ? 'medium'
            : ticket.priority <= 4
              ? 'high'
              : 'critical',
      status:
        ticket.resolution_status === 'resolved'
          ? 'resolved'
          : ticket.status === 'ESCALATE_HIGH'
            ? 'escalated'
            : ticket.state === 'new'
              ? 'new'
              : 'in-progress',
      assignedTo: ticket.assigned_to ?? null,
      assignedUserId: ticket.assigned_user_id ?? null,
      teamId: ticket.team_id ?? null,
      teamName: ticket.assigned_team ?? null,
      createdAt: ticket.created_at ?? null,
      ticketId: ticket.ticket_id ?? null,
    }
  },
}

import api from '../api'

export interface TeamSummary {
  id: string
  name: string
  memberCount: number
  activeTasks: number
  createdAt?: string | null
  updatedAt?: string | null
}

export interface TeamMember {
  id: string
  teamId: string
  userId: string
  name: string
  email: string
  role: 'agent' | 'manager'
  capacity: number
  activeTasks: number
  isActive: boolean
  createdAt?: string | null
  updatedAt?: string | null
}

interface TeamSummaryApiPayload {
  id: string
  name?: string
  member_count?: number
  active_tasks?: number
  created_at?: string | null
  updated_at?: string | null
}

interface TeamMemberApiPayload {
  id: string
  team_id?: string
  user_id?: string
  name?: string
  email?: string
  role?: string
  capacity?: number
  active_tasks?: number
  is_active?: boolean
  created_at?: string | null
  updated_at?: string | null
}

function normalizeTeam(payload: TeamSummaryApiPayload): TeamSummary {
  return {
    id: payload.id,
    name: payload.name ?? 'Team',
    memberCount: Number(payload.member_count ?? 0),
    activeTasks: Number(payload.active_tasks ?? 0),
    createdAt: payload.created_at ?? null,
    updatedAt: payload.updated_at ?? null,
  }
}

function normalizeTeamMember(payload: TeamMemberApiPayload): TeamMember {
  return {
    id: payload.id,
    teamId: String(payload.team_id ?? ''),
    userId: String(payload.user_id ?? ''),
    name: payload.name ?? 'SynapFlow User',
    email: payload.email ?? '',
    role: (payload.role ?? 'agent') as TeamMember['role'],
    capacity: Number(payload.capacity ?? 0),
    activeTasks: Number(payload.active_tasks ?? 0),
    isActive: Boolean(payload.is_active ?? true),
    createdAt: payload.created_at ?? null,
    updatedAt: payload.updated_at ?? null,
  }
}

export const teamsAPI = {
  list: async (): Promise<TeamSummary[]> => {
    const response = await api.get('/api/v1/teams')
    return (response.data?.items ?? []).map(normalizeTeam)
  },

  create: async (name: string): Promise<TeamSummary> => {
    const response = await api.post('/api/v1/teams', { name })
    return normalizeTeam(response.data.team)
  },

  getMembers: async (teamId: string): Promise<{ team: TeamSummary; items: TeamMember[] }> => {
    const response = await api.get(`/api/v1/teams/${teamId}/members`)
    return {
      team: normalizeTeam(response.data.team),
      items: (response.data?.items ?? []).map(normalizeTeamMember),
    }
  },

  addMember: async (
    teamId: string,
    payload: { userId: string; role: TeamMember['role']; capacity: number },
  ): Promise<TeamMember> => {
    const response = await api.post(`/api/v1/teams/${teamId}/members`, {
      user_id: payload.userId,
      role: payload.role,
      capacity: payload.capacity,
    })
    return normalizeTeamMember(response.data.member)
  },

  updateMember: async (
    memberId: string,
    payload: Partial<Pick<TeamMember, 'role' | 'capacity' | 'isActive'>>,
  ): Promise<TeamMember> => {
    const response = await api.patch(`/api/v1/team-members/${memberId}`, {
      role: payload.role,
      capacity: payload.capacity,
      is_active: payload.isActive,
    })
    return normalizeTeamMember(response.data.member)
  },
}

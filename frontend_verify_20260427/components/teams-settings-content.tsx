"use client"

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Loader2, Plus, Users, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { settingsAPI, type SettingsTeamMember } from '@/lib/api/settings'
import { teamsAPI, type TeamMember, type TeamSummary } from '@/lib/api/teams'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

interface MemberDraft {
  role: TeamMember['role']
  capacity: number
  isActive: boolean
}

export function TeamsSettingsContent() {
  const [allUsers, setAllUsers] = useState<SettingsTeamMember[]>([])
  const [teams, setTeams] = useState<TeamSummary[]>([])
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [memberDrafts, setMemberDrafts] = useState<Record<string, MemberDraft>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isMembersLoading, setIsMembersLoading] = useState(false)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newTeamName, setNewTeamName] = useState('')
  const [addMemberDialogOpen, setAddMemberDialogOpen] = useState(false)
  const [newMemberUserId, setNewMemberUserId] = useState('')
  const [newMemberRole, setNewMemberRole] = useState<TeamMember['role']>('agent')
  const [newMemberCapacity, setNewMemberCapacity] = useState('10')
  const [savingMemberId, setSavingMemberId] = useState<string | null>(null)
  const [isCreatingTeam, setIsCreatingTeam] = useState(false)
  const [isAddingMember, setIsAddingMember] = useState(false)

  const selectedTeam = useMemo(
    () => teams.find((team) => team.id === selectedTeamId) ?? null,
    [selectedTeamId, teams],
  )

  const availableUsers = useMemo(() => {
    const existingUserIds = new Set(members.map((member) => member.userId))
    return allUsers.filter((user) => !existingUserIds.has(user.id))
  }, [allUsers, members])

  useEffect(() => {
    let active = true

    const load = async () => {
      setIsLoading(true)
      try {
        const [summary, teamItems] = await Promise.all([
          settingsAPI.getSummary(),
          teamsAPI.list(),
        ])
        if (!active) {
          return
        }
        setAllUsers(summary.team_members)
        setTeams(teamItems)
        setSelectedTeamId((current) => current ?? teamItems[0]?.id ?? null)
      } catch {
        if (active) {
          toast.error('Failed to load teams workspace')
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void load()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selectedTeamId) {
      setMembers([])
      setMemberDrafts({})
      return
    }

    let active = true

    const loadMembers = async () => {
      setIsMembersLoading(true)
      try {
        const response = await teamsAPI.getMembers(selectedTeamId)
        if (!active) {
          return
        }
        setMembers(response.items)
        setMemberDrafts(
          Object.fromEntries(
            response.items.map((member) => [
              member.id,
              {
                role: member.role,
                capacity: member.capacity,
                isActive: member.isActive,
              },
            ]),
          ),
        )
      } catch {
        if (active) {
          setMembers([])
          setMemberDrafts({})
          toast.error('Failed to load team members')
        }
      } finally {
        if (active) {
          setIsMembersLoading(false)
        }
      }
    }

    void loadMembers()

    return () => {
      active = false
    }
  }, [selectedTeamId])

  const refreshTeams = async (preferredTeamId?: string) => {
    const nextTeams = await teamsAPI.list()
    setTeams(nextTeams)
    setSelectedTeamId((current) => preferredTeamId ?? current ?? nextTeams[0]?.id ?? null)
  }

  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) {
      toast.error('Team name is required')
      return
    }

    setIsCreatingTeam(true)
    try {
      const createdTeam = await teamsAPI.create(newTeamName.trim())
      await refreshTeams(createdTeam.id)
      setCreateDialogOpen(false)
      setNewTeamName('')
      toast.success('Team created')
    } catch {
      toast.error('Failed to create team')
    } finally {
      setIsCreatingTeam(false)
    }
  }

  const handleAddMember = async () => {
    if (!selectedTeamId || !newMemberUserId) {
      toast.error('Choose a user to add')
      return
    }

    setIsAddingMember(true)
    try {
      const createdMember = await teamsAPI.addMember(selectedTeamId, {
        userId: newMemberUserId,
        role: newMemberRole,
        capacity: Number(newMemberCapacity || 0),
      })
      setMembers((current) => [...current, createdMember])
      setMemberDrafts((current) => ({
        ...current,
        [createdMember.id]: {
          role: createdMember.role,
          capacity: createdMember.capacity,
          isActive: createdMember.isActive,
        },
      }))
      await refreshTeams(selectedTeamId)
      setAddMemberDialogOpen(false)
      setNewMemberUserId('')
      setNewMemberRole('agent')
      setNewMemberCapacity('10')
      toast.success('Member added')
    } catch {
      toast.error('Failed to add team member')
    } finally {
      setIsAddingMember(false)
    }
  }

  const handleSaveMember = async (memberId: string) => {
    const draft = memberDrafts[memberId]
    if (!draft) {
      return
    }

    setSavingMemberId(memberId)
    try {
      const updatedMember = await teamsAPI.updateMember(memberId, draft)
      setMembers((current) => current.map((member) => (member.id === memberId ? updatedMember : member)))
      setMemberDrafts((current) => ({
        ...current,
        [memberId]: {
          role: updatedMember.role,
          capacity: updatedMember.capacity,
          isActive: updatedMember.isActive,
        },
      }))
      await refreshTeams(selectedTeamId ?? undefined)
      toast.success('Team member updated')
    } catch {
      toast.error('Failed to update team member')
    } finally {
      setSavingMemberId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[65vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border bg-white px-5 py-3 shadow-sm">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span className="text-sm font-medium text-muted-foreground">Loading teams workspace...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-[28px] border border-white/60 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_34%),linear-gradient(135deg,_rgba(255,255,255,0.97),_rgba(241,245,249,0.92))] p-6 shadow-[0_35px_100px_-55px_rgba(15,23,42,0.65)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Teams management</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              Create operational teams, tune capacities, and manage who can take routed complaint work.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link href="/dashboard">Open assignment dashboard</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.4fr]">
        <Card className="border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
          <CardHeader className="border-b bg-slate-50/70">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>Teams</CardTitle>
                <CardDescription>Create teams for routing, staffing, and workload visibility.</CardDescription>
              </div>
              <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" className="gap-2">
                    <Plus className="h-4 w-4" />
                    Create team
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create a team</DialogTitle>
                    <DialogDescription>Add a new routing team for this client workspace.</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-2">
                    <Label htmlFor="team-name">Team name</Label>
                    <Input
                      id="team-name"
                      value={newTeamName}
                      onChange={(event) => setNewTeamName(event.target.value)}
                      placeholder="Support"
                    />
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateTeam} disabled={isCreatingTeam}>
                      {isCreatingTeam ? 'Creating...' : 'Create team'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 pt-6">
            {teams.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm text-muted-foreground">
                No teams yet. Create one to start assigning members and routing work.
              </div>
            ) : (
              teams.map((team) => (
                <button
                  key={team.id}
                  type="button"
                  onClick={() => setSelectedTeamId(team.id)}
                  className={cn(
                    "w-full rounded-2xl border px-4 py-4 text-left transition-all",
                    selectedTeamId === team.id
                      ? "border-slate-900 bg-slate-900 text-white shadow-lg shadow-slate-300/30"
                      : "border-slate-200 bg-slate-50/70 hover:border-slate-300 hover:bg-white",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{team.name}</p>
                      <p className={cn("mt-1 text-xs", selectedTeamId === team.id ? "text-slate-300" : "text-muted-foreground")}>
                        {team.memberCount} members
                      </p>
                    </div>
                    <Badge variant={selectedTeamId === team.id ? 'secondary' : 'outline'}>
                      {team.activeTasks} active
                    </Badge>
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="border-white/70 bg-white/90 shadow-[0_25px_80px_-50px_rgba(15,23,42,0.55)]">
          <CardHeader className="border-b bg-slate-50/70">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>{selectedTeam?.name ?? 'Team members'}</CardTitle>
                <CardDescription>
                  Manage roles, capacity, and availability for the selected team.
                </CardDescription>
              </div>
              <Dialog open={addMemberDialogOpen} onOpenChange={setAddMemberDialogOpen}>
                <DialogTrigger asChild>
                  <Button disabled={!selectedTeam} className="gap-2">
                    <Users className="h-4 w-4" />
                    Add member
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add team member</DialogTitle>
                    <DialogDescription>Select a user and define how much work they can handle.</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>User</Label>
                      <Select value={newMemberUserId} onValueChange={setNewMemberUserId}>
                        <SelectTrigger>
                          <SelectValue placeholder="Choose a user" />
                        </SelectTrigger>
                        <SelectContent>
                          {availableUsers.map((user) => (
                            <SelectItem key={user.id} value={user.id}>
                              {user.name} · {user.email}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Role</Label>
                        <Select value={newMemberRole} onValueChange={(value) => setNewMemberRole(value as TeamMember['role'])}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="agent">Agent</SelectItem>
                            <SelectItem value="manager">Manager</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Capacity</Label>
                        <Input
                          type="number"
                          min={0}
                          value={newMemberCapacity}
                          onChange={(event) => setNewMemberCapacity(event.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setAddMemberDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleAddMember} disabled={isAddingMember || availableUsers.length === 0}>
                      {isAddingMember ? 'Adding...' : 'Add member'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            {!selectedTeam ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center text-sm text-muted-foreground">
                Create a team first to start adding members.
              </div>
            ) : isMembersLoading ? (
              <div className="flex h-56 items-center justify-center">
                <div className="flex items-center gap-3 rounded-full border bg-white px-5 py-3 shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <span className="text-sm font-medium text-muted-foreground">Loading team members...</span>
                </div>
              </div>
            ) : members.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                  <Wrench className="h-5 w-5 text-slate-500" />
                </div>
                <p className="mt-4 font-medium text-slate-900">No members in this team yet</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Add a teammate to start routing and balancing complaint assignments here.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Member</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Capacity</TableHead>
                    <TableHead>Active Tasks</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead className="w-[120px]">Save</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((member) => {
                    const draft = memberDrafts[member.id] ?? {
                      role: member.role,
                      capacity: member.capacity,
                      isActive: member.isActive,
                    }
                    const overloaded = member.activeTasks >= draft.capacity && draft.capacity > 0
                    return (
                      <TableRow key={member.id}>
                        <TableCell>
                          <div className="space-y-1">
                            <p className="font-medium text-slate-900">{member.name}</p>
                            <p className="text-xs text-muted-foreground">{member.email}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Select
                            value={draft.role}
                            onValueChange={(value) => {
                              setMemberDrafts((current) => ({
                                ...current,
                                [member.id]: {
                                  ...draft,
                                  role: value as TeamMember['role'],
                                },
                              }))
                            }}
                          >
                            <SelectTrigger className="w-[140px] bg-white">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="agent">Agent</SelectItem>
                              <SelectItem value="manager">Manager</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            min={0}
                            className="w-[110px]"
                            value={draft.capacity}
                            onChange={(event) => {
                              setMemberDrafts((current) => ({
                                ...current,
                                [member.id]: {
                                  ...draft,
                                  capacity: Number(event.target.value || 0),
                                },
                              }))
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Badge className={overloaded ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-700'}>
                            {member.activeTasks}/{draft.capacity}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Switch
                            checked={draft.isActive}
                            onCheckedChange={(checked) => {
                              setMemberDrafts((current) => ({
                                ...current,
                                [member.id]: {
                                  ...draft,
                                  isActive: checked,
                                },
                              }))
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            onClick={() => void handleSaveMember(member.id)}
                            disabled={savingMemberId === member.id}
                          >
                            {savingMemberId === member.id ? 'Saving...' : 'Save'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Users, Route, Loader2, UserPlus, Tag } from "lucide-react";

interface Team {
  id: string;
  name: string;
  member_count: number;
  active_tasks: number;
  routing_categories: string[];
  created_at: string | null;
}

interface Member {
  id: string;
  team_id: string;
  user_id: string;
  name: string;
  email: string;
  role: string;
  capacity: number;
  active_tasks: number;
  is_active: boolean;
}

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface RoutingRule {
  id: string;
  category: string;
  team_id: string;
}

export function Teams() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);

  // Create team dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [creating, setCreating] = useState(false);

  // Manage members dialog
  const [membersTeam, setMembersTeam] = useState<Team | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedRole, setSelectedRole] = useState("agent");

  // Routing rules dialog
  const [routingTeam, setRoutingTeam] = useState<Team | null>(null);
  const [routingRules, setRoutingRules] = useState<RoutingRule[]>([]);
  const [routingLoading, setRoutingLoading] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  const [addingRule, setAddingRule] = useState(false);

  useEffect(() => {
    loadTeams();
  }, []);

  const loadTeams = async () => {
    setLoading(true);
    try {
      const data = await api.teams.listRaw();
      setTeams(data.items);
    } catch {
      toast.error("Failed to load teams");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) return;
    setCreating(true);
    try {
      await api.teams.create(newTeamName.trim());
      toast.success("Team created");
      setCreateOpen(false);
      setNewTeamName("");
      loadTeams();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message;
      toast.error(msg?.includes("already exists") ? "A team with that name already exists" : "Failed to create team");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteTeam = async (team: Team) => {
    if (!confirm(`Delete team "${team.name}"? This cannot be undone.`)) return;
    try {
      await api.teams.delete(team.id);
      toast.success("Team deleted");
      loadTeams();
    } catch {
      toast.error("Failed to delete team");
    }
  };

  // --- Members ---

  const openManageMembers = async (team: Team) => {
    setMembersTeam(team);
    setMembersLoading(true);
    setSelectedUserId("");
    setSelectedRole("agent");
    try {
      const [membersData, usersData] = await Promise.all([
        api.teams.getMembers(team.id),
        api.users.list(),
      ]);
      setMembers(membersData.items);
      setAllUsers(usersData.items);
    } catch {
      toast.error("Failed to load members");
    } finally {
      setMembersLoading(false);
    }
  };

  const handleAddMember = async () => {
    if (!membersTeam || !selectedUserId) return;
    setAddingMember(true);
    try {
      await api.teams.addMember(membersTeam.id, { user_id: selectedUserId, role: selectedRole, capacity: 10 });
      toast.success("Member added");
      setSelectedUserId("");
      const data = await api.teams.getMembers(membersTeam.id);
      setMembers(data.items);
      loadTeams();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message;
      toast.error(msg?.includes("already a member") ? "User is already in this team" : "Failed to add member");
    } finally {
      setAddingMember(false);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    try {
      await api.teams.removeMember(memberId);
      toast.success("Member removed");
      setMembers((prev) => prev.filter((m) => m.id !== memberId));
      loadTeams();
    } catch {
      toast.error("Failed to remove member");
    }
  };

  const availableUsers = allUsers.filter((u) => !members.some((m) => m.user_id === u.id));

  // --- Routing ---

  const openEditRouting = async (team: Team) => {
    setRoutingTeam(team);
    setRoutingLoading(true);
    setNewCategory("");
    try {
      const data = await api.teams.getRoutingRules(team.id);
      setRoutingRules(data.items);
    } catch {
      toast.error("Failed to load routing rules");
    } finally {
      setRoutingLoading(false);
    }
  };

  const handleAddRule = async () => {
    if (!routingTeam || !newCategory.trim()) return;
    setAddingRule(true);
    try {
      await api.teams.addRoutingRule(routingTeam.id, newCategory.trim());
      toast.success("Category added");
      setNewCategory("");
      const data = await api.teams.getRoutingRules(routingTeam.id);
      setRoutingRules(data.items);
      loadTeams();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message;
      toast.error(msg?.includes("already assigned") ? "This category is already assigned to a team" : "Failed to add category");
    } finally {
      setAddingRule(false);
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    try {
      await api.teams.deleteRoutingRule(ruleId);
      toast.success("Category removed");
      setRoutingRules((prev) => prev.filter((r) => r.id !== ruleId));
      loadTeams();
    } catch {
      toast.error("Failed to remove category");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Teams</h1>
          <p className="text-gray-600">Manage teams and routing rules</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4 mr-2" />
          Create Team
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <Loader2 className="size-5 animate-spin mr-2" />
          Loading teams…
        </div>
      ) : teams.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center text-gray-500">
            <Users className="size-12 mx-auto mb-4 text-gray-300" />
            <p className="font-medium">No teams yet</p>
            <p className="text-sm mt-1">Create your first team to start routing complaints</p>
            <Button className="mt-4" onClick={() => setCreateOpen(true)}>
              <Plus className="size-4 mr-2" />
              Create Team
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {teams.map((team) => (
            <Card key={team.id}>
              <CardContent className="pt-5">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold">{team.name}</h3>
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center gap-2 text-sm">
                        <Users className="size-4 text-gray-400" />
                        <span className="text-gray-600">
                          {team.member_count} {team.member_count === 1 ? "member" : "members"}
                        </span>
                        {team.active_tasks > 0 && (
                          <span className="text-gray-400">· {team.active_tasks} active tasks</span>
                        )}
                      </div>
                      <div className="flex items-start gap-2 text-sm">
                        <Route className="size-4 text-gray-400 mt-0.5 shrink-0" />
                        {team.routing_categories.length === 0 ? (
                          <span className="text-gray-400 italic">No routing categories assigned</span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {team.routing_categories.map((cat) => (
                              <Badge key={cat} variant="outline" className="text-xs">{cat}</Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button size="sm" variant="outline" onClick={() => openManageMembers(team)}>
                      <UserPlus className="size-4 mr-1.5" />
                      Members
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openEditRouting(team)}>
                      <Tag className="size-4 mr-1.5" />
                      Routing
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      onClick={() => handleDeleteTeam(team)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Team Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Team</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label htmlFor="team-name">Team Name</Label>
              <Input
                id="team-name"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                placeholder="e.g. Support Team"
                onKeyDown={(e) => e.key === "Enter" && handleCreateTeam()}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreateTeam} disabled={!newTeamName.trim() || creating}>
              {creating && <Loader2 className="size-4 mr-2 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manage Members Dialog */}
      <Dialog open={!!membersTeam} onOpenChange={(o) => !o && setMembersTeam(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Members — {membersTeam?.name}</DialogTitle>
          </DialogHeader>

          {membersLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-5 animate-spin text-gray-400" />
            </div>
          ) : (
            <div className="space-y-4">
              {/* Add member */}
              {availableUsers.length > 0 ? (
                <div className="flex gap-2">
                  <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder="Select user to add…" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableUsers.map((u) => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.name} ({u.email})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={selectedRole} onValueChange={setSelectedRole}>
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="agent">Agent</SelectItem>
                      <SelectItem value="manager">Manager</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button onClick={handleAddMember} disabled={!selectedUserId || addingMember}>
                    {addingMember ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-gray-500">All users are already in this team.</p>
              )}

              {/* Members list */}
              {members.length === 0 ? (
                <p className="text-center py-6 text-gray-400 text-sm">No members yet</p>
              ) : (
                <div className="divide-y border rounded-lg">
                  {members.map((m) => (
                    <div key={m.id} className="flex items-center justify-between px-4 py-3">
                      <div>
                        <div className="font-medium text-sm">{m.name}</div>
                        <div className="text-xs text-gray-500">{m.email}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs capitalize">{m.role}</Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-red-500 hover:text-red-700 h-7 w-7 p-0"
                          onClick={() => handleRemoveMember(m.id)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setMembersTeam(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Routing Dialog */}
      <Dialog open={!!routingTeam} onOpenChange={(o) => !o && setRoutingTeam(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Routing Categories — {routingTeam?.name}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-500 -mt-2">
            Complaints in these categories will be routed to this team.
          </p>

          {routingLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-5 animate-spin text-gray-400" />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Input
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="e.g. Billing, Technical, Shipping…"
                  onKeyDown={(e) => e.key === "Enter" && handleAddRule()}
                />
                <Button onClick={handleAddRule} disabled={!newCategory.trim() || addingRule}>
                  {addingRule ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                </Button>
              </div>

              {routingRules.length === 0 ? (
                <p className="text-center py-4 text-gray-400 text-sm">No categories assigned yet</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {routingRules.map((r) => (
                    <div
                      key={r.id}
                      className="flex items-center gap-1.5 bg-gray-100 rounded-full px-3 py-1 text-sm"
                    >
                      <span>{r.category}</span>
                      <button
                        onClick={() => handleDeleteRule(r.id)}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setRoutingTeam(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

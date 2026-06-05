import { useEffect, useState, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Checkbox } from "../components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { api, Complaint, Team } from "../lib/api";
import {
  Search,
  Filter,
  Mail,
  MessageSquare,
  Phone,
  Globe,
  Clock,
  AlertCircle,
  RefreshCw,
  TrendingUp,
  CheckCircle,
  Trash2,
} from "lucide-react";
import { Link } from "react-router";
import { toast } from "sonner";

const AUTO_REFRESH_MS = 30_000;

export function ComplaintsInbox() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadComplaints = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const data = await api.complaints.list({
        status: statusFilter !== "all" ? statusFilter : undefined,
        priority: priorityFilter !== "all" ? priorityFilter : undefined,
        search: searchQuery || undefined,
      });
      setComplaints(data);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      const msg = (err as Error)?.message || "Failed to load complaints";
      if (!silent) setError(msg);
      console.error("Failed to load complaints:", err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [statusFilter, priorityFilter, searchQuery]);

  // Initial load
  useEffect(() => {
    loadComplaints();
  }, [loadComplaints]);

  // Auto-refresh every 30s
  useEffect(() => {
    refreshTimerRef.current = setInterval(() => loadComplaints(true), AUTO_REFRESH_MS);
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [loadComplaints]);

  // Load teams once
  useEffect(() => {
    api.teams.list().then(setTeams).catch(() => null);
  }, []);

  const allAgents = teams.flatMap((t) => t.members);

  const setAction = (id: string, on: boolean) =>
    setActionLoading((prev) => ({ ...prev, [id]: on }));

  const handleAssignTeam = async (complaint: Complaint, teamId: string) => {
    setAction(complaint.id, true);
    try {
      await api.complaints.assign(complaint.id, teamId === "unassigned" ? null : teamId, null);
      await loadComplaints(true);
      toast.success("Team assigned");
    } catch (err: unknown) {
      toast.error((err as Error)?.message || "Failed to assign team");
    } finally {
      setAction(complaint.id, false);
    }
  };

  const handleAssignAgent = async (complaint: Complaint, agentId: string) => {
    setAction(complaint.id, true);
    try {
      await api.complaints.assign(complaint.id, complaint.team_id, agentId === "unassigned" ? null : agentId);
      await loadComplaints(true);
      toast.success("Agent assigned");
    } catch (err: unknown) {
      toast.error((err as Error)?.message || "Failed to assign agent");
    } finally {
      setAction(complaint.id, false);
    }
  };

  const handleEscalate = async (complaint: Complaint) => {
    setAction(complaint.id, true);
    try {
      await api.complaints.setStatus(complaint.id, "escalated");
      await loadComplaints(true);
      toast.success("Ticket escalated");
    } catch (err: unknown) {
      toast.error((err as Error)?.message || "Failed to escalate");
    } finally {
      setAction(complaint.id, false);
    }
  };

  const handleResolve = async (complaint: Complaint) => {
    const isResolved = complaint.status === "resolved";
    setAction(complaint.id, true);
    try {
      await api.complaints.setStatus(complaint.id, isResolved ? "in-progress" : "resolved");
      await loadComplaints(true);
      toast.success(isResolved ? "Ticket re-opened" : "Ticket resolved");
    } catch (err: unknown) {
      toast.error((err as Error)?.message || "Failed to update status");
    } finally {
      setAction(complaint.id, false);
    }
  };

  const toggleSelect = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleSelectAll = () => {
    if (selectedIds.size === complaints.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(complaints.map((c) => c.id)));
    }
  };

  const handleBulkEscalate = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await Promise.all([...selectedIds].map((id) => api.complaints.setStatus(id, "escalated")));
      toast.success(`Escalated ${selectedIds.size} ticket${selectedIds.size !== 1 ? "s" : ""}`);
      setSelectedIds(new Set());
      await loadComplaints(true);
    } catch {
      toast.error("Failed to escalate some tickets");
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkResolve = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await Promise.all([...selectedIds].map((id) => api.complaints.setStatus(id, "resolved")));
      toast.success(`Resolved ${selectedIds.size} ticket${selectedIds.size !== 1 ? "s" : ""}`);
      setSelectedIds(new Set());
      await loadComplaints(true);
    } catch {
      toast.error("Failed to resolve some tickets");
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`Delete ${selectedIds.size} ticket${selectedIds.size !== 1 ? "s" : ""}? This cannot be undone.`)) return;
    setBulkLoading(true);
    try {
      await Promise.all([...selectedIds].map((id) => api.complaints.delete(id)));
      toast.success(`Deleted ${selectedIds.size} ticket${selectedIds.size !== 1 ? "s" : ""}`);
      setSelectedIds(new Set());
      await loadComplaints(true);
    } catch {
      toast.error("Failed to delete some tickets");
    } finally {
      setBulkLoading(false);
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case "email":
      case "gmail":
        return <Mail className="size-4" />;
      case "whatsapp":
        return <MessageSquare className="size-4" />;
      case "voice":
        return <Phone className="size-4" />;
      case "chat":
        return <MessageSquare className="size-4" />;
      default:
        return <Globe className="size-4" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      new: "default",
      "in-progress": "secondary",
      escalated: "destructive",
      resolved: "outline",
    };
    return (
      <Badge variant={variants[status] || "default"} className="capitalize">
        {status}
      </Badge>
    );
  };

  const getSentimentBadge = (label: string) => {
    const colors: Record<string, string> = {
      positive: "bg-green-100 text-green-800",
      neutral: "bg-gray-100 text-gray-800",
      negative: "bg-red-100 text-red-800",
    };
    return (
      <Badge className={colors[label] || "bg-gray-100 text-gray-800"}>{label || "neutral"}</Badge>
    );
  };

  const getPriorityBadge = (priority: number) => {
    const labels = ["", "Low", "Low", "Medium", "High", "Critical"];
    const colors = [
      "",
      "text-gray-600",
      "text-gray-600",
      "text-yellow-600",
      "text-orange-600",
      "text-red-600",
    ];
    const idx = Math.max(0, Math.min(5, priority));
    return (
      <span className={`text-sm font-medium ${colors[idx]}`}>{labels[idx]}</span>
    );
  };

  const getSLABadge = (sla_status: string) => {
    const variants: Record<
      string,
      { variant: "default" | "secondary" | "destructive" | "outline"; icon?: React.ReactNode }
    > = {
      on_track: { variant: "outline" },
      at_risk: { variant: "secondary" },
      breached: { variant: "destructive", icon: <AlertCircle className="size-3 mr-1" /> },
    };
    const config = variants[sla_status] || variants.on_track;
    return (
      <Badge variant={config.variant} className="capitalize flex items-center">
        {config.icon}
        {(sla_status || "on_track").replace("_", " ")}
      </Badge>
    );
  };

  const handleExport = () => {
    if (complaints.length === 0) {
      toast.info("No complaints to export");
      return;
    }
    const csv = [
      [
        "Ticket",
        "Summary",
        "Customer",
        "Email",
        "Source",
        "Status",
        "Priority",
        "Sentiment",
        "SLA",
        "Team",
        "Created",
      ].join(","),
      ...complaints.map((c) => {
        const teamName =
          teams.find((t) => t.id === c.team_id)?.name ?? "";
        return [
          c.ticket_number,
          `"${(c.summary || "").replace(/"/g, '""')}"`,
          `"${c.customer_name}"`,
          c.customer_email,
          c.source,
          c.status,
          c.priority,
          c.sentiment_label,
          c.sla_status,
          `"${teamName}"`,
          new Date(c.created_at).toLocaleDateString(),
        ].join(",");
      }),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `complaints-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(`Exported ${complaints.length} complaint${complaints.length !== 1 ? "s" : ""}`);
  };

  const teamAgents = (teamId: string | null) =>
    teamId ? (teams.find((t) => t.id === teamId)?.members ?? allAgents) : allAgents;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Inbox</h1>
          <p className="text-gray-600">Review and manage incoming tickets</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => loadComplaints()} disabled={loading}>
            <RefreshCw className={`size-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={handleExport}>Export CSV</Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-gray-400" />
              <Input
                placeholder="Search complaints..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadComplaints()}
                className="pl-10"
              />
            </div>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="in-progress">In Progress</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
              </SelectContent>
            </Select>

            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" onClick={() => loadComplaints()} disabled={loading}>
              <Filter className="size-4 mr-2" />
              Apply Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Complaints Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              {loading
                ? "Loading…"
                : error
                ? "Error"
                : `${complaints.length} Complaint${complaints.length !== 1 ? "s" : ""}`}
            </CardTitle>
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500 mr-1">
                  {selectedIds.size} selected
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-orange-600 border-orange-200 hover:bg-orange-50 h-8"
                  onClick={handleBulkEscalate}
                  disabled={bulkLoading}
                >
                  <TrendingUp className="size-3.5 mr-1.5" />
                  Escalate
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-green-600 border-green-200 hover:bg-green-50 h-8"
                  onClick={handleBulkResolve}
                  disabled={bulkLoading}
                >
                  <CheckCircle className="size-3.5 mr-1.5" />
                  Mark Resolved
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-red-600 border-red-200 hover:bg-red-50 h-8"
                  onClick={handleBulkDelete}
                  disabled={bulkLoading}
                >
                  <Trash2 className="size-3.5 mr-1.5" />
                  Delete
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-500 gap-2">
              <RefreshCw className="size-4 animate-spin" />
              Loading complaints…
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <AlertCircle className="size-8 text-red-500" />
              <p className="text-red-600 font-medium">Failed to load complaints</p>
              <p className="text-sm text-gray-500">{error}</p>
              <Button variant="outline" size="sm" onClick={() => loadComplaints()}>
                <RefreshCw className="size-4 mr-2" />
                Try Again
              </Button>
            </div>
          ) : complaints.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-gray-500">
              <Clock className="size-8" />
              <p>No items found</p>
              <p className="text-xs text-gray-400">
                {statusFilter !== "all" || priorityFilter !== "all" || searchQuery
                  ? "Try clearing your filters"
                  : "Items will appear here once customers contact you"}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={complaints.length > 0 && selectedIds.size === complaints.length}
                        onCheckedChange={toggleSelectAll}
                        aria-label="Select all"
                      />
                    </TableHead>
                    <TableHead>Ticket</TableHead>
                    <TableHead>Summary</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Sentiment</TableHead>
                    <TableHead>SLA</TableHead>
                    <TableHead>Team</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {complaints.map((complaint) => {
                    const busy = actionLoading[complaint.id];
                    const isResolved = complaint.status === "resolved";
                    const isEscalated = complaint.status === "escalated";
                    const agents = teamAgents(complaint.team_id);
                    return (
                      <TableRow
                        key={complaint.id}
                        className={selectedIds.has(complaint.id) ? "bg-blue-50" : ""}
                      >
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.has(complaint.id)}
                            onCheckedChange={() => toggleSelect(complaint.id)}
                            aria-label={`Select ${complaint.ticket_number}`}
                          />
                        </TableCell>
                        <TableCell className="font-medium text-xs text-gray-500">
                          {complaint.ticket_number || complaint.id.slice(0, 8)}
                        </TableCell>
                        <TableCell className="max-w-[180px] truncate">
                          {complaint.summary}
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div className="font-medium">{complaint.customer_name}</div>
                            <div className="text-gray-500 text-xs">{complaint.customer_email}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getSourceIcon(complaint.source)}
                            <span className="text-sm capitalize">{complaint.source}</span>
                          </div>
                        </TableCell>
                        <TableCell>{getStatusBadge(complaint.status)}</TableCell>
                        <TableCell>{getPriorityBadge(complaint.priority)}</TableCell>
                        <TableCell>{getSentimentBadge(complaint.sentiment_label)}</TableCell>
                        <TableCell>{getSLABadge(complaint.sla_status)}</TableCell>

                        {/* Team assignment */}
                        <TableCell className="min-w-[130px]">
                          <Select
                            value={complaint.team_id ?? "unassigned"}
                            onValueChange={(v) => handleAssignTeam(complaint, v)}
                            disabled={busy}
                          >
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue placeholder="Assign team" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="unassigned">Unassigned</SelectItem>
                              {teams.map((t) => (
                                <SelectItem key={t.id} value={t.id}>
                                  {t.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>

                        {/* Agent assignment */}
                        <TableCell className="min-w-[140px]">
                          <Select
                            value={complaint.assigned_to ?? "unassigned"}
                            onValueChange={(v) => handleAssignAgent(complaint, v)}
                            disabled={busy}
                          >
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue placeholder="Assign agent" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="unassigned">Unassigned</SelectItem>
                              {agents.map((a) => (
                                <SelectItem key={a.id} value={a.id}>
                                  {a.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>

                        <TableCell className="text-sm text-gray-500 whitespace-nowrap">
                          {new Date(complaint.created_at).toLocaleDateString()}
                        </TableCell>

                        {/* Actions */}
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Link to={`/app/complaints/${complaint.id}`}>
                              <Button size="sm" variant="ghost" className="text-xs px-2">
                                View
                              </Button>
                            </Link>
                            {!isEscalated && !isResolved && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-xs px-2 text-orange-600 hover:text-orange-700"
                                onClick={() => handleEscalate(complaint)}
                                disabled={busy}
                                title="Escalate"
                              >
                                <TrendingUp className="size-3.5" />
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant={isResolved ? "secondary" : "ghost"}
                              className={`text-xs px-2 ${
                                isResolved
                                  ? "text-green-700"
                                  : "text-gray-500 hover:text-green-700"
                              }`}
                              onClick={() => handleResolve(complaint)}
                              disabled={busy}
                              title={isResolved ? "Re-open" : "Mark resolved"}
                            >
                              <CheckCircle className="size-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

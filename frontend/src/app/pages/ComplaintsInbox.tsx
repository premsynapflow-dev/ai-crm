import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
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
import { api, Complaint } from "../lib/api";
import { Search, Filter, Mail, MessageSquare, Phone, Globe, Clock, AlertCircle, RefreshCw } from "lucide-react";
import { Link } from "react-router";
import { toast } from "sonner";

export function ComplaintsInbox() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");

  const loadComplaints = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.complaints.list({
        status: statusFilter !== "all" ? statusFilter : undefined,
        priority: priorityFilter !== "all" ? priorityFilter : undefined,
        search: searchQuery || undefined,
      });
      setComplaints(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || "Failed to load complaints";
      setError(msg);
      console.error("Failed to load complaints:", err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, searchQuery]);

  // Initial load
  useEffect(() => {
    loadComplaints();
  }, [loadComplaints]);

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
    const colors = ["", "text-gray-600", "text-gray-600", "text-yellow-600", "text-orange-600", "text-red-600"];
    const idx = Math.max(0, Math.min(5, priority));
    return (
      <span className={`text-sm font-medium ${colors[idx]}`}>
        {labels[idx]}
      </span>
    );
  };

  const getSLABadge = (sla_status: string) => {
    const variants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon?: React.ReactNode }> = {
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
      ["Ticket", "Summary", "Customer", "Email", "Source", "Status", "Priority", "Sentiment", "SLA", "Created"].join(","),
      ...complaints.map((c) =>
        [
          c.ticket_number,
          `"${(c.summary || "").replace(/"/g, '""')}"`,
          `"${c.customer_name}"`,
          c.customer_email,
          c.source,
          c.status,
          c.priority,
          c.sentiment_label,
          c.sla_status,
          new Date(c.created_at).toLocaleDateString(),
        ].join(",")
      ),
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
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Complaints Inbox</h1>
          <p className="text-gray-600">Review and manage customer complaints</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadComplaints} disabled={loading}>
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

            <Button variant="outline" onClick={loadComplaints} disabled={loading}>
              <Filter className="size-4 mr-2" />
              Apply Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Complaints Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            {loading ? "Loading…" : error ? "Error" : `${complaints.length} Complaint${complaints.length !== 1 ? "s" : ""}`}
          </CardTitle>
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
              <Button variant="outline" size="sm" onClick={loadComplaints}>
                <RefreshCw className="size-4 mr-2" />
                Try Again
              </Button>
            </div>
          ) : complaints.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-gray-500">
              <Clock className="size-8" />
              <p>No complaints found</p>
              <p className="text-xs text-gray-400">
                {statusFilter !== "all" || priorityFilter !== "all" || searchQuery
                  ? "Try clearing your filters"
                  : "Complaints will appear here once customers contact you"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticket</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Sentiment</TableHead>
                  <TableHead>SLA</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {complaints.map((complaint) => (
                  <TableRow key={complaint.id}>
                    <TableCell className="font-medium text-xs text-gray-500">
                      {complaint.ticket_number || complaint.id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="max-w-xs truncate">
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
                    <TableCell className="text-sm text-gray-500">
                      {new Date(complaint.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Link to={`/app/complaints/${complaint.id}`}>
                        <Button size="sm" variant="ghost">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

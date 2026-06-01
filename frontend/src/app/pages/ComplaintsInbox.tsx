import { useEffect, useState } from "react";
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
import { Search, Filter, Mail, MessageSquare, Phone, Globe, Clock, AlertCircle } from "lucide-react";
import { Link } from "react-router";

export function ComplaintsInbox() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");

  useEffect(() => {
    loadComplaints();
  }, []);

  const loadComplaints = async () => {
    setLoading(true);
    try {
      const data = await api.complaints.list();
      setComplaints(data);
    } catch (error) {
      console.error("Failed to load complaints:", error);
    } finally {
      setLoading(false);
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case "email":
      case "gmail":
        return <Mail className="size-4" />;
      case "whatsapp":
        return <MessageSquare className="size-4" />;
      case "chat":
        return <MessageSquare className="size-4" />;
      default:
        return <Globe className="size-4" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, any> = {
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
      <Badge className={colors[label] || ""}>{label}</Badge>
    );
  };

  const getPriorityBadge = (priority: number) => {
    const labels = ["", "Low", "Low", "Medium", "High", "Critical"];
    const colors = ["", "text-gray-600", "text-gray-600", "text-yellow-600", "text-orange-600", "text-red-600"];
    return (
      <span className={`text-sm font-medium ${colors[priority]}`}>
        {labels[priority]}
      </span>
    );
  };

  const getSLABadge = (sla_status: string) => {
    const variants: Record<string, { variant: any; icon?: any }> = {
      on_track: { variant: "outline" },
      at_risk: { variant: "secondary" },
      breached: { variant: "destructive", icon: <AlertCircle className="size-3 mr-1" /> },
    };
    const config = variants[sla_status] || variants.on_track;
    return (
      <Badge variant={config.variant} className="capitalize flex items-center">
        {config.icon}
        {sla_status.replace("_", " ")}
      </Badge>
    );
  };

  const filteredComplaints = complaints.filter((complaint) => {
    if (searchQuery && !complaint.summary.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (statusFilter !== "all" && complaint.status !== statusFilter) {
      return false;
    }
    if (priorityFilter !== "all" && complaint.priority.toString() !== priorityFilter) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Complaints Inbox</h1>
          <p className="text-gray-600">Review and manage customer complaints</p>
        </div>
        <Button>Export Data</Button>
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
                <SelectItem value="5">Critical</SelectItem>
                <SelectItem value="4">High</SelectItem>
                <SelectItem value="3">Medium</SelectItem>
                <SelectItem value="2">Low</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline">
              <Filter className="size-4 mr-2" />
              More Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Complaints Table */}
      <Card>
        <CardHeader>
          <CardTitle>{filteredComplaints.length} Complaints</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading complaints...</div>
          ) : filteredComplaints.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No complaints found</div>
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
                {filteredComplaints.map((complaint) => (
                  <TableRow key={complaint.id}>
                    <TableCell className="font-medium">
                      {complaint.ticket_number}
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

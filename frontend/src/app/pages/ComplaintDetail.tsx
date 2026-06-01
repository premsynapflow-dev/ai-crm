import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Separator } from "../components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Progress } from "../components/ui/progress";
import { api, Complaint } from "../lib/api";
import {
  ArrowLeft,
  Mail,
  MessageSquare,
  Clock,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  Send,
  Edit,
} from "lucide-react";
import { toast } from "sonner";

export function ComplaintDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState("");
  const [editedAIReply, setEditedAIReply] = useState("");

  useEffect(() => {
    if (id) {
      loadComplaint(id);
    }
  }, [id]);

  const loadComplaint = async (complaintId: string) => {
    setLoading(true);
    try {
      const data = await api.complaints.get(complaintId);
      setComplaint(data);
      setEditedAIReply(data?.ai_reply || "");
    } catch (error) {
      console.error("Failed to load complaint:", error);
      toast.error("Failed to load complaint");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAIReply = async () => {
    if (!complaint) return;
    try {
      await api.replyQueue.approve(complaint.id, editedAIReply);
      toast.success("AI reply approved and sent!");
      navigate("/app/reply-queue");
    } catch (error) {
      toast.error("Failed to approve reply");
    }
  };

  const handleRejectAIReply = async () => {
    if (!complaint) return;
    try {
      await api.replyQueue.reject(complaint.id);
      toast.success("AI reply rejected");
      setComplaint({ ...complaint, ai_reply_status: "rejected" });
    } catch (error) {
      toast.error("Failed to reject reply");
    }
  };

  const handleSendManualReply = async () => {
    if (!complaint || !replyText.trim()) return;
    try {
      await api.complaints.update(complaint.id, { status: "in-progress" });
      toast.success("Reply sent successfully!");
      setReplyText("");
    } catch (error) {
      toast.error("Failed to send reply");
    }
  };

  if (loading || !complaint) {
    return <div className="p-6">Loading...</div>;
  }

  const emotionData = Object.entries(complaint.sentiment_indicators).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: Math.round((value as number) * 100),
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/app/complaints")}>
          <ArrowLeft className="size-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{complaint.ticket_number}</h1>
          <p className="text-gray-600">{complaint.summary}</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className="capitalize">
            {complaint.source}
          </Badge>
          <Badge variant={complaint.sla_status === "breached" ? "destructive" : "secondary"}>
            {complaint.sla_status.replace("_", " ")}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Conversation Thread */}
          <Card>
            <CardHeader>
              <CardTitle>Conversation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {complaint.thread_messages.map((message) => (
                <div
                  key={message.id}
                  className={`p-4 rounded-lg ${
                    message.direction === "inbound"
                      ? "bg-gray-100"
                      : "bg-blue-50 ml-8"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{message.sender}</span>
                    <span className="text-xs text-gray-500">
                      {new Date(message.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm">{message.content}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* AI Reply Draft */}
          {complaint.ai_reply && complaint.ai_reply_status === "pending" && (
            <Card className="border-blue-200">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="size-5 text-blue-600" />
                    <CardTitle>AI-Generated Reply</CardTitle>
                  </div>
                  <Badge variant="secondary">
                    {Math.round((complaint.ai_reply_confidence || 0) * 100)}% Confidence
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  value={editedAIReply}
                  onChange={(e) => setEditedAIReply(e.target.value)}
                  rows={6}
                  className="font-sans"
                />
                <div className="flex gap-2">
                  <Button onClick={handleApproveAIReply} className="flex-1">
                    <CheckCircle className="size-4 mr-2" />
                    Approve & Send
                  </Button>
                  <Button variant="destructive" onClick={handleRejectAIReply}>
                    Reject
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Manual Reply */}
          <Card>
            <CardHeader>
              <CardTitle>Send Manual Reply</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="Type your response..."
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                rows={6}
              />
              <Button onClick={handleSendManualReply} disabled={!replyText.trim()}>
                <Send className="size-4 mr-2" />
                Send Reply
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Customer Info */}
          <Card>
            <CardHeader>
              <CardTitle>Customer</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <div className="font-medium">{complaint.customer_name}</div>
                <div className="text-sm text-gray-500">{complaint.customer_email}</div>
              </div>
              <Separator />
              <Link to={`/app/customers/${complaint.id}`}>
                <Button variant="outline" size="sm" className="w-full">
                  View Profile
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Sentiment Analysis */}
          <Card>
            <CardHeader>
              <CardTitle>Sentiment Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span>Overall</span>
                <Badge
                  className={
                    complaint.sentiment_label === "positive"
                      ? "bg-green-100 text-green-800"
                      : complaint.sentiment_label === "negative"
                      ? "bg-red-100 text-red-800"
                      : "bg-gray-100 text-gray-800"
                  }
                >
                  {complaint.sentiment_label}
                </Badge>
              </div>
              <div className="space-y-3">
                {emotionData.map((emotion) => (
                  <div key={emotion.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{emotion.name}</span>
                      <span className="text-sm text-gray-500">{emotion.value}%</span>
                    </div>
                    <Progress value={emotion.value} className="h-2" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Metadata */}
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Priority</span>
                <span className="font-medium">
                  {["", "Low", "Low", "Medium", "High", "Critical"][complaint.priority]}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Category</span>
                <span className="font-medium">{complaint.category}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Assigned To</span>
                <span className="font-medium">{complaint.assigned_to || "Unassigned"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Escalation</span>
                <span className="font-medium">
                  {complaint.escalation_level === 0 ? "None" : `Level ${complaint.escalation_level}`}
                </span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-gray-600">Created</span>
                <span>{new Date(complaint.created_at).toLocaleString()}</span>
              </div>
              {complaint.rbi_reference && (
                <>
                  <Separator />
                  <div className="flex justify-between">
                    <span className="text-gray-600">RBI Reference</span>
                    <span className="font-mono text-xs">{complaint.rbi_reference}</span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

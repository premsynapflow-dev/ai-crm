import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Separator } from "../components/ui/separator";
import { Progress } from "../components/ui/progress";
import { api, Complaint } from "../lib/api";
import {
  ArrowLeft,
  Mail,
  MessageSquare,
  Phone,
  Globe,
  CheckCircle,
  TrendingUp,
  Send,
  Edit3,
  Bot,
  User,
  RefreshCw,
  XCircle,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

function SourceBadge({ source }: { source: string }) {
  const icons: Record<string, React.ReactNode> = {
    email: <Mail className="size-3.5" />,
    gmail: <Mail className="size-3.5" />,
    whatsapp: <MessageSquare className="size-3.5" />,
    voice: <Phone className="size-3.5" />,
  };
  return (
    <Badge variant="outline" className="flex items-center gap-1 capitalize">
      {icons[source] ?? <Globe className="size-3.5" />}
      {source}
    </Badge>
  );
}

function MessageBubble({
  sender,
  content,
  timestamp,
  direction,
}: {
  sender: string;
  content: string;
  timestamp: string;
  direction: "inbound" | "outbound";
}) {
  const isOutbound = direction === "outbound";
  const initials = (sender || "?")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className={`flex gap-3 ${isOutbound ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`size-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
          isOutbound
            ? "bg-blue-600 text-white"
            : "bg-gray-200 text-gray-700"
        }`}
      >
        {isOutbound ? <Bot className="size-4" /> : initials}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] space-y-1 ${isOutbound ? "items-end" : "items-start"} flex flex-col`}>
        <div className={`flex items-center gap-2 text-xs text-gray-500 ${isOutbound ? "flex-row-reverse" : ""}`}>
          <span className="font-medium">{sender || (isOutbound ? "Support" : "Customer")}</span>
          <span>·</span>
          <span>{new Date(timestamp).toLocaleString()}</span>
        </div>
        <div
          className={`rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap break-words ${
            isOutbound
              ? "bg-blue-600 text-white rounded-tr-sm"
              : "bg-gray-100 text-gray-900 rounded-tl-sm"
          }`}
        >
          {content || <span className="opacity-50 italic">No content</span>}
        </div>
      </div>
    </div>
  );
}

export function ComplaintDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState("");
  const [editing, setEditing] = useState(false);
  const [sending, setSending] = useState(false);
  const [generatingAI, setGeneratingAI] = useState(false);

  useEffect(() => {
    if (id) {
      setComplaint(null);
      setReplyText("");
      setEditing(false);
      loadComplaint(id);
    }
  }, [id]);

  const loadComplaint = async (complaintId: string) => {
    setLoading(true);
    try {
      const data = await api.complaints.get(complaintId);
      setComplaint(data);
      setReplyText(data?.ai_reply || "");
    } catch {
      toast.error("Failed to load complaint");
    } finally {
      setLoading(false);
    }
  };

  const handleSendApprove = async () => {
    if (!complaint) return;
    setSending(true);
    try {
      await api.complaints.sendReply(complaint.id, replyText || complaint.ai_reply || "");
      toast.success(isPending ? "Reply approved and sent!" : "Reply sent!");
      await loadComplaint(complaint.id);
      setEditing(false);
    } catch (err: unknown) {
      toast.error((err as Error)?.message || "Failed to send reply");
    } finally {
      setSending(false);
    }
  };

  const handleReject = async () => {
    if (!complaint) return;
    setSending(true);
    try {
      await api.complaints.rejectReply(complaint.id);
      toast.success("Draft rejected");
      await loadComplaint(complaint.id);
    } catch {
      toast.error("Failed to reject");
    } finally {
      setSending(false);
    }
  };

  const handleGenerateAIReply = async () => {
    if (!complaint) return;
    setGeneratingAI(true);
    try {
      const updated = await api.complaints.generateReply(complaint.id);
      setComplaint(updated);
      setReplyText(updated.ai_reply || "");
      setEditing(false);
      toast.success("AI reply generated");
    } catch (err: unknown) {
      toast.error((err as Error)?.message || "Failed to generate AI reply");
    } finally {
      setGeneratingAI(false);
    }
  };

  if (loading || !complaint) {
    return (
      <div className="flex items-center justify-center p-12 text-gray-500 gap-2">
        <RefreshCw className="size-4 animate-spin" />
        Loading…
      </div>
    );
  }

  const emotionData = Object.entries(complaint.sentiment_indicators).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: Math.round((value as number) * 100),
  }));

  // Build a unified chronological thread — include the complaint itself if no thread messages
  const threadMessages = (() => {
    if (complaint.thread_messages.length > 0) return complaint.thread_messages;
    // Fallback: show the complaint summary as the original inbound message
    return [
      {
        id: `synthetic-${complaint.id}`,
        content: complaint.summary,
        direction: "inbound" as const,
        channel: complaint.source,
        timestamp: complaint.created_at,
        sender: complaint.customer_name || complaint.customer_email,
      },
    ];
  })();

  const aiDraftExists = Boolean(complaint.ai_reply);
  const isPending = complaint.ai_reply_status === "pending";
  const isSent = complaint.ai_reply_status === "sent" || complaint.ai_reply_status === "approved";
  const isRejected = complaint.ai_reply_status === "rejected";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/app/complaints")}>
          <ArrowLeft className="size-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{complaint.ticket_number}</h1>
          <p className="text-gray-600 text-sm">{complaint.summary}</p>
        </div>
        <div className="flex gap-2">
          <SourceBadge source={complaint.source} />
          <Badge variant={complaint.sla_status === "breached" ? "destructive" : "secondary"}>
            {complaint.sla_status.replace("_", " ")}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">

          {/* ── Conversation thread ── */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="size-4" />
                Conversation
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-5 max-h-[520px] overflow-y-auto pr-1">
                {threadMessages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    sender={msg.sender}
                    content={msg.content}
                    timestamp={msg.timestamp}
                    direction={msg.direction}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          {/* ── Unified Reply Card ── */}
          <Card className={aiDraftExists && isPending ? "border-blue-300 shadow-sm" : ""}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {aiDraftExists ? (
                    <Bot className="size-5 text-blue-600" />
                  ) : (
                    <User className="size-5 text-gray-500" />
                  )}
                  <CardTitle className="text-base">
                    {isSent
                      ? "Reply Sent"
                      : aiDraftExists
                      ? "AI-Drafted Reply"
                      : "Reply"}
                  </CardTitle>
                </div>
                <div className="flex items-center gap-2">
                  {aiDraftExists && !isSent && (
                    <Badge variant="secondary" className="text-xs">
                      {Math.round((complaint.ai_reply_confidence || 0) * 100)}% confidence
                    </Badge>
                  )}
                  {!isSent && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1 text-xs"
                      onClick={() => setEditing((e) => !e)}
                    >
                      <Edit3 className="size-3.5" />
                      {editing ? "Preview" : "Edit"}
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {isSent ? (
                /* Sent — read-only */
                <div className="rounded-lg bg-gray-50 dark:bg-gray-800 border dark:border-gray-700 px-4 py-3 text-sm text-gray-700 dark:text-gray-200 whitespace-pre-wrap">
                  {complaint.ai_reply}
                </div>
              ) : (
                <>
                  <Button
                    variant="outline"
                    className="w-full gap-2 border-blue-200 text-blue-700 hover:bg-blue-50"
                    onClick={handleGenerateAIReply}
                    disabled={generatingAI || sending}
                  >
                    {generatingAI ? (
                      <RefreshCw className="size-4 animate-spin" />
                    ) : aiDraftExists ? (
                      <RefreshCw className="size-4" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}
                    {generatingAI ? "Generating…" : aiDraftExists ? "Regenerate AI Reply" : "Generate AI Reply"}
                  </Button>
                  <Textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder={
                      aiDraftExists
                        ? "AI draft loaded — edit or send as-is"
                        : "Type your reply…"
                    }
                    rows={7}
                    readOnly={!editing && aiDraftExists}
                    className={!editing && aiDraftExists ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700 text-gray-800 dark:text-gray-100" : "dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700"}
                  />
                  <div className="flex gap-2">
                    <Button
                      className="flex-1"
                      onClick={handleSendApprove}
                      disabled={!replyText.trim() || sending}
                    >
                      {sending ? (
                        <RefreshCw className="size-4 mr-2 animate-spin" />
                      ) : (
                        <Send className="size-4 mr-2" />
                      )}
                      {isPending ? "Approve & Send" : "Send Reply"}
                    </Button>
                    {isPending && (
                      <Button
                        variant="outline"
                        className="text-red-600 border-red-200 hover:bg-red-50"
                        onClick={handleReject}
                        disabled={sending}
                      >
                        <XCircle className="size-4 mr-1" />
                        Reject
                      </Button>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── Right sidebar ── */}
        <div className="space-y-6">
          {/* Customer */}
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

          {/* Sentiment */}
          <Card>
            <CardHeader>
              <CardTitle>Sentiment Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm">Overall</span>
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

          {/* Details */}
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Status</span>
                <span className="font-medium capitalize">{complaint.status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Priority</span>
                <span className="font-medium">
                  {["", "Low", "Low", "Medium", "High", "Critical"][complaint.priority]}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Category</span>
                <span className="font-medium capitalize">{complaint.category || "—"}</span>
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
                <span className="text-xs">{new Date(complaint.created_at).toLocaleString()}</span>
              </div>
              {complaint.resolved_at && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Resolved</span>
                  <span className="text-xs">{new Date(complaint.resolved_at).toLocaleString()}</span>
                </div>
              )}
              {complaint.rbi_reference && (
                <>
                  <Separator />
                  <div className="flex justify-between">
                    <span className="text-gray-600">RBI Ref</span>
                    <span className="font-mono text-xs">{complaint.rbi_reference}</span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Quick actions */}
          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {complaint.status !== "escalated" && complaint.status !== "resolved" && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full text-orange-600 border-orange-200 hover:bg-orange-50"
                  onClick={async () => {
                    try {
                      await api.complaints.setStatus(complaint.id, "escalated");
                      toast.success("Ticket escalated");
                      await loadComplaint(complaint.id);
                    } catch { toast.error("Failed to escalate"); }
                  }}
                >
                  <TrendingUp className="size-4 mr-2" />
                  Escalate
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className={`w-full ${
                  complaint.status === "resolved"
                    ? "text-gray-600"
                    : "text-green-600 border-green-200 hover:bg-green-50"
                }`}
                onClick={async () => {
                  try {
                    await api.complaints.setStatus(
                      complaint.id,
                      complaint.status === "resolved" ? "in-progress" : "resolved"
                    );
                    toast.success(
                      complaint.status === "resolved" ? "Ticket re-opened" : "Ticket resolved"
                    );
                    await loadComplaint(complaint.id);
                  } catch { toast.error("Failed to update"); }
                }}
              >
                <CheckCircle className="size-4 mr-2" />
                {complaint.status === "resolved" ? "Re-open" : "Mark Resolved"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

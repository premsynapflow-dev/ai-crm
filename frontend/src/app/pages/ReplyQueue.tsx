import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { api, AIReplyDraft } from "../lib/api";
import { Clock, CheckCircle, XCircle, Edit2 } from "lucide-react";
import { toast } from "sonner";

export function ReplyQueue() {
  const [drafts, setDrafts] = useState<AIReplyDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("pending");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedText, setEditedText] = useState("");

  useEffect(() => {
    loadDrafts();
  }, [activeTab]);

  const loadDrafts = async () => {
    setLoading(true);
    try {
      const data = await api.replyQueue.list(activeTab);
      setDrafts(data.filter(d => d.status === activeTab));
    } catch (error) {
      console.error("Failed to load drafts:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: string, text?: string) => {
    try {
      await api.replyQueue.approve(id, text);
      toast.success("Reply approved and sent!");
      loadDrafts();
    } catch (error) {
      toast.error("Failed to approve reply");
    }
  };

  const handleReject = async (id: string) => {
    try {
      await api.replyQueue.reject(id);
      toast.success("Reply rejected");
      loadDrafts();
    } catch (error) {
      toast.error("Failed to reject reply");
    }
  };

  const startEditing = (draft: AIReplyDraft) => {
    setEditingId(draft.id);
    setEditedText(draft.reply_text);
  };

  const saveEdit = async (id: string) => {
    await handleApprove(id, editedText);
    setEditingId(null);
  };

  const pendingDrafts = drafts.filter(d => d.status === "pending");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">AI Reply Queue</h1>
        <p className="text-gray-600">Review and approve AI-generated responses</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Pending Review
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{pendingDrafts.length}</div>
            <p className="text-xs text-gray-500 mt-1">Awaiting approval</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Avg Confidence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {pendingDrafts.length > 0
                ? Math.round(
                    (pendingDrafts.reduce((sum, d) => sum + d.confidence, 0) /
                      pendingDrafts.length) *
                      100
                  )
                : 0}
              %
            </div>
            <p className="text-xs text-gray-500 mt-1">AI confidence score</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Expiring Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {pendingDrafts.filter(d => {
                const hoursRemaining = (new Date(d.expires_at).getTime() - Date.now()) / (1000 * 60 * 60);
                return hoursRemaining < 6;
              }).length}
            </div>
            <p className="text-xs text-gray-500 mt-1">Less than 6 hours left</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="pending">Pending ({pendingDrafts.length})</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="rejected">Rejected</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-4 mt-6">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading drafts...</div>
          ) : drafts.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-gray-500">
                No drafts in this category
              </CardContent>
            </Card>
          ) : (
            drafts.map((draft) => {
              const hoursRemaining = Math.round(
                (new Date(draft.expires_at).getTime() - Date.now()) / (1000 * 60 * 60)
              );
              const isExpiringSoon = hoursRemaining < 6;

              return (
                <Card key={draft.id} className={isExpiringSoon ? "border-orange-200" : ""}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-lg">{draft.complaint_summary}</CardTitle>
                        <div className="text-sm text-gray-600 mt-1">
                          {draft.customer_name} • {draft.customer_email}
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Badge variant="secondary">
                          {Math.round(draft.confidence * 100)}% Confidence
                        </Badge>
                        {draft.hallucination_check === "passed" && (
                          <Badge variant="outline" className="bg-green-50 text-green-700">
                            Verified
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {editingId === draft.id ? (
                      <Textarea
                        value={editedText}
                        onChange={(e) => setEditedText(e.target.value)}
                        rows={6}
                        className="font-sans"
                      />
                    ) : (
                      <div className="p-4 bg-gray-50 rounded-lg">
                        <p className="text-sm whitespace-pre-wrap">{draft.reply_text}</p>
                      </div>
                    )}

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Clock className="size-4" />
                        {draft.status === "pending" && (
                          <span className={isExpiringSoon ? "text-orange-600 font-medium" : ""}>
                            Expires in {hoursRemaining}h
                          </span>
                        )}
                        {draft.status !== "pending" && (
                          <span>
                            {draft.status === "approved" ? "Approved" : "Rejected"} on{" "}
                            {new Date(draft.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>

                      {draft.status === "pending" && (
                        <div className="flex gap-2">
                          {editingId === draft.id ? (
                            <>
                              <Button onClick={() => saveEdit(draft.id)}>
                                <CheckCircle className="size-4 mr-2" />
                                Save & Send
                              </Button>
                              <Button variant="ghost" onClick={() => setEditingId(null)}>
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => startEditing(draft)}
                              >
                                <Edit2 className="size-4 mr-2" />
                                Edit
                              </Button>
                              <Button size="sm" onClick={() => handleApprove(draft.id)}>
                                <CheckCircle className="size-4 mr-2" />
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleReject(draft.id)}
                              >
                                <XCircle className="size-4 mr-2" />
                                Reject
                              </Button>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

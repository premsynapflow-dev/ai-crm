import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { api, ArtifactItem } from "../lib/api";
import {
  FileText,
  CheckCircle,
  XCircle,
  RefreshCw,
  Send,
  Edit2,
  AlertTriangle,
  TrendingUp,
  DollarSign,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  in_review: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  approved: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  delivered: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

function formatINR(value: number): string {
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(1)}Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(1)}L`;
  if (value >= 1e3) return `₹${(value / 1e3).toFixed(1)}K`;
  return `₹${value.toFixed(0)}`;
}

function SectionBlock({ icon: Icon, title, children }: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="size-4 text-gray-500" />
        <h4 className="font-semibold text-sm text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          {title}
        </h4>
      </div>
      {children}
    </div>
  );
}

function ArtifactSections({ sections }: { sections: Record<string, unknown> }) {
  const whatBroke = (sections.what_broke || {}) as Record<string, unknown>;
  const why = (sections.why || {}) as Record<string, unknown>;
  const cost = (sections.cost || {}) as Record<string, unknown>;
  const action = (sections.action || {}) as Record<string, unknown>;

  const issue = String(whatBroke.issue || "No significant issues detected");
  const count = Number(whatBroke.count || 0);
  const changePct = Number(whatBroke.change_pct || 0);

  const insights: string[] = Array.isArray(why.root_cause_insights)
    ? (why.root_cause_insights as string[])
    : [];
  const trending: Array<Record<string, unknown>> = Array.isArray(why.trending_categories)
    ? (why.trending_categories as Array<Record<string, unknown>>)
    : [];

  const revAtRisk = Number(cost.revenue_at_risk || 0);
  const highRisk = Number(cost.high_risk_customers || 0);
  const hasRevData = Boolean(cost.has_revenue_data);

  const narrative = String(action.narrative || "");
  const recs: string[] = Array.isArray(action.top_recommendations)
    ? (action.top_recommendations as string[])
    : [];

  return (
    <div className="space-y-3">
      <SectionBlock icon={AlertTriangle} title="What Broke">
        <p className="text-sm">
          <span className="font-semibold">{issue}</span>
          {count > 0 && (
            <span className="text-gray-600 dark:text-gray-400">
              {" "}— {count} complaints
              <span className={changePct > 0 ? " text-red-600" : " text-green-600"}>
                {" "}({changePct > 0 ? "+" : ""}{changePct.toFixed(0)}% vs last week)
              </span>
            </span>
          )}
        </p>
      </SectionBlock>

      <SectionBlock icon={TrendingUp} title="Why">
        {insights.length > 0 ? (
          <ul className="text-sm space-y-1 list-disc list-inside text-gray-700 dark:text-gray-300">
            {insights.slice(0, 4).map((ins, i) => <li key={i}>{ins}</li>)}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">No patterns detected in this period.</p>
        )}
        {trending.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {trending.map((t, i) => (
              <span key={i} className="inline-flex items-center gap-1 text-xs bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-2 py-0.5 rounded">
                {String(t.category || "")}
                <span className="font-semibold">+{Number(t.change_percentage || 0).toFixed(0)}%</span>
              </span>
            ))}
          </div>
        )}
      </SectionBlock>

      <SectionBlock icon={DollarSign} title="Cost">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {hasRevData
            ? <><span className="font-semibold">{formatINR(revAtRisk)}</span> revenue at risk across <span className="font-semibold">{highRisk}</span> high-churn customers.</>
            : <><span className="font-semibold">{highRisk}</span> customers at high churn risk. Revenue data not yet connected.</>
          }
        </p>
      </SectionBlock>

      <SectionBlock icon={Zap} title="Recommended Actions">
        {narrative && (
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">{narrative}</p>
        )}
        {recs.length > 0 && (
          <ul className="text-sm space-y-1 list-disc list-inside text-gray-700 dark:text-gray-300">
            {recs.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
      </SectionBlock>
    </div>
  );
}

export function Artifacts() {
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState("draft");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedBody, setEditedBody] = useState("");
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  useEffect(() => {
    loadArtifacts();
  }, [activeTab]);

  const loadArtifacts = async () => {
    setLoading(true);
    try {
      const data = await api.artifacts.list(activeTab === "all" ? undefined : activeTab);
      setArtifacts(data.items || []);
    } catch {
      toast.error("Failed to load artifacts");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const artifact = await api.artifacts.generate({ days: 7 });
      toast.success("Digest generated and ready for review");
      setArtifacts((prev) => {
        const exists = prev.find((a) => a.id === artifact.id);
        return exists ? prev.map((a) => (a.id === artifact.id ? artifact : a)) : [artifact, ...prev];
      });
      setSelectedId(artifact.id);
      if (activeTab !== "draft") setActiveTab("draft");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to generate digest");
    } finally {
      setGenerating(false);
    }
  };

  const handleApprove = async (id: string) => {
    setProcessingId(id);
    try {
      const body = editingId === id ? editedBody : undefined;
      const updated = await api.artifacts.approve(id, body || undefined);
      toast.success("Artifact approved");
      setArtifacts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      setEditingId(null);
    } catch {
      toast.error("Failed to approve artifact");
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (id: string) => {
    if (!rejectReason.trim()) {
      toast.error("Please provide a rejection reason");
      return;
    }
    setProcessingId(id);
    try {
      const updated = await api.artifacts.reject(id, rejectReason);
      toast.success("Artifact rejected");
      setArtifacts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      setRejectingId(null);
      setRejectReason("");
    } catch {
      toast.error("Failed to reject artifact");
    } finally {
      setProcessingId(null);
    }
  };

  const handleDeliver = async (id: string) => {
    setProcessingId(id);
    try {
      const updated = await api.artifacts.deliver(id);
      toast.success("Artifact delivered");
      setArtifacts((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to deliver artifact");
    } finally {
      setProcessingId(null);
    }
  };

  const startEditing = (artifact: ArtifactItem) => {
    setEditingId(artifact.id);
    setEditedBody(artifact.edited_body || "");
  };

  const selected = artifacts.find((a) => a.id === selectedId) || artifacts[0] || null;

  const draftCount = artifacts.filter((a) => a.status === "draft" || a.status === "in_review").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Artifacts</h1>
          <p className="text-gray-600 dark:text-gray-400">Weekly operational digests — review, edit, and deliver</p>
        </div>
        <Button onClick={handleGenerate} disabled={generating}>
          {generating ? (
            <RefreshCw className="size-4 mr-2 animate-spin" />
          ) : (
            <FileText className="size-4 mr-2" />
          )}
          Generate this week's digest
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">Pending Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{draftCount}</div>
            <p className="text-xs text-gray-500 mt-1">Awaiting analyst approval</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">Delivered</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {artifacts.filter((a) => a.status === "delivered").length}
            </div>
            <p className="text-xs text-gray-500 mt-1">Sent to pilot</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">Acted On</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {artifacts.filter((a) => a.acted_at !== null).length}
            </div>
            <p className="text-xs text-gray-500 mt-1">Pilot confirmed action taken</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: artifact list */}
        <div className="space-y-3">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full">
              <TabsTrigger value="draft" className="flex-1">Draft ({draftCount})</TabsTrigger>
              <TabsTrigger value="delivered" className="flex-1">Delivered</TabsTrigger>
            </TabsList>
          </Tabs>

          {loading ? (
            <p className="text-center text-gray-500 py-8">Loading...</p>
          ) : artifacts.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-gray-500 text-sm">
                No artifacts yet. Click "Generate" to create this week's digest.
              </CardContent>
            </Card>
          ) : (
            artifacts.map((a) => (
              <Card
                key={a.id}
                className={`cursor-pointer transition-colors ${
                  selected?.id === a.id
                    ? "border-indigo-400 dark:border-indigo-500"
                    : "hover:border-gray-400"
                }`}
                onClick={() => setSelectedId(a.id)}
              >
                <CardContent className="py-3 px-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{a.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {a.period_start} – {a.period_end}
                      </p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${STATUS_COLORS[a.status] || ""}`}>
                      {a.status}
                    </span>
                  </div>
                  {a.summary && (
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">{a.summary}</p>
                  )}
                  {a.acted_at && (
                    <p className="text-xs text-green-600 dark:text-green-400 mt-1 font-medium">✓ Action taken</p>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Right: detail + edit panel */}
        <div className="lg:col-span-2">
          {!selected ? (
            <Card>
              <CardContent className="py-20 text-center text-gray-500">
                Select an artifact to review, or generate this week's digest.
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{selected.title}</CardTitle>
                    <p className="text-sm text-gray-500 mt-1">
                      {selected.period_start} – {selected.period_end}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[selected.status] || ""}`}>
                    {selected.status}
                  </span>
                </div>
                {selected.delivered_at && (
                  <p className="text-xs text-gray-500">
                    Delivered {new Date(selected.delivered_at).toLocaleString()}
                    {selected.opened_at && " · Opened"}
                    {selected.acted_at && " · Action confirmed"}
                  </p>
                )}
              </CardHeader>

              <CardContent className="space-y-4">
                {editingId === selected.id ? (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">Edit the digest body (markdown supported). Leave blank to use the auto-generated content.</p>
                    <Textarea
                      value={editedBody}
                      onChange={(e) => setEditedBody(e.target.value)}
                      rows={14}
                      placeholder="Edit the digest narrative here…"
                      className="font-mono text-sm dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700"
                    />
                  </div>
                ) : (
                  <ArtifactSections sections={selected.sections_json} />
                )}

                {/* Actions for draft / in_review */}
                {(selected.status === "draft" || selected.status === "in_review") && (
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                    {editingId === selected.id ? (
                      <>
                        <Button
                          size="sm"
                          onClick={() => handleApprove(selected.id)}
                          disabled={processingId === selected.id}
                        >
                          {processingId === selected.id ? (
                            <RefreshCw className="size-4 mr-2 animate-spin" />
                          ) : (
                            <CheckCircle className="size-4 mr-2" />
                          )}
                          Save & Approve
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => startEditing(selected)}
                          disabled={!!processingId}
                        >
                          <Edit2 className="size-4 mr-2" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => handleApprove(selected.id)}
                          disabled={!!processingId}
                        >
                          {processingId === selected.id ? (
                            <RefreshCw className="size-4 mr-2 animate-spin" />
                          ) : (
                            <CheckCircle className="size-4 mr-2" />
                          )}
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => setRejectingId(selected.id)}
                          disabled={!!processingId}
                        >
                          <XCircle className="size-4 mr-2" />
                          Reject
                        </Button>
                      </>
                    )}
                  </div>
                )}

                {/* Reject reason input */}
                {rejectingId === selected.id && (
                  <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                    <Textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Reason for rejection…"
                      rows={2}
                      className="text-sm dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleReject(selected.id)}
                        disabled={processingId === selected.id}
                      >
                        Confirm Reject
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => { setRejectingId(null); setRejectReason(""); }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {/* Deliver action for approved */}
                {selected.status === "approved" && (
                  <div className="flex items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                    <Button
                      size="sm"
                      onClick={() => handleDeliver(selected.id)}
                      disabled={processingId === selected.id}
                    >
                      {processingId === selected.id ? (
                        <RefreshCw className="size-4 mr-2 animate-spin" />
                      ) : (
                        <Send className="size-4 mr-2" />
                      )}
                      Deliver now
                    </Button>
                    <p className="text-xs text-gray-500">
                      {selected.recipient ? `Will send to ${selected.recipient}` : "Set recipient in n8n or via API"}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, UploadJob } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import {
  Upload,
  FileText,
  BarChart3,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";

const DATA_TYPES = [
  {
    value: "reviews",
    label: "Product / Service Reviews",
    description: "Star-rated reviews, app store feedback, survey responses",
    columns: "text/review, rating, email, date",
  },
  {
    value: "support_tickets",
    label: "Support Tickets",
    description: "Helpdesk exports from Zendesk, Freshdesk, Jira, etc.",
    columns: "title, description, priority, email, category",
  },
  {
    value: "complaints",
    label: "Complaint / Feedback Exports",
    description: "Generic complaint or feedback CSV from any system",
    columns: "complaint, category, priority, email, date",
  },
  {
    value: "refunds",
    label: "Returns & Refunds",
    description: "Refund / return order exports with order IDs and reasons",
    columns: "order_id, reason, amount, product, email",
  },
] as const;

type DataType = (typeof DATA_TYPES)[number]["value"];

type Step = 1 | 2 | 3;

function stepLabel(s: Step) {
  return ["Upload", "Analyze", "Generate Digest"][s - 1];
}

function StatusBadge({ status }: { status: UploadJob["status"] }) {
  const map: Record<UploadJob["status"], { label: string; className: string }> = {
    processing: { label: "Processing", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" },
    queued: { label: "Queued for AI", className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300" },
    analyzing: { label: "Analyzing", className: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300" },
    done: { label: "Done", className: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300" },
    failed: { label: "Failed", className: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" },
  };
  const s = map[status] ?? { label: status, className: "bg-gray-100 text-gray-700" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${s.className}`}>
      {s.label}
    </span>
  );
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
      <div
        className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function TopIssueRow({ issue }: { issue: { category: string; current_count: number; change_percentage: number } }) {
  const change = issue.change_percentage ?? 0;
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <span className="text-sm font-medium capitalize">{issue.category}</span>
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500">{issue.current_count} tickets</span>
        <span className={`text-xs font-semibold ${change > 0 ? "text-red-500" : change < 0 ? "text-green-500" : "text-gray-400"}`}>
          {change > 0 ? "+" : ""}{change.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

export function Uploads() {
  const navigate = useNavigate();

  // Step state
  const [step, setStep] = useState<Step>(1);

  // Step 1 — Upload
  const [file, setFile] = useState<File | null>(null);
  const [dataType, setDataType] = useState<DataType>("complaints");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Job polling
  const [job, setJob] = useState<UploadJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Step 2 — Analyze
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [errorsExpanded, setErrorsExpanded] = useState(false);

  // Step 3 — Generate
  const [generating, setGenerating] = useState(false);
  const [artifactResult, setArtifactResult] = useState<{
    artifact_id: string;
    artifact_title: string;
  } | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Recent jobs
  const [recentJobs, setRecentJobs] = useState<UploadJob[]>([]);

  useEffect(() => {
    api.uploadIntelligence.listJobs().then(setRecentJobs).catch(() => {});
  }, []);

  // Poll job status
  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const updated = await api.uploadIntelligence.getJob(jobId);
        setJob(updated);
        if (updated.status !== "processing") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          // refresh recent jobs list
          api.uploadIntelligence.listJobs().then(setRecentJobs).catch(() => {});
        }
      } catch {
        clearInterval(pollRef.current!);
        pollRef.current = null;
      }
    }, 2500);
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // File handlers
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const result = await api.uploadIntelligence.upload(file, dataType);
      const initialJob = await api.uploadIntelligence.getJob(result.job_id);
      setJob(initialJob);
      setStep(2);
      startPolling(result.job_id);
    } catch (err: unknown) {
      alert(`Upload failed: ${(err as Error).message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!job) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const updated = await api.uploadIntelligence.analyze(job.id);
      setJob(updated);
      api.uploadIntelligence.listJobs().then(setRecentJobs).catch(() => {});
    } catch (err: unknown) {
      setAnalysisError((err as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerateArtifact = async () => {
    if (!job) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const result = await api.uploadIntelligence.generateArtifact(job.id);
      setArtifactResult({ artifact_id: result.artifact_id, artifact_title: result.artifact_title });
      const updated = await api.uploadIntelligence.getJob(job.id);
      setJob(updated);
      setStep(3);
    } catch (err: unknown) {
      setGenerateError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  const reset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setStep(1);
    setFile(null);
    setJob(null);
    setArtifactResult(null);
    setAnalysisError(null);
    setGenerateError(null);
    setUploading(false);
    setAnalyzing(false);
    setGenerating(false);
    api.uploadIntelligence.listJobs().then(setRecentJobs).catch(() => {});
  };

  const isProcessing = job?.status === "processing";
  const isReadyToAnalyze = job && (job.status === "queued" || job.status === "done") && job.analysis_status === "none";
  const analysisReady = job?.analysis_status === "done";
  const rootCause = (job?.analysis_results as any)?.root_cause;
  const pulse = (job?.analysis_results as any)?.pulse;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold dark:text-white">Upload Intelligence</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Import customer feedback files — SynapFlow classifies, clusters, and generates a digest automatically.
          </p>
        </div>
        {step > 1 && (
          <Button variant="outline" size="sm" onClick={reset}>
            <RefreshCw className="size-4 mr-1.5" /> New Upload
          </Button>
        )}
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm">
        {([1, 2, 3] as Step[]).map((s) => (
          <React.Fragment key={s}>
            <div className={`flex items-center gap-1.5 ${s === step ? "text-indigo-600 dark:text-indigo-400 font-semibold" : s < step ? "text-green-600 dark:text-green-400" : "text-gray-400 dark:text-gray-500"}`}>
              {s < step ? (
                <CheckCircle2 className="size-4" />
              ) : (
                <span className={`size-5 rounded-full border-2 flex items-center justify-center text-xs font-bold ${s === step ? "border-indigo-500 text-indigo-600" : "border-gray-300 dark:border-gray-600"}`}>{s}</span>
              )}
              {stepLabel(s)}
            </div>
            {s < 3 && <div className="h-px w-8 bg-gray-200 dark:bg-gray-700" />}
          </React.Fragment>
        ))}
      </div>

      {/* ─── Step 1: Upload ─── */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Upload className="size-4 text-indigo-500" /> Upload File
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Drop zone */}
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${dragOver ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/30" : "border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-600"}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".csv,.xlsx,.xls,.json"
                onChange={handleFileChange}
              />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileText className="size-8 text-indigo-500" />
                  <div className="text-left">
                    <p className="font-medium dark:text-white">{file.name}</p>
                    <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                  </div>
                  <button
                    className="ml-2 text-gray-400 hover:text-red-500"
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  >
                    <X className="size-4" />
                  </button>
                </div>
              ) : (
                <div className="text-gray-400 space-y-1">
                  <Upload className="size-8 mx-auto mb-2" />
                  <p className="text-sm font-medium dark:text-gray-300">Drop a file here, or click to browse</p>
                  <p className="text-xs">Supports CSV, Excel (.xlsx), and JSON · Max 20 MB</p>
                </div>
              )}
            </div>

            {/* Data type selector */}
            <div className="space-y-2">
              <label className="text-sm font-medium dark:text-white">Data type</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {DATA_TYPES.map((dt) => (
                  <button
                    key={dt.value}
                    className={`text-left p-3 rounded-lg border-2 transition-colors ${dataType === dt.value ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30" : "border-gray-200 dark:border-gray-700 hover:border-indigo-200 dark:hover:border-indigo-700"}`}
                    onClick={() => setDataType(dt.value)}
                  >
                    <p className={`text-sm font-medium ${dataType === dt.value ? "text-indigo-700 dark:text-indigo-300" : "dark:text-white"}`}>{dt.label}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{dt.description}</p>
                    <p className="text-xs text-gray-400 font-mono mt-1 truncate">Columns: {dt.columns}</p>
                  </button>
                ))}
              </div>
            </div>

            <Button
              className="w-full"
              onClick={handleUpload}
              disabled={!file || uploading}
            >
              {uploading ? <><Loader2 className="size-4 mr-2 animate-spin" /> Uploading…</> : <><Upload className="size-4 mr-2" /> Upload & Import</>}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ─── Step 2: Process + Analyze ─── */}
      {step === 2 && job && (
        <div className="space-y-4">
          {/* Progress card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="size-4 text-indigo-500" />
                  {job.filename || "Uploaded file"}
                </CardTitle>
                <StatusBadge status={job.status} />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {isProcessing ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <Loader2 className="size-4 animate-spin" /> Parsing and ingesting records…
                  </div>
                  <ProgressBar value={job.mapped_rows} max={job.total_rows ?? 1} />
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-2xl font-bold dark:text-white">{job.total_rows ?? "—"}</div>
                      <div className="text-xs text-gray-400">Total rows</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-green-600">{job.mapped_rows}</div>
                      <div className="text-xs text-gray-400">Imported</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-red-500">{job.failed_rows}</div>
                      <div className="text-xs text-gray-400">Skipped</div>
                    </div>
                  </div>

                  {job.failed_rows > 0 && job.errors.length > 0 && (
                    <div className="rounded border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-3">
                      <button
                        className="flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-300"
                        onClick={() => setErrorsExpanded((v) => !v)}
                      >
                        <AlertCircle className="size-3.5" />
                        {job.failed_rows} row{job.failed_rows !== 1 ? "s" : ""} skipped
                        {errorsExpanded ? <ChevronUp className="size-3.5 ml-1" /> : <ChevronDown className="size-3.5 ml-1" />}
                      </button>
                      {errorsExpanded && (
                        <ul className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                          {job.errors.slice(0, 20).map((e, i) => (
                            <li key={i} className="text-xs text-amber-700 dark:text-amber-300">
                              Row {e.row}: {e.reason}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Analyze card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="size-4 text-indigo-500" /> Analyze
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {job.analysis_status === "none" && (
                <div className="space-y-3">
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Run root-cause analysis and customer pulse across all ingested complaints.
                    This will surface top issues, trends, and churn signals.
                  </p>
                  <Button
                    onClick={handleAnalyze}
                    disabled={analyzing || isProcessing}
                    className="w-full"
                  >
                    {analyzing
                      ? <><Loader2 className="size-4 mr-2 animate-spin" /> Analyzing…</>
                      : <><BarChart3 className="size-4 mr-2" /> Run Analysis</>}
                  </Button>
                  {analysisError && (
                    <p className="text-sm text-red-500">{analysisError}</p>
                  )}
                  {isProcessing && (
                    <p className="text-xs text-gray-400">Waiting for import to complete…</p>
                  )}
                </div>
              )}

              {job.analysis_status === "running" && (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="size-4 animate-spin" /> Running analysis…
                </div>
              )}

              {job.analysis_status === "failed" && (
                <div className="space-y-2">
                  <p className="text-sm text-red-500">Analysis failed. Try again.</p>
                  <Button variant="outline" size="sm" onClick={handleAnalyze} disabled={analyzing}>
                    {analyzing ? <Loader2 className="size-4 animate-spin" /> : "Retry"}
                  </Button>
                </div>
              )}

              {analysisReady && rootCause && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-green-600 dark:text-green-400 text-sm font-medium">
                    <CheckCircle2 className="size-4" /> Analysis complete
                  </div>

                  {/* Top issues */}
                  {rootCause.top_issues?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                        Top Issues ({rootCause.period_days || 30}d)
                      </p>
                      {rootCause.top_issues.slice(0, 5).map((issue: any, i: number) => (
                        <TopIssueRow key={i} issue={issue} />
                      ))}
                    </div>
                  )}

                  {/* Insights */}
                  {rootCause.insights?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Insights</p>
                      <ul className="space-y-1">
                        {rootCause.insights.slice(0, 3).map((ins: string, i: number) => (
                          <li key={i} className="text-sm text-gray-700 dark:text-gray-300 flex gap-2">
                            <span className="text-indigo-400 mt-0.5">•</span> {ins}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Sentiment trend from pulse */}
                  {pulse?.sentiment_trend && (
                    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Sentiment Trend</p>
                      <div className="flex items-center gap-3">
                        <span className="text-sm dark:text-white">
                          {pulse.sentiment_trend.current_avg?.toFixed(2) ?? "—"}
                        </span>
                        <span className={`text-xs font-medium capitalize ${pulse.sentiment_trend.direction === "worsening" ? "text-red-500" : pulse.sentiment_trend.direction === "improving" ? "text-green-500" : "text-gray-400"}`}>
                          {pulse.sentiment_trend.direction}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Generate digest button */}
                  <div className="pt-2 border-t dark:border-gray-700">
                    {generateError && (
                      <p className="text-sm text-red-500 mb-2">{generateError}</p>
                    )}
                    <Button onClick={handleGenerateArtifact} disabled={generating} className="w-full">
                      {generating
                        ? <><Loader2 className="size-4 mr-2 animate-spin" /> Generating Digest…</>
                        : <><Sparkles className="size-4 mr-2" /> Generate Operational Digest</>}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─── Step 3: Digest generated ─── */}
      {step === 3 && artifactResult && (
        <Card>
          <CardContent className="py-10 text-center space-y-4">
            <CheckCircle2 className="size-12 text-green-500 mx-auto" />
            <div>
              <h2 className="text-lg font-bold dark:text-white">Digest Created</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{artifactResult.artifact_title}</p>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 max-w-sm mx-auto">
              The Weekly Operational Digest is ready for review. Open it in the Artifacts page to approve and deliver it.
            </p>
            <div className="flex gap-3 justify-center">
              <Button asChild>
                <Link to="/app/artifacts">
                  <FileText className="size-4 mr-2" /> View in Artifacts <ArrowRight className="size-4 ml-1" />
                </Link>
              </Button>
              <Button variant="outline" onClick={reset}>
                Upload Another File
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─── Recent uploads ─── */}
      {recentJobs.length > 0 && step === 1 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            Recent Uploads
          </h2>
          <div className="divide-y dark:divide-gray-800 rounded-lg border dark:border-gray-800 overflow-hidden bg-white dark:bg-gray-900">
            {recentJobs.map((j) => (
              <div key={j.id} className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate dark:text-white">{j.filename || "upload"}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {j.data_type} · {j.mapped_rows}/{j.total_rows ?? "?"} rows
                    {j.created_at ? ` · ${new Date(j.created_at).toLocaleDateString()}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <StatusBadge status={j.status} />
                  {j.artifact_id && (
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                    >
                      <Link to="/app/artifacts">
                        <FileText className="size-3.5 mr-1" /> Artifact
                      </Link>
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

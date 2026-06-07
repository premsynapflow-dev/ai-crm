import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import {
  Sparkles,
  Send,
  Clock,
  ChevronRight,
  Loader2,
  MoreHorizontal,
  Share2,
  Pencil,
  FolderOpen,
  Pin,
  Archive,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

interface Message {
  role: "user" | "assistant";
  content: string;
  latency_ms?: number;
}

interface HistoryItem {
  id: string;
  question: string;
  answer: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Local-storage helpers for pin / archive / label (no backend column needed)
// ---------------------------------------------------------------------------

function readLS<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; }
  catch { return fallback; }
}

const STARTER_PROMPTS = [
  "What is our largest source of customer dissatisfaction?",
  "Which operational issue is creating the most churn risk?",
  "What should we fix first to protect revenue?",
  "Why are complaints increasing this week?",
  "Which teams are causing the most escalations?",
  "What product or feature has the most defects?",
];

// ---------------------------------------------------------------------------
// Meatball menu component
// ---------------------------------------------------------------------------

interface MenuProps {
  item: HistoryItem;
  isPinned: boolean;
  onShare: () => void;
  onRename: () => void;
  onMoveToProject: () => void;
  onPin: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onClose: () => void;
}

function ItemMenu({ item, isPinned, onShare, onRename, onMoveToProject, onPin, onArchive, onDelete, onClose }: MenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const row = (icon: React.ReactNode, label: string, action: () => void, danger = false) => (
    <button
      onClick={(e) => { e.stopPropagation(); action(); }}
      className={`flex items-center gap-2.5 w-full px-3 py-2 text-sm rounded-md transition-colors text-left
        ${danger
          ? "text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
          : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"}`}
    >
      {icon}
      {label}
    </button>
  );

  return (
    <div
      ref={ref}
      className="absolute left-full top-0 ml-1 z-50 w-52 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 py-1.5 overflow-hidden"
      onClick={(e) => e.stopPropagation()}
    >
      {row(<Share2 className="size-3.5 shrink-0" />, "Share", onShare)}
      {row(<Pencil className="size-3.5 shrink-0" />, "Rename", onRename)}
      <div className="relative group">
        <button
          onClick={(e) => { e.stopPropagation(); onMoveToProject(); }}
          className="flex items-center gap-2.5 w-full px-3 py-2 text-sm rounded-md text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <FolderOpen className="size-3.5 shrink-0" />
          <span className="flex-1">Move to project</span>
          <ChevronRight className="size-3.5 text-gray-400" />
        </button>
      </div>
      <div className="my-1 h-px bg-gray-100 dark:bg-gray-700" />
      {row(<Pin className="size-3.5 shrink-0" />, isPinned ? "Unpin" : "Pin chat", onPin)}
      {row(<Archive className="size-3.5 shrink-0" />, "Archive", onArchive)}
      <div className="my-1 h-px bg-gray-100 dark:bg-gray-700" />
      {row(<Trash2 className="size-3.5 shrink-0" />, "Delete", onDelete, true)}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function Copilot() {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const autoSentRef = useRef(false);

  // Meatball menu
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  // Rename
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameRef = useRef<HTMLInputElement>(null);

  // Persistent local state
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(
    () => new Set<string>(readLS<string[]>("copilot_pinned", []))
  );
  const [archivedIds, setArchivedIds] = useState<Set<string>>(
    () => new Set<string>(readLS<string[]>("copilot_archived", []))
  );
  const [labels, setLabels] = useState<Record<string, string>>(
    () => readLS<Record<string, string>>("copilot_labels", {})
  );

  useEffect(() => {
    api.copilot.history()
      .then((items) => setHistory(items.slice(0, 30)))
      .catch(() => null)
      .finally(() => setHistoryLoading(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (renamingId) renameRef.current?.focus();
  }, [renamingId]);

  // Auto-send ?q= param from dashboard quick-ask widget
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !autoSentRef.current && !loading) {
      autoSentRef.current = true;
      send(q);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const send = async (question: string) => {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const result = await api.copilot.query(q);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.answer, latency_ms: result.latency_ms },
      ]);
      const newItem: HistoryItem = {
        id: result.id,
        question: q,
        answer: result.answer,
        created_at: new Date().toISOString(),
      };
      setHistory((prev) => [newItem, ...prev.slice(0, 29)]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't process that question. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const loadHistoryItem = (item: HistoryItem) => {
    setMessages([
      { role: "user", content: labels[item.id] || item.question },
      { role: "assistant", content: item.answer },
    ]);
    setMenuOpenId(null);
  };

  // ── Menu actions ──────────────────────────────────────────────────────────

  const handleShare = (item: HistoryItem) => {
    const text = `Q: ${item.question}\n\nA: ${item.answer}`;
    navigator.clipboard.writeText(text).then(
      () => toast.success("Copied to clipboard"),
      () => toast.error("Could not copy to clipboard"),
    );
    setMenuOpenId(null);
  };

  const handleStartRename = (item: HistoryItem) => {
    setRenamingId(item.id);
    setRenameValue(labels[item.id] || item.question);
    setMenuOpenId(null);
  };

  const commitRename = (id: string) => {
    const newVal = renameValue.trim();
    if (newVal) {
      const next = { ...labels, [id]: newVal };
      setLabels(next);
      localStorage.setItem("copilot_labels", JSON.stringify(next));
    }
    setRenamingId(null);
  };

  const handleMoveToProject = () => {
    toast.info("Projects feature coming soon");
    setMenuOpenId(null);
  };

  const handlePin = (id: string) => {
    const next = new Set(pinnedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPinnedIds(next);
    localStorage.setItem("copilot_pinned", JSON.stringify([...next]));
    toast.success(next.has(id) ? "Chat pinned" : "Chat unpinned");
    setMenuOpenId(null);
  };

  const handleArchive = (id: string) => {
    const next = new Set(archivedIds);
    next.add(id);
    setArchivedIds(next);
    localStorage.setItem("copilot_archived", JSON.stringify([...next]));
    toast.success("Conversation archived");
    setMenuOpenId(null);
  };

  const handleDelete = async (id: string) => {
    setMenuOpenId(null);
    try {
      await api.copilot.deleteHistory(id);
      setHistory((prev) => prev.filter((h) => h.id !== id));
      // Also clean up local state
      const nl = { ...labels }; delete nl[id];
      setLabels(nl); localStorage.setItem("copilot_labels", JSON.stringify(nl));
      toast.success("Conversation deleted");
    } catch {
      toast.error("Failed to delete conversation");
    }
  };

  // ── Derived list: pinned first, archived hidden ───────────────────────────

  const visibleHistory = [
    ...history.filter((h) => pinnedIds.has(h.id) && !archivedIds.has(h.id)),
    ...history.filter((h) => !pinnedIds.has(h.id) && !archivedIds.has(h.id)),
  ];

  const archivedCount = history.filter((h) => archivedIds.has(h.id)).length;

  return (
    <div className="flex h-full gap-4">
      {/* Left: Session history */}
      <aside className="w-64 shrink-0 flex flex-col gap-2 min-h-0">
        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-1">
          Recent Questions
        </div>

        {historyLoading ? (
          <div className="text-xs text-gray-400 px-1">Loading…</div>
        ) : visibleHistory.length === 0 ? (
          <div className="text-xs text-gray-400 px-1">No history yet</div>
        ) : (
          <div className="space-y-0.5 overflow-y-auto flex-1">
            {visibleHistory.map((item) => (
              <div
                key={item.id}
                className="relative group"
              >
                {/* Rename mode */}
                {renamingId === item.id ? (
                  <input
                    ref={renameRef}
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => commitRename(item.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename(item.id);
                      if (e.key === "Escape") setRenamingId(null);
                    }}
                    className="w-full px-3 py-2 text-xs rounded-md bg-white dark:bg-gray-800 border border-blue-400 outline-none text-gray-800 dark:text-gray-100"
                  />
                ) : (
                  <button
                    onClick={() => loadHistoryItem(item)}
                    className="w-full text-left px-3 py-2 pr-8 rounded-md text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      {pinnedIds.has(item.id) && (
                        <Pin className="size-2.5 shrink-0 text-blue-500" />
                      )}
                      <span className="line-clamp-2">
                        {labels[item.id] || item.question}
                      </span>
                    </span>
                  </button>
                )}

                {/* Meatball button — visible on hover */}
                {renamingId !== item.id && (
                  <div className="absolute right-1 top-1/2 -translate-y-1/2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpenId(menuOpenId === item.id ? null : item.id);
                      }}
                      className={`p-1 rounded-md transition-colors text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700
                        ${menuOpenId === item.id
                          ? "opacity-100 bg-gray-200 dark:bg-gray-700"
                          : "opacity-0 group-hover:opacity-100"}`}
                      aria-label="More options"
                    >
                      <MoreHorizontal className="size-3.5" />
                    </button>

                    {/* Dropdown menu */}
                    {menuOpenId === item.id && (
                      <ItemMenu
                        item={item}
                        isPinned={pinnedIds.has(item.id)}
                        onShare={() => handleShare(item)}
                        onRename={() => handleStartRename(item)}
                        onMoveToProject={handleMoveToProject}
                        onPin={() => handlePin(item.id)}
                        onArchive={() => handleArchive(item.id)}
                        onDelete={() => handleDelete(item.id)}
                        onClose={() => setMenuOpenId(null)}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Archived count hint */}
        {archivedCount > 0 && (
          <button
            onClick={() => {
              const next = new Set<string>();
              setArchivedIds(next);
              localStorage.setItem("copilot_archived", "[]");
              toast.success("All archived chats restored");
            }}
            className="text-[10px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-1 text-left transition-colors"
          >
            {archivedCount} archived — restore all
          </button>
        )}
      </aside>

      {/* Right: Chat window */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="size-5 text-blue-600" />
          <h1 className="text-lg font-semibold dark:text-white">Operational Copilot</h1>
          <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
            Ask anything about your operational data
          </span>
        </div>

        <Card className="flex-1 flex flex-col min-h-0 dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="flex-1 flex flex-col p-0 min-h-0">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-6 py-12">
                  <div className="flex flex-col items-center gap-2 text-center">
                    <Sparkles className="size-10 text-blue-500 opacity-60" />
                    <p className="text-sm text-gray-500 dark:text-gray-400 max-w-xs">
                      Ask the AI about operational issues, customer churn, product defects, and more.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-2 w-full max-w-md">
                    {STARTER_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => send(prompt)}
                        className="flex items-center gap-2 text-left px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                      >
                        <ChevronRight className="size-3.5 text-blue-500 shrink-0" />
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-sm"
                        : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-sm"
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    {msg.role === "assistant" && msg.latency_ms && (
                      <p className="mt-1.5 text-[10px] text-gray-400 dark:text-gray-500 flex items-center gap-1">
                        <Clock className="size-2.5" />
                        {(msg.latency_ms / 1000).toFixed(1)}s
                      </p>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3">
                    <Loader2 className="size-4 animate-spin text-gray-400" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="border-t dark:border-gray-800 p-3 flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask a question about your complaints… (Enter to send)"
                rows={2}
                className="flex-1 resize-none rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <Button
                size="icon"
                onClick={() => send(input)}
                disabled={loading || !input.trim()}
                className="shrink-0"
              >
                {loading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

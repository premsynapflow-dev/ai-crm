import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { Sparkles, Send, Clock, ChevronRight, Loader2 } from "lucide-react";

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

const STARTER_PROMPTS = [
  "What is our largest source of customer dissatisfaction?",
  "Which operational issue is creating the most churn risk?",
  "What should we fix first to protect revenue?",
  "Why are complaints increasing this week?",
  "Which teams are causing the most escalations?",
  "What product or feature has the most defects?",
];

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

  useEffect(() => {
    api.copilot.history()
      .then((items) => setHistory(items.slice(0, 20)))
      .catch(() => null)
      .finally(() => setHistoryLoading(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
      setHistory((prev) => [
        { id: result.id, question: q, answer: result.answer, created_at: new Date().toISOString() },
        ...prev.slice(0, 19),
      ]);
    } catch (err) {
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
      { role: "user", content: item.question },
      { role: "assistant", content: item.answer },
    ]);
  };

  return (
    <div className="flex h-full gap-4">
      {/* Left: Session history */}
      <aside className="w-64 shrink-0 flex flex-col gap-2">
        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-1">
          Recent Questions
        </div>
        {historyLoading ? (
          <div className="text-xs text-gray-400 px-1">Loading…</div>
        ) : history.length === 0 ? (
          <div className="text-xs text-gray-400 px-1">No history yet</div>
        ) : (
          <div className="space-y-1 overflow-y-auto flex-1">
            {history.map((item) => (
              <button
                key={item.id}
                onClick={() => loadHistoryItem(item)}
                className="w-full text-left px-3 py-2 rounded-md text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors line-clamp-2"
              >
                {item.question}
              </button>
            ))}
          </div>
        )}
      </aside>

      {/* Right: Chat window */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="size-5 text-blue-600" />
          <h1 className="text-lg font-semibold dark:text-white">Executive Copilot</h1>
          <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
            Ask anything about your complaint data
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
                      Ask the AI about complaint trends, customer churn, product issues, and more.
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

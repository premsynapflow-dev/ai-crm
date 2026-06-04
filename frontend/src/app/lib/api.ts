// SynapFlow API client — connects to real backend at /api/v1/
// Auth: Bearer JWT token stored in localStorage after login

export type Plan = "free" | "starter" | "pro" | "max" | "scale" | "enterprise";

export interface User {
  id: string;
  name: string;
  email: string;
  businessType: string;
  companyName: string;
  plan: Plan;
  ticketsUsed: number;
  ticketsQuota: number;
  role: "agent" | "manager" | "supervisor" | "admin";
  apiKey?: string;
}

export interface Complaint {
  id: string;
  ticket_number: string;
  summary: string;
  subject?: string;
  customer_name: string;
  customer_email: string;
  source: "api" | "email" | "gmail" | "whatsapp" | "chat";
  status: "new" | "in-progress" | "escalated" | "resolved";
  state: string;
  priority: 1 | 2 | 3 | 4 | 5;
  sentiment_label: "positive" | "neutral" | "negative";
  sentiment_score: number;
  sentiment_indicators: {
    frustration: number;
    urgency: number;
    confusion: number;
    satisfaction: number;
    aggression: number;
    loyalty: number;
  };
  category: string;
  sla_due_at: string;
  sla_status: "on_track" | "at_risk" | "breached";
  escalation_level: 0 | 1 | 2 | 3;
  assigned_to: string | null;
  team_id: string | null;
  created_at: string;
  resolved_at: string | null;
  ai_reply?: string;
  ai_reply_confidence?: number;
  ai_reply_status?: "pending" | "approved" | "sent" | "rejected" | "discarded";
  rbi_reference?: string;
  rbi_category_code?: string;
  tat_status?: "within_tat" | "approaching_breach" | "breached";
  thread_messages: ThreadMessage[];
}

export interface ThreadMessage {
  id: string;
  content: string;
  direction: "inbound" | "outbound";
  channel: string;
  timestamp: string;
  sender: string;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone?: string;
  company_name?: string;
  customer_type: "individual" | "business";
  total_tickets: number;
  open_tickets: number;
  sentiment_label: "positive" | "neutral" | "negative";
  churn_risk: "low" | "medium" | "high";
  churn_risk_score: number;
  lifetime_value?: number;
  avg_satisfaction_score: number;
  last_interaction_at: string;
  tags?: string[];
}

export interface Agent {
  id: string;
  name: string;
  email: string;
  role: "agent" | "manager" | "supervisor";
  active_tasks: number;
  capacity: number;
  is_active: boolean;
  team_id: string;
}

export interface Team {
  id: string;
  name: string;
  member_count: number;
  members: Agent[];
}

export interface AIReplyDraft {
  id: string;
  complaint_id: string;
  complaint_summary: string;
  customer_name: string;
  customer_email: string;
  reply_text: string;
  confidence: number;
  hallucination_check: "passed" | "failed";
  toxicity_score: number;
  status: "pending" | "approved" | "rejected" | "expired";
  expires_at: string;
  created_at: string;
}

export interface KnowledgeSnippet {
  id: string;
  title: string;
  category: string;
  content: string;
  usage_count: number;
  created_by: string;
  created_at: string;
}

export interface AutomationRule {
  id: string;
  name: string;
  trigger: string;
  conditions: Array<{ field: string; operator: string; value: string }>;
  actions: Array<{ type: string; params: Record<string, unknown> }>;
  enabled: boolean;
  last_triggered?: string;
  created_at: string;
}

// ── Auth helpers ─────────────────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem("synapflow_token");
}

function getApiKey(): string | null {
  return localStorage.getItem("synapflow_api_key");
}

function authHeaders(overrides?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...overrides,
  };
  const token = getToken();
  if (token && !headers["Authorization"]) headers["Authorization"] = `Bearer ${token}`;
  const apiKey = getApiKey();
  if (apiKey && !headers["x-api-key"]) headers["x-api-key"] = apiKey;
  return headers;
}

async function request<T>(
  path: string,
  options: RequestInit & { headers?: Record<string, string> } = {}
): Promise<T> {
  const { headers: extraHeaders, ...rest } = options;
  const res = await fetch(path, {
    ...rest,
    headers: authHeaders(extraHeaders),
  });

  if (res.status === 401) {
    // Session expired or invalid — clear stored credentials and redirect to login
    localStorage.removeItem("synapflow_token");
    localStorage.removeItem("synapflow_user");
    localStorage.removeItem("synapflow_api_key");
    if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/signup")) {
      window.location.href = "/login";
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.detail === "object") detail = body.detail?.message || JSON.stringify(body.detail);
      else if (body.message) detail = body.message;
    } catch {
      // ignore
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Shape normalizers ─────────────────────────────────────────────────────────

function normalizePriority(p: string | number | null | undefined): 1 | 2 | 3 | 4 | 5 {
  if (typeof p === "number") return Math.max(1, Math.min(5, p)) as 1 | 2 | 3 | 4 | 5;
  switch (String(p).toLowerCase()) {
    case "critical": return 5;
    case "high": return 4;
    case "medium": return 3;
    case "low": return 2;
    default: return 1;
  }
}

function normalizeComplaint(raw: Record<string, unknown>): Complaint {
  const rawInd = raw.sentiment_indicators;
  const indicators = (rawInd && !Array.isArray(rawInd) && typeof rawInd === "object" ? rawInd : {}) as Record<string, number>;
  return {
    id: String(raw.id),
    ticket_number: String(raw.ticket_number || raw.ticket_id || raw.id || ""),
    summary: String(raw.subject || raw.complaint_text || raw.summary || ""),
    customer_name: String(raw.customer_name || ""),
    customer_email: String(raw.customer_email || ""),
    source: (raw.source as Complaint["source"]) || "api",
    status: (raw.status as Complaint["status"]) || "new",
    state: String(raw.state || "new"),
    priority: normalizePriority(raw.priority),
    sentiment_label: (raw.sentiment_label || raw.sentiment || "neutral") as Complaint["sentiment_label"],
    sentiment_score: Number(raw.sentiment_score ?? raw.sentiment ?? 0),
    sentiment_indicators: {
      frustration: Number(indicators.frustration ?? 0),
      urgency: Number(indicators.urgency ?? 0),
      confusion: Number(indicators.confusion ?? 0),
      satisfaction: Number(indicators.satisfaction ?? 0),
      aggression: Number(indicators.aggression ?? 0),
      loyalty: Number(indicators.loyalty ?? 0),
    },
    category: String(raw.category || ""),
    sla_due_at: String(raw.sla_due_at || new Date(Date.now() + 24 * 3600000).toISOString()),
    sla_status: (raw.sla_status as Complaint["sla_status"]) || "on_track",
    escalation_level: (Number(raw.escalation_level) || 0) as 0 | 1 | 2 | 3,
    assigned_to: (raw.assigned_to as string) || null,
    team_id: raw.team_id ? String(raw.team_id) : null,
    created_at: String(raw.created_at || new Date().toISOString()),
    resolved_at: raw.resolved_at ? String(raw.resolved_at) : null,
    ai_reply: raw.ai_reply ? String(raw.ai_reply) : undefined,
    ai_reply_confidence: raw.ai_confidence != null ? Number(raw.ai_confidence) / 100 : undefined,
    ai_reply_status: raw.ai_reply_status as Complaint["ai_reply_status"],
    rbi_reference: raw.rbi_reference ? String(raw.rbi_reference) : undefined,
    rbi_category_code: raw.rbi_category_code ? String(raw.rbi_category_code) : undefined,
    tat_status: raw.tat_status as Complaint["tat_status"],
    thread_messages: Array.isArray(raw.thread_messages)
      ? (raw.thread_messages as Array<Record<string, unknown>>).map(normalizeMessage)
      : [],
  };
}

function normalizeMessage(raw: Record<string, unknown>): ThreadMessage {
  return {
    id: String(raw.id || Math.random()),
    content: String(raw.message_text || raw.body || raw.content || raw.text || ""),
    direction: (raw.direction as ThreadMessage["direction"]) || "inbound",
    channel: String(raw.channel || "email"),
    timestamp: String(raw.timestamp || raw.created_at || new Date().toISOString()),
    sender: String(raw.sender_name || raw.sender || raw.from_email || ""),
  };
}

function normalizeCustomer(raw: Record<string, unknown>): Customer {
  return {
    id: String(raw.id),
    name: String(raw.name || raw.full_name || ""),
    email: String(raw.primary_email || raw.email || ""),
    phone: raw.primary_phone ? String(raw.primary_phone) : undefined,
    company_name: raw.company_name ? String(raw.company_name) : undefined,
    customer_type: (raw.customer_type as Customer["customer_type"]) || "individual",
    total_tickets: Number(raw.total_tickets || 0),
    open_tickets: Number(raw.open_tickets || 0),
    sentiment_label: (raw.sentiment_label as Customer["sentiment_label"]) || "neutral",
    churn_risk: (raw.churn_risk as Customer["churn_risk"]) || "low",
    churn_risk_score: Number(raw.churn_risk_score || 0),
    lifetime_value: raw.lifetime_value != null ? Number(raw.lifetime_value) : undefined,
    avg_satisfaction_score: Number(raw.avg_satisfaction_score || 0),
    last_interaction_at: String(
      raw.last_interaction_at || raw.last_contacted_at || new Date().toISOString()
    ),
    tags: Array.isArray(raw.tags) ? (raw.tags as string[]) : [],
  };
}

function normalizeAutomation(raw: Record<string, unknown>): AutomationRule {
  const trigger = (raw.trigger as Record<string, unknown>) || {};
  const conditions = (raw.conditions as Array<Record<string, unknown>>) || [];
  const actions = (raw.actions as Array<Record<string, unknown>>) || [];

  return {
    id: String(raw.id),
    name: String(raw.workflow_name || raw.name || "Untitled rule"),
    trigger: String(trigger.type || raw.trigger_type || "complaint.created"),
    conditions: conditions.map((c) => ({
      field: String(c.field || ""),
      operator: String(c.operator || "equals"),
      value: String(c.value || ""),
    })),
    actions: actions.map((a) => ({
      type: String(a.type || ""),
      params: (a.config as Record<string, unknown>) || (a.params as Record<string, unknown>) || {},
    })),
    enabled: Boolean(raw.enabled),
    last_triggered: raw.last_triggered ? String(raw.last_triggered) : undefined,
    created_at: String(raw.created_at || new Date().toISOString()),
  };
}

function serializeAutomation(data: Partial<AutomationRule>): Record<string, unknown> {
  return {
    workflow_name: data.name,
    trigger: { type: data.trigger },
    conditions: (data.conditions || []).map((c) => ({
      field: c.field,
      operator: c.operator,
      value: c.value,
    })),
    actions: (data.actions || []).map((a) => ({
      type: a.type,
      config: a.params || {},
    })),
    enabled: data.enabled !== false,
  };
}

// ── API ───────────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    login: async (email: string, password: string): Promise<{ token: string; user: User }> => {
      const data = await request<{ access_token: string }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
        headers: { "Content-Type": "application/json" },
      });
      const token = data.access_token;
      localStorage.setItem("synapflow_token", token);

      const settingsData = await request<{
        profile: { id: string; email: string; name: string; plan: string; business_sector: string; company: string };
        company: { name: string; monthly_ticket_limit: number; plan_id: string };
        api_key: string;
      }>("/api/settings", { headers: { Authorization: `Bearer ${token}` } });

      localStorage.setItem("synapflow_api_key", settingsData.api_key);

      const profile = settingsData.profile;
      const company = settingsData.company;
      const user: User = {
        id: profile.id,
        name: profile.name || email.split("@")[0],
        email: profile.email,
        businessType: profile.business_sector || "",
        companyName: company.name || profile.company || "",
        plan: ((company.plan_id || profile.plan || "free") as Plan),
        ticketsUsed: 0,
        ticketsQuota: company.monthly_ticket_limit || 50,
        role: "manager",
        apiKey: settingsData.api_key,
      };
      return { token, user };
    },

    signup: async (data: {
      name: string;
      email: string;
      password: string;
      businessType: string;
      phone?: string;
    }): Promise<{ token: string; user: User }> => {
      await request("/api/signup", {
        method: "POST",
        body: JSON.stringify({
          company_name: data.name,
          email: data.email,
          password: data.password,
          phone_number: data.phone || "0000000000",
          business_sector: data.businessType,
        }),
        headers: { "Content-Type": "application/json" },
      });
      return api.auth.login(data.email, data.password);
    },

    forgotPassword: async (email: string): Promise<void> => {
      await request("/api/v1/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
        headers: { "Content-Type": "application/json" },
      });
    },

    verifyOTP: async (_email: string, _otp: string): Promise<void> => {
      // OTP verified inline during resetPassword
    },

    resetPassword: async (email: string, otp: string, password: string): Promise<void> => {
      await request("/api/v1/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ email, otp, new_password: password }),
        headers: { "Content-Type": "application/json" },
      });
    },
  },

  complaints: {
    list: async (filters?: {
      status?: string;
      priority?: string;
      search?: string;
      sla?: string;
      page?: number;
    }): Promise<Complaint[]> => {
      const params = new URLSearchParams({ page_size: "100" });
      if (filters?.status && filters.status !== "all") params.set("status", filters.status);
      if (filters?.priority && filters.priority !== "all") params.set("priority", filters.priority);
      if (filters?.search) params.set("search", filters.search);
      if (filters?.page) params.set("page", String(filters.page));

      const data = await request<{ items?: unknown[]; complaints?: unknown[] }>(
        `/api/v1/complaints?${params}`
      );
      const items = data.items || data.complaints || [];
      return (items as Array<Record<string, unknown>>).map(normalizeComplaint);
    },

    get: async (id: string): Promise<Complaint | null> => {
      try {
        const data = await request<Record<string, unknown>>(`/api/v1/complaints/${id}`);
        return normalizeComplaint(data);
      } catch {
        return null;
      }
    },

    update: async (id: string, data: Partial<Complaint>): Promise<Complaint> => {
      const raw = await request<Record<string, unknown>>(`/api/v1/complaints/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      return normalizeComplaint(raw);
    },

    sendReply: async (id: string, replyText: string): Promise<void> => {
      await request(`/api/v1/complaints/${id}/reply`, {
        method: "POST",
        body: JSON.stringify({ reply_text: replyText }),
      });
    },

    setStatus: async (id: string, status: "escalated" | "resolved" | "in-progress" | "new"): Promise<void> => {
      await request(`/api/v1/complaints/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
    },

    assign: async (id: string, teamId: string | null, agentId: string | null): Promise<void> => {
      await request(`/api/v1/tickets/${id}/assign`, {
        method: "POST",
        body: JSON.stringify({ team_id: teamId, assigned_to: agentId }),
      });
    },

    delete: async (id: string): Promise<void> => {
      await request(`/api/v1/complaints/${id}`, { method: "DELETE" });
    },

    generateReply: async (id: string): Promise<Complaint> => {
      const raw = await request<Record<string, unknown>>(`/api/v1/complaints/${id}/generate-reply`, {
        method: "POST",
      });
      return normalizeComplaint(raw);
    },
  },

  replyQueue: {
    list: async (status = "pending"): Promise<AIReplyDraft[]> => {
      const data = await request<{ items: Array<Record<string, unknown>> }>(
        `/api/v1/reply-queue?status=${status}`
      );
      return (data.items || []).map((item) => ({
        id: String(item.id),
        complaint_id: String(item.ticket_id || item.complaint_id || ""),
        complaint_summary: String(item.ticket_summary || item.complaint_summary || ""),
        customer_name: String(item.customer_name || ""),
        customer_email: String(item.customer_email || ""),
        reply_text: String(item.draft_body || item.edited_reply || item.generated_reply || ""),
        confidence: Number(item.confidence_score || 0),
        hallucination_check: item.hallucination_check_passed ? "passed" : ("failed" as "passed" | "failed"),
        toxicity_score: Number(item.toxicity_score || 0),
        status: (item.status as AIReplyDraft["status"]) || "pending",
        expires_at: String(item.expires_at || new Date(Date.now() + 86400000).toISOString()),
        created_at: String(item.created_at || new Date().toISOString()),
      }));
    },

    approve: async (id: string, editedText?: string): Promise<void> => {
      await request(`/api/v1/reply-queue/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ edited_reply: editedText }),
      });
    },

    reject: async (id: string, reason?: string): Promise<void> => {
      await request(`/api/v1/reply-queue/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: reason || "Rejected by agent" }),
      });
    },
  },

  customers: {
    list: async (filters?: { search?: string }): Promise<Customer[]> => {
      const params = new URLSearchParams({ limit: "100" });
      if (filters?.search) params.set("search", filters.search);
      const data = await request<{ items: Array<Record<string, unknown>> }>(
        `/api/v1/customers?${params}`
      );
      return (data.items || []).map(normalizeCustomer);
    },

    get: async (id: string): Promise<Customer | null> => {
      try {
        const data = await request<Record<string, unknown>>(`/api/v1/customers/${id}/360`);
        const raw = ((data as { customer?: Record<string, unknown> }).customer || data) as Record<string, unknown>;
        return normalizeCustomer(raw);
      } catch {
        return null;
      }
    },

    getSaveRecommendations: async (id: string): Promise<{
      customer_id: string;
      churn_risk: string;
      churn_risk_score: number;
      recommendations: string[];
    } | null> => {
      try {
        return await request(`/api/v1/customers/${id}/save-recommendations`);
      } catch {
        return null;
      }
    },
  },

  agents: {
    list: async (): Promise<Agent[]> => {
      const data = await request<{
        teams: Array<{
          id: string;
          members: Array<{
            id: string;
            email: string;
            name: string;
            role: string;
            active_tasks: number;
            capacity: number;
            is_active: boolean;
          }>;
        }>;
      }>("/api/v1/dashboard/assignments");

      const agents: Agent[] = [];
      for (const team of data.teams || []) {
        for (const member of team.members || []) {
          agents.push({
            id: member.id,
            name: member.name || member.email,
            email: member.email,
            role: (member.role as Agent["role"]) || "agent",
            active_tasks: member.active_tasks || 0,
            capacity: member.capacity || 10,
            is_active: member.is_active !== false,
            team_id: team.id,
          });
        }
      }
      return agents;
    },
  },

  dashboard: {
    stats: async () => {
      type OverviewResp = {
        total_complaints: number;
        resolved_today: number;
        customer_satisfaction: number;
        category_breakdown: Array<{ category: string; count: number }>;
        priority_breakdown?: Array<{ priority: string; count: number }>;
      };
      type ComplaintsResp = {
        items: Array<{ sla_status?: string; status?: string; resolved_at?: string | null; created_at?: string }>;
      };
      type QueueResp = { items: unknown[] };

      const [overview, replyQueue, complaints] = await Promise.all([
        request<OverviewResp>("/api/analytics/overview"),
        request<QueueResp>("/api/v1/reply-queue?status=pending"),
        request<ComplaintsResp>("/api/v1/complaints?page_size=200"),
      ]);

      const items = complaints.items || [];
      const openTickets = items.filter((c) => c.status !== "resolved").length;
      const now = new Date();
      const resolvedThisMonth = items.filter((c) => {
        if (!c.resolved_at) return false;
        const d = new Date(c.resolved_at);
        return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
      }).length;
      const slaBreached = items.filter((c) => c.sla_status === "breached").length;

      const categoryDist: Record<string, number> = {};
      for (const cat of overview.category_breakdown || []) {
        if (cat.category) categoryDist[cat.category] = cat.count;
      }

      const priorityMap = { critical: 0, high: 0, medium: 0, low: 0 };
      for (const p of overview.priority_breakdown || []) {
        const key = String(p.priority || "").toLowerCase() as keyof typeof priorityMap;
        if (key in priorityMap) priorityMap[key] = p.count;
      }

      const volMap: Record<string, number> = {};
      for (const c of items) {
        if (c.created_at) {
          const d = new Date(c.created_at).toISOString().slice(0, 10);
          volMap[d] = (volMap[d] || 0) + 1;
        }
      }
      const volumeDays = Array.from({ length: 14 }, (_, i) => {
        const d = new Date(Date.now() - (13 - i) * 86400000).toISOString().slice(0, 10);
        return volMap[d] || 0;
      });

      const csat = Number(overview.customer_satisfaction || 0);
      const csatNorm = csat > 1 ? csat : csat * 5;

      return {
        total_tickets: overview.total_complaints || 0,
        total_tickets_month: items.length,
        open_tickets: openTickets,
        resolved_tickets_month: resolvedThisMonth,
        csat_avg: csatNorm,
        csat_trend: Array(7).fill(csatNorm) as number[],
        ticket_volume: volumeDays,
        priority_breakdown: priorityMap,
        category_distribution: categoryDist,
        ai_queue_size: (replyQueue.items || []).length,
        sla_breached: slaBreached,
      };
    },
  },

  knowledge: {
    list: async (): Promise<KnowledgeSnippet[]> => {
      const data = await request<{ items: Array<Record<string, unknown>> }>("/api/v1/knowledge");
      return (data.items || []).map((item) => ({
        id: String(item.id),
        title: String(item.title || ""),
        category: String(item.category || "General"),
        content: String(item.content || ""),
        usage_count: Number(item.usage_count || 0),
        created_by: String(item.created_by || ""),
        created_at: String(item.created_at || new Date().toISOString()),
      }));
    },

    create: async (data: { title: string; category: string; content: string }): Promise<KnowledgeSnippet> => {
      const res = await request<{ item: Record<string, unknown> }>("/api/v1/knowledge", {
        method: "POST",
        body: JSON.stringify({ title: data.title, content: data.content, category: data.category }),
      });
      const item = res.item;
      return {
        id: String(item.id),
        title: String(item.title || data.title),
        category: String(item.category || data.category),
        content: String(item.content || data.content),
        usage_count: 0,
        created_by: String(item.created_by || ""),
        created_at: String(item.created_at || new Date().toISOString()),
      };
    },

    update: async (id: string, data: Partial<KnowledgeSnippet>): Promise<KnowledgeSnippet> => {
      const res = await request<{ item: Record<string, unknown> }>(`/api/v1/knowledge/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      const item = res.item || {};
      return {
        id: String(item.id || id),
        title: String(item.title || data.title || ""),
        category: String(item.category || data.category || ""),
        content: String(item.content || data.content || ""),
        usage_count: Number(item.usage_count || 0),
        created_by: String(item.created_by || ""),
        created_at: String(item.created_at || new Date().toISOString()),
      };
    },

    delete: async (id: string): Promise<void> => {
      await request(`/api/v1/knowledge/${id}`, { method: "DELETE" });
    },
  },

  automations: {
    list: async (): Promise<AutomationRule[]> => {
      const data = await request<{ items: Array<Record<string, unknown>> }>("/api/v1/workflows");
      return (data.items || []).map(normalizeAutomation);
    },

    create: async (data: Omit<AutomationRule, "id" | "created_at">): Promise<AutomationRule> => {
      const res = await request<{ item: Record<string, unknown> }>("/api/v1/workflows", {
        method: "POST",
        body: JSON.stringify(serializeAutomation(data)),
      });
      return normalizeAutomation(res.item);
    },

    update: async (id: string, data: Partial<AutomationRule>): Promise<AutomationRule> => {
      const res = await request<{ item: Record<string, unknown> }>(`/api/v1/workflows/${id}`, {
        method: "PATCH",
        body: JSON.stringify(serializeAutomation(data)),
      });
      return normalizeAutomation(res.item);
    },

    delete: async (id: string): Promise<void> => {
      await request(`/api/v1/workflows/${id}`, { method: "DELETE" });
    },

    toggle: async (id: string): Promise<AutomationRule> => {
      const res = await request<{ item: Record<string, unknown> }>(`/api/v1/workflows/${id}/toggle`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      return normalizeAutomation(res.item);
    },
  },

  channels: {
    list: async (type?: string) => {
      const url = type ? `/api/v1/channel-connections?type=${type}` : "/api/v1/channel-connections";
      const raw = await request<Array<{
        id: string;
        channel_type: string;
        account_identifier: string | null;
        status: string;
        metadata: Record<string, unknown>;
        created_at: string | null;
      }>>(url);
      return Array.isArray(raw) ? raw : [];
    },

    connectWhatsApp: async (payload: {
      phone_number_id: string;
      access_token: string;
      business_account_id?: string;
      verify_token?: string;
    }) => {
      return request<{ status: string; connection_id: string; account_identifier: string }>(
        "/integrations/whatsapp/connect",
        { method: "POST", body: JSON.stringify(payload) }
      );
    },

    connect: async (payload: {
      channel_type: string;
      account_identifier?: string;
      credentials?: Record<string, unknown>;
      metadata?: Record<string, unknown>;
    }) => {
      return request<{ id: string; channel_type: string; account_identifier: string | null; status: string }>(
        "/api/v1/channel-connections",
        { method: "POST", body: JSON.stringify(payload) }
      );
    },

    disconnect: async (id: string) => {
      const token = localStorage.getItem("synapflow_token");
      const apiKey = localStorage.getItem("synapflow_api_key");
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (apiKey) headers["x-api-key"] = apiKey;
      const res = await fetch(`/api/v1/channel-connections/${id}`, { method: "DELETE", headers });
      if (!res.ok && res.status !== 204) throw new Error("Failed to disconnect");
    },
  },

  inboxes: {
    poll: async (inboxId: string) => {
      return request<{
        diagnostics: Record<string, unknown>;
        result: { fetched: number; processed: number; duplicates: number; errors: number } | null;
        error?: string;
      }>(`/inboxes/${inboxId}/poll`, { method: "POST" });
    },
    list: async () => {
      const raw = await request<Array<{ id: string; email: string; provider: string; status: string }>>("/inboxes");
      return Array.isArray(raw) ? raw : [];
    },

    getGmailConnectUrl: async () => {
      return request<{ connect_url: string }>("/inboxes/gmail/connect-url");
    },

    connectImap: async (payload: {
      email: string;
      password: string;
      host?: string;
      port?: number;
      use_ssl?: boolean;
    }) => {
      return request<{ id: string; email: string; provider: string; status: string }>("/inboxes/connect-imap", {
        method: "POST",
        body: JSON.stringify({
          email: payload.email,
          password: payload.password,
          imap_host: payload.host,
          imap_port: payload.port ?? 993,
          use_ssl: payload.use_ssl ?? true,
        }),
      });
    },

    disconnect: async (inboxId: string) => {
      const token = localStorage.getItem("synapflow_token");
      const apiKey = localStorage.getItem("synapflow_api_key");
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (apiKey) headers["x-api-key"] = apiKey;
      const res = await fetch(`/inboxes/${inboxId}`, { method: "DELETE", headers });
      if (!res.ok && res.status !== 204) throw new Error("Failed to disconnect");
    },
  },

  settings: {
    get: async () => {
      return request<{
        profile: Record<string, unknown>;
        company: Record<string, unknown>;
        api_key: string;
        webhooks: unknown[];
        channels: Record<string, unknown>;
        notification_preferences: Record<string, unknown>;
      }>("/api/settings");
    },

    updateSlack: async (slackWebhookUrl: string): Promise<void> => {
      await request("/api/settings/webhooks/slack", {
        method: "PUT",
        body: JSON.stringify({ slack_webhook_url: slackWebhookUrl }),
      });
    },

    testSlack: async (slackWebhookUrl?: string): Promise<void> => {
      await request("/api/settings/webhooks/slack/test", {
        method: "POST",
        body: JSON.stringify({ slack_webhook_url: slackWebhookUrl }),
      });
    },

    updateNotificationPrefs: async (prefs: {
      sla_breach: boolean;
      new_escalation: boolean;
      daily_digest: boolean;
      ticket_assigned: boolean;
      ai_draft_expired: boolean;
      auto_ai_reply: boolean;
    }): Promise<void> => {
      await request("/api/settings/notifications", {
        method: "PUT",
        body: JSON.stringify(prefs),
      });
    },
  },

  billing: {
    getUsage: async () => {
      return request<{
        plan_id: string;
        current_usage: number;
        monthly_limit: number;
        tickets_processed: number;
        period_end?: string;
        next_billing_date?: string;
      }>("/api/usage");
    },

    getInvoices: async () => {
      const raw = await request<Array<{
        id: string;
        invoice_number: string;
        status: string;
        total: number;
        subtotal: number;
        tax: number;
        invoice_date: string | null;
        paid_at: string | null;
        payment_method: string | null;
        plan: string;
      }>>("/api/invoices");
      return Array.isArray(raw) ? raw : [];
    },

    downloadInvoice: async (invoiceId: string): Promise<Blob> => {
      const token = localStorage.getItem("synapflow_token");
      const apiKey = localStorage.getItem("synapflow_api_key");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (apiKey) headers["x-api-key"] = apiKey;
      const res = await fetch(`/api/invoices/${invoiceId}/download`, { headers });
      if (!res.ok) throw new Error("Failed to download invoice");
      return res.blob();
    },

    upgrade: async (planId: string, billingCycle: "monthly" | "annual" = "monthly") => {
      return request<{
        ok: boolean;
        status: "upgraded" | "payment_pending";
        plan_id: string;
        plan_name?: string;
        payment_url: string | null;
        plan_applied: boolean;
        checkout_mode?: "order";
        order_id?: string;
        razorpay_key?: string;
        amount?: number;
        currency?: string;
        billing_cycle?: string;
      }>("/api/upgrade", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle }),
      });
    },

    verifyPayment: async (data: {
      order_id: string;
      payment_id: string;
      signature: string;
      plan_id: string;
      billing_cycle: string;
    }) => {
      return request<{ ok: boolean; status: string; plan_id: string; plan_name: string }>("/api/verify-payment", {
        method: "POST",
        body: JSON.stringify(data),
      });
    },

    verifyPaymentLink: async (data: {
      razorpay_payment_id: string;
      razorpay_payment_link_id: string;
      razorpay_payment_link_reference_id: string;
      razorpay_payment_link_status: string;
      razorpay_signature: string;
      plan_id: string;
      billing_cycle: string;
    }) => {
      return request<{ ok: boolean; status: string; plan_id: string; plan_name: string }>("/api/verify-payment-link", {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
  },

  copilot: {
    query: async (question: string, days = 30): Promise<{
      id: string;
      answer: string;
      sources: Record<string, unknown>;
      latency_ms: number;
    }> => {
      return request("/api/v1/copilot/query", {
        method: "POST",
        body: JSON.stringify({ question, days }),
      });
    },

    history: async (): Promise<Array<{ id: string; question: string; answer: string; latency_ms: number; created_at: string }>> => {
      const data = await request<{ queries: Array<{ id: string; question: string; answer: string; latency_ms: number; created_at: string }> }>("/api/v1/copilot/history");
      return data.queries || [];
    },
  },

  intelligence: {
    pulse: async (): Promise<{
      top_issues: Array<{ category: string; count: number }>;
      sentiment_trend: { current_avg: number; previous_avg: number; direction: string };
      churn_risk_customers: Array<{ customer_email: string; complaint_count: number; avg_sentiment: number }>;
      new_complaint_spikes: Array<{ type: string; severity: string; hour_count?: number; avg_sentiment?: number }>;
      suggested_actions: string[];
    }> => {
      return request("/api/v1/intelligence/pulse");
    },

    operations: async (): Promise<{
      spikes: Array<{ type: string; severity: string }>;
      defect_signals: Array<{ category: string; complaint_count: number; sample_messages: string[] }>;
      top_themes: Array<{ theme: string; count: number; pct: number }>;
      period_days: number;
      total_complaints: number;
    }> => {
      return request("/api/v1/intelligence/operations");
    },

    clusters: async (days = 30): Promise<Array<{
      id: string;
      cluster_label: string;
      size: number;
      summary: string;
      top_category: string;
      period_start: string;
      period_end: string;
    }>> => {
      const data = await request<{ clusters: unknown[] }>(`/api/v1/clusters?days=${days}`);
      return (data.clusters || []) as Array<{ id: string; cluster_label: string; size: number; summary: string; top_category: string; period_start: string; period_end: string }>;
    },

    acknowledgeCluster: async (clusterId: string, action: string, note: string): Promise<void> => {
      await request(`/api/v1/intelligence/clusters/${clusterId}/acknowledge`, {
        method: "POST",
        body: JSON.stringify({ action, note }),
      });
    },

    forecast: async (): Promise<Record<string, unknown>> => {
      return request("/api/v1/forecasting/forecast");
    },

    revenueRisk: async (): Promise<{
      total_revenue_at_risk: number;
      high_risk_customers: Array<{ customer_email: string; revenue_at_risk: number; churn_probability: number }>;
    }> => {
      return request("/api/v1/revenue-risk");
    },
  },

  admin: {
    getOverview: async (adminPassword: string) => {
      return request("/admin/dashboard/overview", {
        headers: { Authorization: `Bearer ${adminPassword}` },
      });
    },

    getTenants: async (adminPassword: string) => {
      return request<{ items: unknown[] }>("/admin/tenants", {
        headers: { Authorization: `Bearer ${adminPassword}` },
      });
    },
  },

  teams: {
    list: async (): Promise<Team[]> => {
      try {
        const data = await request<{ teams: Array<{ id: string; name: string; member_count: number }> }>(
          "/api/v1/teams"
        );
        const result: Team[] = [];
        for (const t of data.teams || []) {
          let members: Agent[] = [];
          try {
            const md = await request<{ members: Array<Record<string, unknown>> }>(
              `/api/v1/teams/${t.id}/members`
            );
            members = (md.members || []).map((m) => ({
              id: String(m.id || m.user_id || ""),
              name: String(m.name || m.email || ""),
              email: String(m.email || ""),
              role: (m.role as Agent["role"]) || "agent",
              active_tasks: Number(m.active_tasks || 0),
              capacity: Number(m.capacity || 10),
              is_active: m.is_active !== false,
              team_id: t.id,
            }));
          } catch { /* members unavailable */ }
          result.push({ id: t.id, name: t.name, member_count: t.member_count || members.length, members });
        }
        return result;
      } catch {
        return [];
      }
    },
    listRaw: async () => {
      return request<{ items: Array<{
        id: string; name: string; member_count: number; active_tasks: number;
        routing_categories: string[]; created_at: string | null;
      }> }>("/api/v1/teams");
    },
    create: async (name: string) => {
      return request<{ team: { id: string; name: string } }>("/api/v1/teams", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
    },
    delete: async (teamId: string) => {
      await request(`/api/v1/teams/${teamId}`, { method: "DELETE" });
    },
    getMembers: async (teamId: string) => {
      return request<{ team: unknown; items: Array<{
        id: string; team_id: string; user_id: string; name: string; email: string;
        role: string; capacity: number; active_tasks: number; is_active: boolean;
      }> }>(`/api/v1/teams/${teamId}/members`);
    },
    addMember: async (teamId: string, data: { user_id: string; role: string; capacity: number }) => {
      return request(`/api/v1/teams/${teamId}/members`, {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    removeMember: async (memberId: string) => {
      await request(`/api/v1/team-members/${memberId}`, { method: "DELETE" });
    },
    updateMember: async (memberId: string, data: { role?: string; capacity?: number; is_active?: boolean }) => {
      return request(`/api/v1/team-members/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    },
    getRoutingRules: async (teamId: string) => {
      return request<{ items: Array<{ id: string; category: string; team_id: string }> }>(
        `/api/v1/teams/${teamId}/routing-rules`
      );
    },
    addRoutingRule: async (teamId: string, category: string) => {
      return request(`/api/v1/teams/${teamId}/routing-rules`, {
        method: "POST",
        body: JSON.stringify({ category }),
      });
    },
    deleteRoutingRule: async (ruleId: string) => {
      await request(`/api/v1/routing-rules/${ruleId}`, { method: "DELETE" });
    },
  },

  users: {
    list: async () => {
      return request<{ items: Array<{ id: string; email: string; name: string; role: string }> }>("/api/v1/users");
    },
  },

  rbi: {
    list: async () => {
      return request<{ items: unknown[] }>("/api/v1/rbi-compliance/assignments");
    },
    getMisReport: async (year: number, month: number) => {
      return request(`/api/v1/rbi-compliance/mis-report/${year}/${month}`);
    },
  },

  notifications: {
    list: async () => {
      return request<{ items: unknown[] }>("/api/v1/notifications");
    },
    markRead: async (id: string) => {
      return request(`/api/v1/notifications/${id}/read`, {
        method: "POST",
        body: "{}",
      });
    },
  },
};

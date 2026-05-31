import api from '../api'

export interface WorkflowTrigger {
  type: string
  value?: string
  [key: string]: unknown
}

export interface WorkflowCondition {
  field: string
  operator: string
  value: string | number | boolean
}

export interface WorkflowAction {
  type: string
  config?: Record<string, unknown>
}

export interface WorkflowRule {
  id: string
  workflowName: string
  trigger: WorkflowTrigger
  conditions: WorkflowCondition[]
  actions: WorkflowAction[]
  enabled: boolean
  createdAt: string
}

export interface WorkflowExecution {
  id: string
  automationRuleId: string | null
  complaintId: string | null
  customerId: string | null
  actionType: string
  executionStatus: string
  retryCount: number
  errorMessage: string | null
  startedAt: string | null
  completedAt: string | null
  failedAt: string | null
  executedAt: string | null
}

export interface CreateWorkflowPayload {
  workflow_name?: string
  trigger: WorkflowTrigger
  conditions: WorkflowCondition[]
  actions: WorkflowAction[]
  enabled?: boolean
}

function normalizeRule(raw: Record<string, unknown>): WorkflowRule {
  return {
    id: raw.id as string,
    workflowName: (raw.workflow_name ?? 'Untitled Workflow') as string,
    trigger: (raw.trigger ?? {}) as WorkflowTrigger,
    conditions: (raw.conditions ?? []) as WorkflowCondition[],
    actions: (raw.actions ?? []) as WorkflowAction[],
    enabled: Boolean(raw.enabled),
    createdAt: (raw.created_at ?? '') as string,
  }
}

function normalizeExecution(raw: Record<string, unknown>): WorkflowExecution {
  return {
    id: raw.id as string,
    automationRuleId: (raw.automation_rule_id ?? null) as string | null,
    complaintId: (raw.complaint_id ?? null) as string | null,
    customerId: (raw.customer_id ?? null) as string | null,
    actionType: (raw.action_type ?? '') as string,
    executionStatus: (raw.execution_status ?? '') as string,
    retryCount: (raw.retry_count ?? 0) as number,
    errorMessage: (raw.error_message ?? null) as string | null,
    startedAt: (raw.started_at ?? null) as string | null,
    completedAt: (raw.completed_at ?? null) as string | null,
    failedAt: (raw.failed_at ?? null) as string | null,
    executedAt: (raw.executed_at ?? null) as string | null,
  }
}

export const workflowsAPI = {
  list: async (): Promise<WorkflowRule[]> => {
    const res = await api.get('/api/v1/workflows')
    return (res.data?.items ?? []).map(normalizeRule)
  },

  create: async (payload: CreateWorkflowPayload): Promise<WorkflowRule> => {
    const res = await api.post('/api/v1/workflows', payload)
    return normalizeRule(res.data.item)
  },

  update: async (id: string, payload: CreateWorkflowPayload): Promise<WorkflowRule> => {
    const res = await api.patch(`/api/v1/workflows/${id}`, payload)
    return normalizeRule(res.data.item)
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/workflows/${id}`)
  },

  toggle: async (id: string): Promise<WorkflowRule> => {
    const res = await api.post(`/api/v1/workflows/${id}/toggle`)
    return normalizeRule(res.data.item)
  },

  listExecutions: async (limit = 50): Promise<WorkflowExecution[]> => {
    const res = await api.get('/api/v1/workflows/executions', { params: { limit } })
    return (res.data?.items ?? []).map(normalizeExecution)
  },
}

"use client"

import { useEffect, useState } from "react"
import { Zap, Plus, Pencil, Trash2, Loader2, ChevronRight, ChevronLeft, History } from "lucide-react"
import { toast } from "sonner"

import {
  workflowsAPI,
  WorkflowRule,
  WorkflowExecution,
  WorkflowCondition,
  WorkflowAction,
  WorkflowTrigger,
} from "@/lib/api/workflows"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

// ── Constants ──────────────────────────────────────────────────────────────

const TRIGGER_TYPES = [
  { value: "complaint_created", label: "Complaint Created" },
  { value: "sla_breach", label: "SLA Breach" },
  { value: "state_change", label: "State Changed" },
  { value: "escalation_triggered", label: "Escalation Triggered" },
  { value: "sentiment_spike", label: "Sentiment Spike" },
  { value: "tat_breach", label: "TAT Breach" },
]

const CONDITION_FIELDS = [
  { value: "priority", label: "Priority" },
  { value: "category", label: "Category" },
  { value: "sentiment", label: "Sentiment Score" },
  { value: "urgency_score", label: "Urgency Score" },
  { value: "escalation_level", label: "Escalation Level" },
  { value: "source", label: "Source" },
  { value: "state", label: "State" },
]

const OPERATORS = [
  { value: "eq", label: "=" },
  { value: "neq", label: "≠" },
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
  { value: "contains", label: "contains" },
]

const ACTION_TYPES = [
  { value: "send_email", label: "Send Email" },
  { value: "send_slack", label: "Send Slack Alert" },
  { value: "escalate", label: "Escalate Ticket" },
  { value: "assign_team", label: "Assign to Team" },
  { value: "change_status", label: "Change Status" },
  { value: "auto_reply", label: "Trigger Auto Reply" },
]

// ── Types ──────────────────────────────────────────────────────────────────

const EMPTY_CONDITION: WorkflowCondition = { field: "priority", operator: "gte", value: "" }
const EMPTY_ACTION: WorkflowAction = { type: "send_slack", config: {} }

interface BuilderForm {
  name: string
  triggerType: string
  triggerValue: string
  conditions: WorkflowCondition[]
  actions: WorkflowAction[]
  enabled: boolean
}

const DEFAULT_FORM: BuilderForm = {
  name: "",
  triggerType: "complaint_created",
  triggerValue: "",
  conditions: [],
  actions: [{ ...EMPTY_ACTION }],
  enabled: true,
}

// ── Status badge color ─────────────────────────────────────────────────────

function execStatusBadge(status: string) {
  if (status === "success") return <Badge className="bg-green-100 text-green-800 border-green-200">{status}</Badge>
  if (status === "failed") return <Badge variant="destructive">{status}</Badge>
  if (status === "pending") return <Badge variant="secondary">{status}</Badge>
  return <Badge variant="outline">{status}</Badge>
}

// ── Main Component ─────────────────────────────────────────────────────────

export function WorkflowsContent() {
  const [rules, setRules] = useState<WorkflowRule[]>([])
  const [executions, setExecutions] = useState<WorkflowExecution[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isExecLoading, setIsExecLoading] = useState(false)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<WorkflowRule | null>(null)
  const [form, setForm] = useState<BuilderForm>(DEFAULT_FORM)
  const [step, setStep] = useState(0) // 0: basics, 1: conditions, 2: actions
  const [isSaving, setIsSaving] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState<WorkflowRule | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    loadRules()
  }, [])

  async function loadRules() {
    setIsLoading(true)
    try {
      setRules(await workflowsAPI.list())
    } catch {
      toast.error("Failed to load workflows")
    } finally {
      setIsLoading(false)
    }
  }

  async function loadExecutions() {
    setIsExecLoading(true)
    try {
      setExecutions(await workflowsAPI.listExecutions())
    } catch {
      toast.error("Failed to load execution history")
    } finally {
      setIsExecLoading(false)
    }
  }

  function openCreate() {
    setEditingRule(null)
    setForm(DEFAULT_FORM)
    setStep(0)
    setDialogOpen(true)
  }

  function openEdit(rule: WorkflowRule) {
    setEditingRule(rule)
    setForm({
      name: rule.workflowName,
      triggerType: rule.trigger.type ?? "complaint_created",
      triggerValue: String(rule.trigger.value ?? ""),
      conditions: rule.conditions.length ? rule.conditions : [],
      actions: rule.actions.length ? rule.actions : [{ ...EMPTY_ACTION }],
      enabled: rule.enabled,
    })
    setStep(0)
    setDialogOpen(true)
  }

  async function handleToggle(rule: WorkflowRule) {
    try {
      const updated = await workflowsAPI.toggle(rule.id)
      setRules((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
      toast.success(updated.enabled ? "Workflow enabled" : "Workflow disabled")
    } catch {
      toast.error("Failed to toggle workflow")
    }
  }

  async function handleSave() {
    if (!form.name.trim()) {
      toast.error("Workflow name is required")
      return
    }
    if (!form.actions.length || !form.actions[0].type) {
      toast.error("At least one action is required")
      return
    }
    setIsSaving(true)
    try {
      const trigger: WorkflowTrigger = {
        type: form.triggerType,
        ...(form.triggerValue ? { value: form.triggerValue } : {}),
      }
      const payload = {
        workflow_name: form.name.trim(),
        trigger,
        conditions: form.conditions,
        actions: form.actions,
        enabled: form.enabled,
      }
      if (editingRule) {
        const updated = await workflowsAPI.update(editingRule.id, payload)
        setRules((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
        toast.success("Workflow updated")
      } else {
        const created = await workflowsAPI.create(payload)
        setRules((prev) => [created, ...prev])
        toast.success("Workflow created")
      }
      setDialogOpen(false)
    } catch {
      toast.error("Failed to save workflow")
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await workflowsAPI.delete(deleteTarget.id)
      setRules((prev) => prev.filter((r) => r.id !== deleteTarget.id))
      toast.success("Workflow deleted")
      setDeleteTarget(null)
    } catch {
      toast.error("Failed to delete workflow")
    } finally {
      setIsDeleting(false)
    }
  }

  // Condition helpers
  function addCondition() {
    setForm((f) => ({ ...f, conditions: [...f.conditions, { ...EMPTY_CONDITION }] }))
  }
  function removeCondition(i: number) {
    setForm((f) => ({ ...f, conditions: f.conditions.filter((_, idx) => idx !== i) }))
  }
  function updateCondition(i: number, patch: Partial<WorkflowCondition>) {
    setForm((f) => ({
      ...f,
      conditions: f.conditions.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
    }))
  }

  // Action helpers
  function addAction() {
    setForm((f) => ({ ...f, actions: [...f.actions, { ...EMPTY_ACTION }] }))
  }
  function removeAction(i: number) {
    setForm((f) => ({ ...f, actions: f.actions.filter((_, idx) => idx !== i) }))
  }
  function updateAction(i: number, patch: Partial<WorkflowAction>) {
    setForm((f) => ({
      ...f,
      actions: f.actions.map((a, idx) => (idx === i ? { ...a, ...patch } : a)),
    }))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Automation</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Build event-driven workflows that automatically respond to complaint activity.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          New Workflow
        </Button>
      </div>

      <Tabs defaultValue="rules" onValueChange={(v) => v === "history" && loadExecutions()}>
        <TabsList>
          <TabsTrigger value="rules">Workflows</TabsTrigger>
          <TabsTrigger value="history">
            <History className="mr-1.5 h-3.5 w-3.5" />
            Execution History
          </TabsTrigger>
        </TabsList>

        {/* Rules Tab */}
        <TabsContent value="rules" className="mt-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              Loading workflows…
            </div>
          ) : rules.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
              <Zap className="h-12 w-12 mb-4 opacity-30" />
              <p className="font-medium">No workflows yet</p>
              <p className="text-sm mt-1">Create your first workflow to automate complaint handling.</p>
            </div>
          ) : (
            <div className="rounded-md border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">Name</th>
                    <th className="px-4 py-3 text-left font-medium">Trigger</th>
                    <th className="px-4 py-3 text-left font-medium">Conditions</th>
                    <th className="px-4 py-3 text-left font-medium">Actions</th>
                    <th className="px-4 py-3 text-left font-medium">Enabled</th>
                    <th className="px-4 py-3 text-right font-medium">Controls</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id} className="border-b last:border-0 hover:bg-muted/25 transition-colors">
                      <td className="px-4 py-3 font-medium">{rule.workflowName}</td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className="capitalize">
                          {TRIGGER_TYPES.find((t) => t.value === rule.trigger.type)?.label ?? rule.trigger.type}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {rule.conditions.length === 0
                          ? "Always"
                          : `${rule.conditions.length} condition${rule.conditions.length > 1 ? "s" : ""}`}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {rule.actions.slice(0, 2).map((a, i) => (
                            <Badge key={i} variant="secondary" className="text-xs capitalize">
                              {ACTION_TYPES.find((t) => t.value === a.type)?.label ?? a.type}
                            </Badge>
                          ))}
                          {rule.actions.length > 2 && (
                            <Badge variant="secondary" className="text-xs">
                              +{rule.actions.length - 2}
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Switch
                          checked={rule.enabled}
                          onCheckedChange={() => handleToggle(rule)}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEdit(rule)} title="Edit">
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteTarget(rule)}
                            title="Delete"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        {/* Execution History Tab */}
        <TabsContent value="history" className="mt-4">
          {isExecLoading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              Loading history…
            </div>
          ) : executions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
              <History className="h-12 w-12 mb-4 opacity-30" />
              <p className="font-medium">No executions yet</p>
              <p className="text-sm mt-1">Workflow executions will appear here when they run.</p>
            </div>
          ) : (
            <div className="rounded-md border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">Action</th>
                    <th className="px-4 py-3 text-left font-medium">Status</th>
                    <th className="px-4 py-3 text-left font-medium">Retries</th>
                    <th className="px-4 py-3 text-left font-medium">Error</th>
                    <th className="px-4 py-3 text-left font-medium">Executed At</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.map((ex) => (
                    <tr key={ex.id} className="border-b last:border-0 hover:bg-muted/25">
                      <td className="px-4 py-3 capitalize">{ex.actionType}</td>
                      <td className="px-4 py-3">{execStatusBadge(ex.executionStatus)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{ex.retryCount}</td>
                      <td className="px-4 py-3 text-xs text-destructive truncate max-w-[200px]">
                        {ex.errorMessage ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {ex.executedAt ? new Date(ex.executedAt).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Builder Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingRule ? "Edit Workflow" : "New Workflow"}</DialogTitle>
            <div className="flex items-center gap-2 pt-2 text-sm text-muted-foreground">
              <span className={step === 0 ? "font-medium text-foreground" : ""}>1. Basics</span>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className={step === 1 ? "font-medium text-foreground" : ""}>2. Conditions</span>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className={step === 2 ? "font-medium text-foreground" : ""}>3. Actions</span>
            </div>
          </DialogHeader>

          <div className="py-2 min-h-[260px]">
            {/* Step 0: Name + Trigger */}
            {step === 0 && (
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Workflow Name *</Label>
                  <Input
                    placeholder="e.g. Escalate High Priority Complaints"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Trigger Event *</Label>
                  <Select
                    value={form.triggerType}
                    onValueChange={(v) => setForm((f) => ({ ...f, triggerType: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select trigger" />
                    </SelectTrigger>
                    <SelectContent>
                      {TRIGGER_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-3 pt-1">
                  <Switch
                    id="wf-enabled"
                    checked={form.enabled}
                    onCheckedChange={(v) => setForm((f) => ({ ...f, enabled: v }))}
                  />
                  <Label htmlFor="wf-enabled">Enable workflow immediately</Label>
                </div>
              </div>
            )}

            {/* Step 1: Conditions */}
            {step === 1 && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  All conditions must match for the workflow to trigger. Leave empty to always trigger.
                </p>
                {form.conditions.map((cond, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Select
                      value={cond.field}
                      onValueChange={(v) => updateCondition(i, { field: v })}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CONDITION_FIELDS.map((f) => (
                          <SelectItem key={f.value} value={f.value}>
                            {f.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={cond.operator}
                      onValueChange={(v) => updateCondition(i, { operator: v })}
                    >
                      <SelectTrigger className="w-24">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {OPERATORS.map((op) => (
                          <SelectItem key={op.value} value={op.value}>
                            {op.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      className="flex-1"
                      placeholder="value"
                      value={String(cond.value)}
                      onChange={(e) => updateCondition(i, { value: e.target.value })}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeCondition(i)}
                      className="shrink-0 text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={addCondition}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Add Condition
                </Button>
              </div>
            )}

            {/* Step 2: Actions */}
            {step === 2 && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  All actions run in order when the workflow triggers.
                </p>
                {form.actions.map((action, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Select
                      value={action.type}
                      onValueChange={(v) => updateAction(i, { type: v })}
                    >
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder="Select action" />
                      </SelectTrigger>
                      <SelectContent>
                        {ACTION_TYPES.map((a) => (
                          <SelectItem key={a.value} value={a.value}>
                            {a.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {form.actions.length > 1 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeAction(i)}
                        className="shrink-0 text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={addAction}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Add Action
                </Button>
              </div>
            )}
          </div>

          <DialogFooter className="flex items-center justify-between sm:justify-between">
            <div>
              {step > 0 && (
                <Button variant="outline" onClick={() => setStep((s) => s - 1)}>
                  <ChevronLeft className="mr-1.5 h-4 w-4" />
                  Back
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={isSaving}>
                Cancel
              </Button>
              {step < 2 ? (
                <Button
                  onClick={() => setStep((s) => s + 1)}
                  disabled={step === 0 && !form.name.trim()}
                >
                  Next
                  <ChevronRight className="ml-1.5 h-4 w-4" />
                </Button>
              ) : (
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingRule ? "Save Changes" : "Create Workflow"}
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete workflow?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{deleteTarget?.workflowName}</strong> will be permanently deleted and will no longer
              run. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

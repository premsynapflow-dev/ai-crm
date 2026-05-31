"use client"

import { useEffect, useState } from "react"
import { BookOpen, Plus, Search, Pencil, Trash2, Archive, ArchiveRestore, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { knowledgeAPI, KnowledgeSnippet } from "@/lib/api/knowledge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
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
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const CATEGORIES = [
  "general",
  "refund",
  "billing",
  "technical",
  "shipping",
  "returns",
  "account",
  "compliance",
  "other",
]

const EMPTY_FORM = { title: "", content: "", category: "general", keywords: "" }

export function KnowledgeBaseContent() {
  const [snippets, setSnippets] = useState<KnowledgeSnippet[]>([])
  const [filtered, setFiltered] = useState<KnowledgeSnippet[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [showArchived, setShowArchived] = useState(false)

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingSnippet, setEditingSnippet] = useState<KnowledgeSnippet | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)

  // Delete confirm state
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeSnippet | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    loadSnippets()
  }, [])

  useEffect(() => {
    const q = searchQuery.toLowerCase()
    setFiltered(
      snippets.filter((s) => {
        if (!showArchived && s.status === "archived") return false
        if (!q) return true
        return (
          s.title.toLowerCase().includes(q) ||
          s.content.toLowerCase().includes(q) ||
          (s.category ?? "").toLowerCase().includes(q) ||
          s.keywords.some((k) => k.toLowerCase().includes(q))
        )
      })
    )
  }, [snippets, searchQuery, showArchived])

  async function loadSnippets() {
    setIsLoading(true)
    try {
      const data = await knowledgeAPI.list()
      setSnippets(data)
    } catch {
      toast.error("Failed to load knowledge base")
    } finally {
      setIsLoading(false)
    }
  }

  function openCreate() {
    setEditingSnippet(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  function openEdit(snippet: KnowledgeSnippet) {
    setEditingSnippet(snippet)
    setForm({
      title: snippet.title,
      content: snippet.content,
      category: snippet.category ?? "general",
      keywords: snippet.keywords.join(", "),
    })
    setDialogOpen(true)
  }

  async function handleSave() {
    if (!form.title.trim() || !form.content.trim()) {
      toast.error("Title and content are required")
      return
    }
    setIsSaving(true)
    try {
      const keywords = form.keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean)

      if (editingSnippet) {
        const updated = await knowledgeAPI.update(editingSnippet.id, {
          title: form.title.trim(),
          content: form.content.trim(),
          category: form.category || undefined,
          keywords,
        })
        setSnippets((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
        toast.success("Snippet updated")
      } else {
        const created = await knowledgeAPI.create({
          title: form.title.trim(),
          content: form.content.trim(),
          category: form.category || undefined,
          keywords,
        })
        setSnippets((prev) => [created, ...prev])
        toast.success("Snippet created")
      }
      setDialogOpen(false)
    } catch {
      toast.error("Failed to save snippet")
    } finally {
      setIsSaving(false)
    }
  }

  async function handleToggleStatus(snippet: KnowledgeSnippet) {
    const newStatus = snippet.status === "active" ? "archived" : "active"
    try {
      const updated = await knowledgeAPI.updateStatus(snippet.id, newStatus)
      setSnippets((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      toast.success(newStatus === "archived" ? "Snippet archived" : "Snippet restored")
    } catch {
      toast.error("Failed to update snippet status")
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await knowledgeAPI.delete(deleteTarget.id)
      setSnippets((prev) => prev.filter((s) => s.id !== deleteTarget.id))
      toast.success("Snippet deleted")
      setDeleteTarget(null)
    } catch {
      toast.error("Failed to delete snippet")
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Snippets are automatically injected into AI reply generation to improve response quality.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          New Snippet
        </Button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search snippets…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button
          variant={showArchived ? "secondary" : "outline"}
          size="sm"
          onClick={() => setShowArchived((v) => !v)}
        >
          {showArchived ? "Hide Archived" : "Show Archived"}
        </Button>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          Loading snippets…
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
          <BookOpen className="h-12 w-12 mb-4 opacity-30" />
          <p className="font-medium">No snippets found</p>
          <p className="text-sm mt-1">
            {snippets.length === 0
              ? "Create your first snippet to help the AI generate better replies."
              : "Try a different search term."}
          </p>
        </div>
      ) : (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Title</th>
                <th className="px-4 py-3 text-left font-medium">Category</th>
                <th className="px-4 py-3 text-left font-medium">Keywords</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Updated</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((snippet) => (
                <tr key={snippet.id} className="border-b last:border-0 hover:bg-muted/25 transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium truncate max-w-[200px]">{snippet.title}</p>
                    <p className="text-xs text-muted-foreground truncate max-w-[200px] mt-0.5">
                      {snippet.content.slice(0, 80)}…
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="capitalize">
                      {snippet.category ?? "general"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1 max-w-[200px]">
                      {snippet.keywords.slice(0, 3).map((k) => (
                        <Badge key={k} variant="secondary" className="text-xs">
                          {k}
                        </Badge>
                      ))}
                      {snippet.keywords.length > 3 && (
                        <Badge variant="secondary" className="text-xs">
                          +{snippet.keywords.length - 3}
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={snippet.status === "active" ? "default" : "secondary"}
                      className="capitalize"
                    >
                      {snippet.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {new Date(snippet.updatedAt).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(snippet)} title="Edit">
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleToggleStatus(snippet)}
                        title={snippet.status === "active" ? "Archive" : "Restore"}
                      >
                        {snippet.status === "active" ? (
                          <Archive className="h-4 w-4" />
                        ) : (
                          <ArchiveRestore className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(snippet)}
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

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingSnippet ? "Edit Snippet" : "New Snippet"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="kb-title">Title *</Label>
              <Input
                id="kb-title"
                placeholder="e.g. Refund Policy"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="kb-content">Content *</Label>
              <Textarea
                id="kb-content"
                placeholder="Write the knowledge content here…"
                rows={5}
                value={form.content}
                onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="kb-category">Category</Label>
                <Select
                  value={form.category}
                  onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}
                >
                  <SelectTrigger id="kb-category">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c} value={c} className="capitalize">
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="kb-keywords">Keywords</Label>
                <Input
                  id="kb-keywords"
                  placeholder="refund, billing, policy"
                  value={form.keywords}
                  onChange={(e) => setForm((f) => ({ ...f, keywords: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground">Comma-separated</p>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingSnippet ? "Save Changes" : "Create Snippet"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete snippet?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{deleteTarget?.title}</strong> will be permanently deleted and removed from AI reply
              context. This cannot be undone.
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

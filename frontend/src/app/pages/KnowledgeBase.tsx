import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { api, KnowledgeSnippet } from "../lib/api";
import { BookOpen, Plus, Search, Edit, Trash2 } from "lucide-react";
import { toast } from "sonner";

export function KnowledgeBase() {
  const [snippets, setSnippets] = useState<KnowledgeSnippet[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newSnippet, setNewSnippet] = useState({ title: "", category: "", content: "" });

  useEffect(() => {
    loadSnippets();
  }, []);

  const loadSnippets = async () => {
    setLoading(true);
    try {
      const data = await api.knowledge.list();
      setSnippets(data);
    } catch (error) {
      console.error("Failed to load snippets:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      await api.knowledge.create(newSnippet);
      toast.success("Snippet created successfully!");
      setIsDialogOpen(false);
      setNewSnippet({ title: "", category: "", content: "" });
      loadSnippets();
    } catch (error) {
      toast.error("Failed to create snippet");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.knowledge.delete(id);
      toast.success("Snippet deleted");
      loadSnippets();
    } catch (error) {
      toast.error("Failed to delete snippet");
    }
  };

  const filteredSnippets = snippets.filter((snippet) =>
    snippet.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    snippet.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Knowledge Base</h1>
          <p className="text-gray-600">Pre-approved reply templates for AI to use</p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="size-4 mr-2" />
              Add Snippet
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Knowledge Snippet</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={newSnippet.title}
                  onChange={(e) => setNewSnippet({ ...newSnippet, title: e.target.value })}
                  placeholder="e.g., Payment Issue - Standard Response"
                />
              </div>

              <div>
                <Label htmlFor="category">Category</Label>
                <Select
                  value={newSnippet.category}
                  onValueChange={(value) => setNewSnippet({ ...newSnippet, category: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Billing">Billing</SelectItem>
                    <SelectItem value="Technical Support">Technical Support</SelectItem>
                    <SelectItem value="Delivery">Delivery</SelectItem>
                    <SelectItem value="Loan">Loan</SelectItem>
                    <SelectItem value="Account">Account</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="content">Reply Template</Label>
                <Textarea
                  id="content"
                  value={newSnippet.content}
                  onChange={(e) => setNewSnippet({ ...newSnippet, content: e.target.value })}
                  rows={8}
                  placeholder="Enter the standard reply template..."
                />
              </div>

              <Button onClick={handleCreate} className="w-full">
                Create Snippet
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total Snippets
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{snippets.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {snippets.reduce((sum, s) => sum + s.usage_count, 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Categories
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {new Set(snippets.map((s) => s.category)).size}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Snippets</CardTitle>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-gray-400" />
              <Input
                placeholder="Search snippets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading snippets...</div>
          ) : filteredSnippets.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No snippets found</div>
          ) : (
            <div className="space-y-4">
              {filteredSnippets.map((snippet) => (
                <div key={snippet.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold">{snippet.title}</h3>
                        <Badge variant="outline">{snippet.category}</Badge>
                      </div>
                      <p className="text-sm text-gray-600 mb-3">{snippet.content}</p>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>Used {snippet.usage_count} times</span>
                        <span>•</span>
                        <span>By {snippet.created_by}</span>
                        <span>•</span>
                        <span>{new Date(snippet.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <Button size="sm" variant="ghost">
                        <Edit className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(snippet.id)}
                      >
                        <Trash2 className="size-4 text-red-600" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

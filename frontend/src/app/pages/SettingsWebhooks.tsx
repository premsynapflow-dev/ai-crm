import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Loader2, Slack, Trash2 } from "lucide-react";

export function SettingsWebhooks() {
  const [slackUrl, setSlackUrl] = useState("");
  const [savedSlackUrl, setSavedSlackUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.settings.get()
      .then((data) => {
        const slackWebhook = (data.webhooks as Array<{ id: string; url: string }>).find((w) => w.id === "slack");
        if (slackWebhook?.url) {
          setSavedSlackUrl(slackWebhook.url);
          setSlackUrl(slackWebhook.url);
        }
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.settings.updateSlack(slackUrl.trim());
      setSavedSlackUrl(slackUrl.trim() || null);
      toast.success(slackUrl.trim() ? "Slack webhook saved" : "Slack webhook removed");
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message;
      toast.error(msg?.includes("Invalid") ? "Invalid Slack webhook URL" : "Failed to save webhook");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      await api.settings.testSlack(slackUrl.trim() || undefined);
      toast.success("Test message sent to Slack!");
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message;
      toast.error(msg?.includes("Invalid") ? "Enter a valid Slack webhook URL first" : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    setSaving(true);
    try {
      await api.settings.updateSlack("");
      setSavedSlackUrl(null);
      setSlackUrl("");
      toast.success("Slack webhook disconnected");
    } catch {
      toast.error("Failed to disconnect");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Webhooks</h1>
          <p className="text-gray-600">Configure outbound notifications for complaint events</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-5 animate-spin text-gray-400" />
        </div>
      ) : (
        <>
          {/* Slack */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Slack className="size-5 text-[#4A154B]" />
                Slack Notifications
                {savedSlackUrl && <Badge className="ml-2">Active</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-600">
                Send complaint events to a Slack channel. You'll receive alerts for new tickets, escalations, and SLA breaches.
              </p>
              <div>
                <Label htmlFor="slack-url">Incoming Webhook URL</Label>
                <Input
                  id="slack-url"
                  value={slackUrl}
                  onChange={(e) => setSlackUrl(e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  className="mt-1.5 font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1.5">
                  Create an Incoming Webhook in your{" "}
                  <a href="https://api.slack.com/apps" target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                    Slack App configuration
                  </a>.
                </p>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleSave} disabled={saving || slackUrl === (savedSlackUrl ?? "")}>
                  {saving && <Loader2 className="size-4 mr-2 animate-spin" />}
                  Save
                </Button>
                <Button
                  variant="outline"
                  onClick={handleTest}
                  disabled={testing || !slackUrl.trim()}
                >
                  {testing && <Loader2 className="size-4 mr-2 animate-spin" />}
                  Test
                </Button>
                {savedSlackUrl && (
                  <Button
                    variant="ghost"
                    className="text-red-500 hover:text-red-700 hover:bg-red-50 ml-auto"
                    onClick={handleDisconnect}
                    disabled={saving}
                  >
                    <Trash2 className="size-4 mr-1.5" />
                    Disconnect
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Events reference */}
          <Card>
            <CardHeader>
              <CardTitle>Triggered Events</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li className="flex items-start gap-3">
                  <code className="bg-gray-100 px-2 py-0.5 rounded text-xs shrink-0">complaint.created</code>
                  <span className="text-gray-600">Sent when a new complaint ticket is received</span>
                </li>
                <li className="flex items-start gap-3">
                  <code className="bg-gray-100 px-2 py-0.5 rounded text-xs shrink-0">complaint.escalated</code>
                  <span className="text-gray-600">Sent when a ticket is escalated to a higher tier</span>
                </li>
                <li className="flex items-start gap-3">
                  <code className="bg-gray-100 px-2 py-0.5 rounded text-xs shrink-0">complaint.resolved</code>
                  <span className="text-gray-600">Sent when a ticket is marked as resolved</span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

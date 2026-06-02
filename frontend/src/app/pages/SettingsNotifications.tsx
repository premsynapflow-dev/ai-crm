import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Loader2, Bell } from "lucide-react";

interface NotifPrefs {
  sla_breach: boolean;
  new_escalation: boolean;
  daily_digest: boolean;
  ticket_assigned: boolean;
  ai_draft_expired: boolean;
}

const DEFAULT_PREFS: NotifPrefs = {
  sla_breach: false,
  new_escalation: false,
  daily_digest: false,
  ticket_assigned: false,
  ai_draft_expired: false,
};

export function SettingsNotifications() {
  const [prefs, setPrefs] = useState<NotifPrefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.settings.get()
      .then((data) => {
        const saved = data.notification_preferences as Partial<NotifPrefs> | undefined;
        if (saved && typeof saved === "object") {
          setPrefs({ ...DEFAULT_PREFS, ...saved });
        }
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  const toggle = (key: keyof NotifPrefs) => {
    setPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.settings.updateNotificationPrefs(prefs);
      toast.success("Notification preferences saved");
    } catch {
      toast.error("Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="size-5 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Notifications</h1>
          <p className="text-gray-600">Configure how you receive alerts</p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving && <Loader2 className="size-4 mr-2 animate-spin" />}
          Save Preferences
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-5" />
            Email Alerts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <Label>SLA Breach Alerts</Label>
              <p className="text-sm text-gray-500">Get notified when tickets breach their SLA deadline</p>
            </div>
            <Switch checked={prefs.sla_breach} onCheckedChange={() => toggle("sla_breach")} />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>New Escalations</Label>
              <p className="text-sm text-gray-500">Alert when complaints are escalated to a higher tier</p>
            </div>
            <Switch checked={prefs.new_escalation} onCheckedChange={() => toggle("new_escalation")} />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>Daily Digest</Label>
              <p className="text-sm text-gray-500">Daily summary of ticket activity sent each morning</p>
            </div>
            <Switch checked={prefs.daily_digest} onCheckedChange={() => toggle("daily_digest")} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>In-App Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <Label>New Ticket Assigned</Label>
              <p className="text-sm text-gray-500">When a ticket is assigned to you</p>
            </div>
            <Switch checked={prefs.ticket_assigned} onCheckedChange={() => toggle("ticket_assigned")} />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>AI Draft Expired</Label>
              <p className="text-sm text-gray-500">When AI reply drafts expire without review</p>
            </div>
            <Switch checked={prefs.ai_draft_expired} onCheckedChange={() => toggle("ai_draft_expired")} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

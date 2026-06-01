import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Label } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";

export function SettingsNotifications() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Notifications</h1>
        <p className="text-gray-600">Configure how you receive alerts</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Slack Integration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="slackWebhook">Webhook URL</Label>
            <Input
              id="slackWebhook"
              placeholder="https://hooks.slack.com/services/..."
            />
          </div>
          <Button>Test Connection</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Email Alerts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>SLA Breach Alerts</Label>
              <p className="text-sm text-gray-500">Get notified when tickets breach SLA</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>New Escalations</Label>
              <p className="text-sm text-gray-500">Alert when complaints are escalated</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>Daily Digest</Label>
              <p className="text-sm text-gray-500">Daily summary of ticket activity</p>
            </div>
            <Switch />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>In-App Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>New Ticket Assigned</Label>
              <p className="text-sm text-gray-500">When a ticket is assigned to you</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>AI Draft Expired</Label>
              <p className="text-sm text-gray-500">When AI reply drafts expire</p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";

export function SettingsWebhooks() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Webhooks</h1>
          <p className="text-gray-600">Configure outbound webhooks for events</p>
        </div>
        <Button>Add Webhook</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configured Webhooks</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 border rounded">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium">Production Webhook</div>
                <Badge>Active</Badge>
              </div>
              <div className="text-sm text-gray-600 mb-3">
                https://api.yourapp.com/synapflow/webhook
              </div>
              <div className="flex gap-2 text-xs">
                <Badge variant="outline">ticket.created</Badge>
                <Badge variant="outline">ticket.resolved</Badge>
                <Badge variant="outline">ticket.escalated</Badge>
              </div>
              <div className="flex gap-2 mt-3">
                <Button size="sm" variant="outline">Test</Button>
                <Button size="sm" variant="outline">Edit</Button>
                <Button size="sm" variant="destructive">Delete</Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Available Events</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            <li><code className="bg-gray-100 px-2 py-1 rounded">ticket.created</code> - When a new ticket is created</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">ticket.resolved</code> - When a ticket is resolved</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">ticket.escalated</code> - When a ticket is escalated</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">reply.sent</code> - When a reply is sent</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

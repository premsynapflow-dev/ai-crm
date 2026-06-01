import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Mail, MessageSquare, Globe, Phone, Instagram, Star, Copy } from "lucide-react";
import { toast } from "sonner";

export function SettingsConnections() {
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Connections</h1>
        <p className="text-gray-600">Connect channels to ingest complaints</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className="size-5" />
              <CardTitle>REST API</CardTitle>
            </div>
            <Badge variant="outline">Connected</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-sm font-medium">API Key</label>
            <div className="flex gap-2 mt-1">
              <Input value="sk_live_xxxxxxxxxxxxxxxxxxxx" readOnly className="font-mono text-sm" />
              <Button variant="outline" onClick={() => copyToClipboard("sk_live_xxxxxxxxxxxxxxxxxxxx")}>
                <Copy className="size-4" />
              </Button>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Webhook URL</label>
            <div className="flex gap-2 mt-1">
              <Input value="https://api.synapflow.com/webhook/complaints" readOnly className="text-sm" />
              <Button variant="outline" onClick={() => copyToClipboard("https://api.synapflow.com/webhook/complaints")}>
                <Copy className="size-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail className="size-5" />
              <CardTitle>Gmail</CardTitle>
            </div>
            <Badge>Connected</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-3">support@democompany.com</p>
          <Button variant="outline">Disconnect</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <MessageSquare className="size-5" />
              <CardTitle>WhatsApp</CardTitle>
            </div>
            <Badge variant="outline">Not Connected</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-3">Connect via Meta Business API</p>
          <Button>Connect WhatsApp</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className="size-5" />
              <CardTitle>Live Chat Widget</CardTitle>
            </div>
            <Badge>Connected</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-sm font-medium">Embed Code</label>
            <textarea
              className="w-full mt-1 p-2 border rounded text-xs font-mono bg-gray-50"
              rows={4}
              readOnly
              value={`<script src="https://cdn.synapflow.com/widget.js" data-key="pk_live_xxxxx"></script>`}
            />
          </div>
          <Button variant="outline" onClick={() => copyToClipboard('<script...')}>
            <Copy className="size-4 mr-2" />
            Copy Embed Code
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Instagram className="size-5" />
              <CardTitle>Instagram DMs</CardTitle>
            </div>
            <Badge variant="outline">Max+ Only</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-3">Available on Max, Scale, and Enterprise plans</p>
          <Button disabled>Connect Instagram</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Star className="size-5" />
              <CardTitle>Google Reviews</CardTitle>
            </div>
            <Badge variant="outline">Max+ Only</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-3">Available on Max, Scale, and Enterprise plans</p>
          <Button disabled>Connect Google Reviews</Button>
        </CardContent>
      </Card>
    </div>
  );
}

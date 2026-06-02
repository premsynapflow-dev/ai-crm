import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Mail,
  MessageSquare,
  Globe,
  Instagram,
  Star,
  Copy,
  Plus,
  Trash2,
  Loader2,
  Eye,
  EyeOff,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

interface Inbox {
  id: string;
  email: string;
  provider: string;
  status: string;
}

export function SettingsConnections() {
  const location = useLocation();
  const [apiKey, setApiKey] = useState("");
  const [inboxes, setInboxes] = useState<Inbox[]>([]);
  const [loading, setLoading] = useState(true);
  const [showApiKey, setShowApiKey] = useState(false);
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);
  const [showImapDialog, setShowImapDialog] = useState(false);
  const [imapForm, setImapForm] = useState({
    email: "",
    password: "",
    host: "",
    port: "993",
    use_ssl: true,
  });
  const [connectingImap, setConnectingImap] = useState(false);

  const webhookUrl = `${window.location.origin}/webhook/complaints`;

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("gmail_connected") === "true") {
      toast.success("Gmail account connected successfully!");
      window.history.replaceState({}, "", location.pathname);
    } else if (params.get("gmail_error") === "true") {
      toast.error("Gmail connection failed. Please try again.");
      window.history.replaceState({}, "", location.pathname);
    }

    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [settings, inboxList] = await Promise.all([
        api.settings.get(),
        api.inboxes.list(),
      ]);
      setApiKey(settings.api_key || "");
      setInboxes(inboxList);
    } catch {
      toast.error("Failed to load connection settings.");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied!");
  };

  const handleConnectGmail = async () => {
    setConnectingGmail(true);
    try {
      const { connect_url } = await api.inboxes.getGmailConnectUrl();
      window.location.href = connect_url;
    } catch {
      toast.error("Could not start Gmail OAuth. Ensure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are configured.");
      setConnectingGmail(false);
    }
  };

  const handleDisconnect = async (id: string, email: string) => {
    setDisconnectingId(id);
    try {
      await api.inboxes.disconnect(id);
      setInboxes((prev) => prev.filter((i) => i.id !== id));
      toast.success(`Disconnected ${email}`);
    } catch {
      toast.error("Failed to disconnect. Please try again.");
    } finally {
      setDisconnectingId(null);
    }
  };

  const handleConnectImap = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnectingImap(true);
    try {
      const inbox = await api.inboxes.connectImap({
        email: imapForm.email,
        password: imapForm.password,
        host: imapForm.host || undefined,
        port: parseInt(imapForm.port) || 993,
        use_ssl: imapForm.use_ssl,
      });
      setInboxes((prev) => [...prev, inbox]);
      setShowImapDialog(false);
      setImapForm({ email: "", password: "", host: "", port: "993", use_ssl: true });
      toast.success(`Connected ${inbox.email}`);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Connection failed";
      if (msg.toLowerCase().includes("auth")) {
        toast.error("Authentication failed — check your email and password.");
      } else if (msg.toLowerCase().includes("host")) {
        toast.error("Could not reach IMAP server — check the host and port.");
      } else {
        toast.error(msg);
      }
    } finally {
      setConnectingImap(false);
    }
  };

  const gmailInboxes = inboxes.filter((i) => i.provider === "gmail");
  const imapInboxes = inboxes.filter((i) => i.provider === "imap");
  const maskedApiKey = apiKey ? apiKey.slice(0, 8) + "•".repeat(Math.max(0, apiKey.length - 8)) : "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Connections</h1>
        <p className="text-gray-600">Connect channels to ingest complaints</p>
      </div>

      {/* REST API */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className="size-5" />
              <CardTitle>REST API</CardTitle>
            </div>
            <Badge variant="outline">Always Active</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>API Key</Label>
            <div className="flex gap-2 mt-1">
              <Input
                value={loading ? "Loading…" : showApiKey ? apiKey : maskedApiKey}
                readOnly
                className="font-mono text-sm"
              />
              <Button variant="outline" size="icon" onClick={() => setShowApiKey((v) => !v)}>
                {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </Button>
              <Button variant="outline" size="icon" onClick={() => copyToClipboard(apiKey)} disabled={!apiKey}>
                <Copy className="size-4" />
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Send as <code className="bg-gray-100 px-1 rounded">x-api-key</code> header with every API request.
            </p>
          </div>
          <div>
            <Label>Webhook Endpoint</Label>
            <div className="flex gap-2 mt-1">
              <Input value={webhookUrl} readOnly className="text-sm" />
              <Button variant="outline" size="icon" onClick={() => copyToClipboard(webhookUrl)}>
                <Copy className="size-4" />
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              POST complaints to this URL with the <code className="bg-gray-100 px-1 rounded">x-api-key</code> header.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Gmail */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail className="size-5" />
              <CardTitle>Gmail</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              {gmailInboxes.length > 0 && (
                <Badge variant="secondary">{gmailInboxes.length} connected</Badge>
              )}
              <Button size="sm" onClick={handleConnectGmail} disabled={connectingGmail}>
                {connectingGmail ? (
                  <><Loader2 className="size-4 mr-2 animate-spin" />Redirecting…</>
                ) : (
                  <><Plus className="size-4 mr-2" />Connect Gmail</>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="size-4 animate-spin" /> Loading…
            </div>
          ) : gmailInboxes.length === 0 ? (
            <p className="text-sm text-gray-500">
              No Gmail accounts connected. Click "Connect Gmail" to authorize via Google OAuth — new complaints arriving in that inbox will be ingested automatically.
            </p>
          ) : (
            <div className="space-y-2">
              {gmailInboxes.map((inbox) => (
                <div
                  key={inbox.id}
                  className="flex items-center justify-between p-3 border rounded-lg bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <div className="size-8 bg-red-100 rounded-full flex items-center justify-center">
                      <Mail className="size-4 text-red-600" />
                    </div>
                    <div>
                      <div className="text-sm font-medium">{inbox.email}</div>
                      <div className="text-xs text-green-600 font-medium">● Active</div>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-red-600 border-red-200 hover:bg-red-50"
                    disabled={disconnectingId === inbox.id}
                    onClick={() => handleDisconnect(inbox.id, inbox.email)}
                  >
                    {disconnectingId === inbox.id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <><Trash2 className="size-4 mr-1.5" />Disconnect</>
                    )}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* IMAP */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail className="size-5" />
              <CardTitle>Email (IMAP)</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              {imapInboxes.length > 0 && (
                <Badge variant="secondary">{imapInboxes.length} connected</Badge>
              )}
              <Button size="sm" variant="outline" onClick={() => setShowImapDialog(true)}>
                <Plus className="size-4 mr-2" />Add Account
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="size-4 animate-spin" /> Loading…
            </div>
          ) : imapInboxes.length === 0 ? (
            <p className="text-sm text-gray-500">
              Connect any IMAP mailbox — Outlook, Yahoo, Zoho, or a custom server. Complaints arriving in that inbox are ingested automatically every few minutes.
            </p>
          ) : (
            <div className="space-y-2">
              {imapInboxes.map((inbox) => (
                <div
                  key={inbox.id}
                  className="flex items-center justify-between p-3 border rounded-lg bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <div className="size-8 bg-blue-100 rounded-full flex items-center justify-center">
                      <Mail className="size-4 text-blue-600" />
                    </div>
                    <div>
                      <div className="text-sm font-medium">{inbox.email}</div>
                      <div className="text-xs text-green-600 font-medium">● Active (IMAP)</div>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-red-600 border-red-200 hover:bg-red-50"
                    disabled={disconnectingId === inbox.id}
                    onClick={() => handleDisconnect(inbox.id, inbox.email)}
                  >
                    {disconnectingId === inbox.id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <><Trash2 className="size-4 mr-1.5" />Disconnect</>
                    )}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* WhatsApp */}
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
          <p className="text-sm text-gray-600 mb-3">
            Connect via Meta Business API. Requires a WhatsApp Business Account and phone number.
          </p>
          <Button disabled>Connect WhatsApp</Button>
        </CardContent>
      </Card>

      {/* Live Chat Widget */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className="size-5" />
              <CardTitle>Live Chat Widget</CardTitle>
            </div>
            {apiKey ? <Badge>Active</Badge> : <Badge variant="outline">Requires API Key</Badge>}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label>Embed Code</Label>
            <textarea
              className="w-full mt-1 p-2 border rounded text-xs font-mono bg-gray-50"
              rows={3}
              readOnly
              value={`<script src="${window.location.origin}/widget.js" data-key="${apiKey || "YOUR_API_KEY"}"></script>`}
            />
          </div>
          <Button
            variant="outline"
            onClick={() =>
              copyToClipboard(
                `<script src="${window.location.origin}/widget.js" data-key="${apiKey}"></script>`
              )
            }
            disabled={!apiKey}
          >
            <Copy className="size-4 mr-2" />
            Copy Embed Code
          </Button>
        </CardContent>
      </Card>

      {/* Instagram DMs */}
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
          <p className="text-sm text-gray-600 mb-3">Available on Max, Scale, and Enterprise plans.</p>
          <Button disabled>Connect Instagram</Button>
        </CardContent>
      </Card>

      {/* Google Reviews */}
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
          <p className="text-sm text-gray-600 mb-3">Available on Max, Scale, and Enterprise plans.</p>
          <Button disabled>Connect Google Reviews</Button>
        </CardContent>
      </Card>

      {/* IMAP Connect Dialog */}
      <Dialog open={showImapDialog} onOpenChange={setShowImapDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Connect IMAP Account</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleConnectImap} className="space-y-4 pt-2">
            <div>
              <Label>Email Address</Label>
              <Input
                type="email"
                placeholder="support@yourcompany.com"
                value={imapForm.email}
                onChange={(e) => setImapForm((f) => ({ ...f, email: e.target.value }))}
                required
              />
            </div>
            <div>
              <Label>Password / App Password</Label>
              <Input
                type="password"
                placeholder="Use an app-specific password if 2FA is enabled"
                value={imapForm.password}
                onChange={(e) => setImapForm((f) => ({ ...f, password: e.target.value }))}
                required
              />
            </div>
            <div>
              <Label>
                IMAP Host{" "}
                <span className="text-gray-400 text-xs font-normal">
                  (auto-detected for Gmail, Outlook, Yahoo)
                </span>
              </Label>
              <Input
                placeholder="imap.yourprovider.com"
                value={imapForm.host}
                onChange={(e) => setImapForm((f) => ({ ...f, host: e.target.value }))}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <Label>Port</Label>
                <Input
                  type="number"
                  value={imapForm.port}
                  onChange={(e) => setImapForm((f) => ({ ...f, port: e.target.value }))}
                />
              </div>
              <div className="flex-1 flex flex-col justify-end pb-1">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="imap_use_ssl"
                    checked={imapForm.use_ssl}
                    onChange={(e) => setImapForm((f) => ({ ...f, use_ssl: e.target.checked }))}
                    className="rounded"
                  />
                  <label htmlFor="imap_use_ssl" className="text-sm">
                    Use SSL/TLS
                  </label>
                </div>
              </div>
            </div>
            <div className="flex gap-3 pt-1">
              <Button type="submit" disabled={connectingImap} className="flex-1">
                {connectingImap ? (
                  <><Loader2 className="size-4 mr-2 animate-spin" />Testing connection…</>
                ) : (
                  "Connect"
                )}
              </Button>
              <Button type="button" variant="outline" onClick={() => setShowImapDialog(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

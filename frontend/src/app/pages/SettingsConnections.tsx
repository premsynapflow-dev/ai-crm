import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
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
  Lock,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth-context";

interface Inbox {
  id: string;
  email: string;
  provider: string;
  status: string;
}

interface ChannelConn {
  id: string;
  channel_type: string;
  account_identifier: string | null;
  status: string;
  metadata: Record<string, unknown>;
}

export function SettingsConnections() {
  const { user } = useAuth();
  const location = useLocation();

  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [inboxes, setInboxes] = useState<Inbox[]>([]);
  const [channelConns, setChannelConns] = useState<ChannelConn[]>([]);
  const [loading, setLoading] = useState(true);

  // Gmail
  const [connectingGmail, setConnectingGmail] = useState(false);

  // IMAP dialog
  const [showImapDialog, setShowImapDialog] = useState(false);
  const [imapForm, setImapForm] = useState({ email: "", password: "", host: "", port: "993", use_ssl: true });
  const [connectingImap, setConnectingImap] = useState(false);

  // WhatsApp dialog
  const [showWaDialog, setShowWaDialog] = useState(false);
  const [waForm, setWaForm] = useState({ phone_number_id: "", access_token: "", business_account_id: "" });
  const [connectingWa, setConnectingWa] = useState(false);

  // Shared disconnect
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);

  // Manual sync
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const webhookUrl = `${window.location.origin}/webhook/complaints`;
  const waWebhookUrl = `${window.location.origin}/webhooks/whatsapp`;

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("gmail_connected") === "true") {
      toast.success("Gmail account connected!");
      window.history.replaceState({}, "", location.pathname);
    } else if (params.get("gmail_error") === "true") {
      toast.error("Gmail connection failed. Please try again.");
      window.history.replaceState({}, "", location.pathname);
    }
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [settings, inboxList, connList] = await Promise.all([
        api.settings.get(),
        api.inboxes.list(),
        api.channels.list(),
      ]);
      setApiKey(settings.api_key || "");
      setInboxes(inboxList);
      setChannelConns(connList);
    } catch {
      toast.error("Failed to load connections.");
    } finally {
      setLoading(false);
    }
  };

  const copy = (text: string, label = "Copied!") => {
    navigator.clipboard.writeText(text);
    toast.success(label);
  };

  // Gmail
  const handleConnectGmail = async () => {
    setConnectingGmail(true);
    try {
      const { connect_url } = await api.inboxes.getGmailConnectUrl();
      window.location.href = connect_url;
    } catch {
      toast.error("Could not start Gmail OAuth. Ensure Google OAuth env vars are set.");
      setConnectingGmail(false);
    }
  };

  const handleSyncInbox = async (id: string, email: string) => {
    setSyncingId(id);
    try {
      const result = await api.inboxes.poll(id);
      if (result.error) {
        toast.error(`Sync failed: ${result.error}`);
      } else if (result.result) {
        const { fetched, processed, duplicates } = result.result;
        if (fetched === 0) {
          toast.info("No new messages found in inbox.");
        } else {
          toast.success(`Synced: ${fetched} fetched, ${processed} new complaint${processed !== 1 ? "s" : ""}, ${duplicates} already seen.`);
        }
      }
    } catch {
      toast.error("Sync request failed. Check server logs.");
    } finally {
      setSyncingId(null);
    }
  };

  const handleDisconnectInbox = async (id: string, email: string) => {
    setDisconnectingId(id);
    try {
      await api.inboxes.disconnect(id);
      setInboxes((p) => p.filter((i) => i.id !== id));
      toast.success(`Disconnected ${email}`);
    } catch {
      toast.error("Failed to disconnect.");
    } finally {
      setDisconnectingId(null);
    }
  };

  // IMAP
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
      setInboxes((p) => [...p, inbox]);
      setShowImapDialog(false);
      setImapForm({ email: "", password: "", host: "", port: "993", use_ssl: true });
      toast.success(`Connected ${inbox.email}`);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Connection failed";
      toast.error(msg.toLowerCase().includes("auth") ? "Authentication failed — check credentials." : msg);
    } finally {
      setConnectingImap(false);
    }
  };

  // WhatsApp
  const handleConnectWhatsApp = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnectingWa(true);
    try {
      const res = await api.channels.connectWhatsApp({
        phone_number_id: waForm.phone_number_id,
        access_token: waForm.access_token,
        business_account_id: waForm.business_account_id || undefined,
      });
      await loadAll();
      setShowWaDialog(false);
      setWaForm({ phone_number_id: "", access_token: "", business_account_id: "" });
      toast.success(`Connected WhatsApp number ${res.account_identifier}`);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Connection failed";
      toast.error(msg);
    } finally {
      setConnectingWa(false);
    }
  };

  const handleDisconnectChannel = async (id: string, label: string) => {
    setDisconnectingId(id);
    try {
      await api.channels.disconnect(id);
      setChannelConns((p) => p.filter((c) => c.id !== id));
      toast.success(`Disconnected ${label}`);
    } catch {
      toast.error("Failed to disconnect.");
    } finally {
      setDisconnectingId(null);
    }
  };

  const gmailInboxes = inboxes.filter((i) => i.provider === "gmail");
  const imapInboxes = inboxes.filter((i) => i.provider === "imap");
  const waConns = channelConns.filter((c) => c.channel_type === "whatsapp");
  const maskedKey = apiKey ? apiKey.slice(0, 8) + "•".repeat(Math.max(0, apiKey.length - 8)) : "";

  const isPaidPlan = ["max", "scale", "enterprise"].includes(user?.plan?.toLowerCase() || "");

  // ── Shared UI helpers ──────────────────────────────────────────────────────

  const InboxRow = ({
    id, label, sublabel, onDisconnect, onSync,
  }: { id: string; label: string; sublabel?: string; onDisconnect: () => void; onSync?: () => void }) => (
    <div className="flex items-center justify-between p-3 border dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800">
      <div className="flex items-center gap-3">
        <div className="size-8 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
          <Mail className="size-4 text-blue-600" />
        </div>
        <div>
          <div className="text-sm font-medium">{label}</div>
          {sublabel && <div className="text-xs text-gray-500">{sublabel}</div>}
          <div className="text-xs text-green-600 font-medium">● Active</div>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {onSync && (
          <Button
            size="sm"
            variant="outline"
            disabled={syncingId === id}
            onClick={onSync}
            title="Manually trigger inbox sync now"
          >
            {syncingId === id
              ? <Loader2 className="size-4 animate-spin" />
              : <><RefreshCw className="size-4 mr-1.5" />Sync Now</>}
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          className="text-red-600 border-red-200 hover:bg-red-50"
          disabled={disconnectingId === id}
          onClick={onDisconnect}
        >
          {disconnectingId === id
            ? <Loader2 className="size-4 animate-spin" />
            : <><Trash2 className="size-4 mr-1.5" />Disconnect</>}
        </Button>
      </div>
    </div>
  );

  const LockedPanel = ({ plan = "Max+" }: { plan?: string }) => (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Lock className="size-10 text-gray-300 mb-3" />
      <p className="text-gray-600 font-medium">Available on {plan} plans</p>
      <p className="text-sm text-gray-500 mb-4">Upgrade your plan to unlock this integration.</p>
      <Button onClick={() => window.location.href = "/app/billing"}>View Plans</Button>
    </div>
  );

  // ── Tab definitions ────────────────────────────────────────────────────────

  const tabs = [
    { value: "gmail",    label: "Gmail",        icon: Mail,           count: gmailInboxes.length },
    { value: "imap",     label: "Email (IMAP)",  icon: Mail,           count: imapInboxes.length },
    { value: "whatsapp", label: "WhatsApp",      icon: MessageSquare,  count: waConns.length },
    { value: "widget",   label: "Live Chat",     icon: Globe,          count: null },
    { value: "instagram",label: "Instagram",     icon: Instagram,      locked: !isPaidPlan },
    { value: "reviews",  label: "Google Reviews",icon: Star,           locked: !isPaidPlan },
    { value: "api",      label: "REST API",      icon: Globe,          count: null },
  ] as const;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Connections</h1>
        <p className="text-gray-600">Connect channels to ingest complaints</p>
      </div>

      <Tabs defaultValue="gmail" className="w-full">
        {/* Horizontal pill tab bar */}
        <TabsList className="h-auto bg-gray-100 dark:bg-gray-800 p-1 rounded-lg w-full flex flex-wrap gap-1 justify-start">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors text-gray-500 dark:text-gray-400 data-[state=active]:bg-white dark:data-[state=active]:bg-gray-700 data-[state=active]:text-gray-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm hover:text-gray-700 dark:hover:text-gray-200"
              >
                <Icon className="size-4 shrink-0" />
                <span>{tab.label}</span>
                {"count" in tab && tab.count != null && tab.count > 0 && (
                  <Badge className="size-5 p-0 text-xs justify-center rounded-full bg-blue-100 text-blue-700 border-0">
                    {tab.count}
                  </Badge>
                )}
                {"locked" in tab && tab.locked && (
                  <Lock className="size-3 text-gray-400" />
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>

        {/* ── Gmail ── */}
        <TabsContent value="gmail" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Gmail Accounts</CardTitle>
                <Button size="sm" onClick={handleConnectGmail} disabled={connectingGmail}>
                  {connectingGmail
                    ? <><Loader2 className="size-4 mr-2 animate-spin" />Redirecting…</>
                    : <><Plus className="size-4 mr-2" />Connect Gmail</>}
                </Button>
              </div>
              <p className="text-sm text-gray-500">
                Authorize via Google OAuth. New emails arriving in the inbox are automatically ingested as complaints.
              </p>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
                  <Loader2 className="size-4 animate-spin" /> Loading…
                </div>
              ) : gmailInboxes.length === 0 ? (
                <div className="text-center py-8">
                  <Mail className="size-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No Gmail accounts connected yet.</p>
                  <Button className="mt-4" onClick={handleConnectGmail} disabled={connectingGmail}>
                    <Plus className="size-4 mr-2" />Connect your first Gmail account
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {gmailInboxes.map((inbox) => (
                    <InboxRow
                      key={inbox.id}
                      id={inbox.id}
                      label={inbox.email}
                      sublabel="Gmail OAuth"
                      onDisconnect={() => handleDisconnectInbox(inbox.id, inbox.email)}
                      onSync={() => handleSyncInbox(inbox.id, inbox.email)}
                    />
                  ))}
                  <Button variant="outline" size="sm" className="mt-2" onClick={handleConnectGmail} disabled={connectingGmail}>
                    <Plus className="size-4 mr-2" />Add another Gmail account
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── IMAP ── */}
        <TabsContent value="imap" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Email (IMAP) Accounts</CardTitle>
                <Button size="sm" variant="outline" onClick={() => setShowImapDialog(true)}>
                  <Plus className="size-4 mr-2" />Add Account
                </Button>
              </div>
              <p className="text-sm text-gray-500">
                Works with any IMAP mailbox — Outlook, Yahoo, Zoho, custom SMTP, etc.
              </p>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
                  <Loader2 className="size-4 animate-spin" /> Loading…
                </div>
              ) : imapInboxes.length === 0 ? (
                <div className="text-center py-8">
                  <Mail className="size-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No IMAP accounts connected yet.</p>
                  <Button className="mt-4" variant="outline" onClick={() => setShowImapDialog(true)}>
                    <Plus className="size-4 mr-2" />Add IMAP account
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {imapInboxes.map((inbox) => (
                    <InboxRow
                      key={inbox.id}
                      id={inbox.id}
                      label={inbox.email}
                      sublabel="IMAP"
                      onDisconnect={() => handleDisconnectInbox(inbox.id, inbox.email)}
                    />
                  ))}
                  <Button variant="outline" size="sm" className="mt-2" onClick={() => setShowImapDialog(true)}>
                    <Plus className="size-4 mr-2" />Add another account
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── WhatsApp ── */}
        <TabsContent value="whatsapp" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>WhatsApp Business Accounts</CardTitle>
                <Button size="sm" onClick={() => setShowWaDialog(true)}>
                  <Plus className="size-4 mr-2" />Add Number
                </Button>
              </div>
              <p className="text-sm text-gray-500">
                Connect via Meta Business API. Each phone number becomes a separate inbox.
              </p>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
                  <Loader2 className="size-4 animate-spin" /> Loading…
                </div>
              ) : waConns.length === 0 ? (
                <div className="text-center py-8">
                  <MessageSquare className="size-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No WhatsApp numbers connected yet.</p>
                  <Button className="mt-4" onClick={() => setShowWaDialog(true)}>
                    <Plus className="size-4 mr-2" />Connect a WhatsApp number
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {waConns.map((conn) => (
                    <div key={conn.id} className="flex items-center justify-between p-3 border dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800">
                      <div className="flex items-center gap-3">
                        <div className="size-8 bg-green-100 rounded-full flex items-center justify-center shrink-0">
                          <MessageSquare className="size-4 text-green-600" />
                        </div>
                        <div>
                          <div className="text-sm font-medium">
                            {conn.account_identifier || (conn.metadata?.phone_number_id as string) || "Unknown"}
                          </div>
                          <div className="text-xs text-gray-500">Phone Number ID</div>
                          <div className="text-xs text-green-600 font-medium">● Active</div>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-red-600 border-red-200 hover:bg-red-50 shrink-0"
                        disabled={disconnectingId === conn.id}
                        onClick={() => handleDisconnectChannel(conn.id, conn.account_identifier || "number")}
                      >
                        {disconnectingId === conn.id
                          ? <Loader2 className="size-4 animate-spin" />
                          : <><Trash2 className="size-4 mr-1.5" />Disconnect</>}
                      </Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" className="mt-2" onClick={() => setShowWaDialog(true)}>
                    <Plus className="size-4 mr-2" />Add another number
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Webhook config reference */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Meta Webhook Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-gray-500">
                In Meta Business Manager → WhatsApp → Configuration, set these values:
              </p>
              <div>
                <Label className="text-xs text-gray-500">Webhook URL</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={waWebhookUrl} readOnly className="text-sm font-mono" />
                  <Button variant="outline" size="icon" onClick={() => copy(waWebhookUrl, "Webhook URL copied!")}>
                    <Copy className="size-4" />
                  </Button>
                </div>
              </div>
              <div>
                <Label className="text-xs text-gray-500">Verify Token</Label>
                <div className="flex gap-2 mt-1">
                  <Input value="(set WHATSAPP_VERIFY_TOKEN in your env)" readOnly className="text-sm text-gray-400" />
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Set the same value you put in <code className="bg-gray-100 px-1 rounded">WHATSAPP_VERIFY_TOKEN</code> environment variable.
                </p>
              </div>
              <a
                href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
              >
                Meta Cloud API Setup Guide <ExternalLink className="size-3" />
              </a>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Live Chat Widget ── */}
        <TabsContent value="widget" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Live Chat Widget</CardTitle>
              <p className="text-sm text-gray-500">
                Embed this script on your website to enable the SynapFlow chat widget.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>API Key</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    value={loading ? "Loading…" : showApiKey ? apiKey : maskedKey}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button variant="outline" size="icon" onClick={() => setShowApiKey((v) => !v)}>
                    {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => copy(apiKey, "API key copied!")} disabled={!apiKey}>
                    <Copy className="size-4" />
                  </Button>
                </div>
              </div>
              <div>
                <Label>Embed Code</Label>
                <textarea
                  className="w-full mt-1 p-3 border rounded text-xs font-mono bg-gray-50 resize-none"
                  rows={3}
                  readOnly
                  value={`<script src="${window.location.origin}/widget.js" data-key="${apiKey || "YOUR_API_KEY"}"></script>`}
                />
              </div>
              <Button
                variant="outline"
                onClick={() => copy(
                  `<script src="${window.location.origin}/widget.js" data-key="${apiKey}"></script>`,
                  "Embed code copied!"
                )}
                disabled={!apiKey}
              >
                <Copy className="size-4 mr-2" />Copy Embed Code
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Instagram ── */}
        <TabsContent value="instagram" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Instagram DMs</CardTitle>
            </CardHeader>
            <CardContent>
              {isPaidPlan ? (
                <p className="text-sm text-gray-600">Instagram DM integration — coming soon.</p>
              ) : (
                <LockedPanel plan="Max+" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Google Reviews ── */}
        <TabsContent value="reviews" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Google Reviews</CardTitle>
            </CardHeader>
            <CardContent>
              {isPaidPlan ? (
                <p className="text-sm text-gray-600">Google Reviews integration — coming soon.</p>
              ) : (
                <LockedPanel plan="Max+" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── REST API ── */}
        <TabsContent value="api" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>REST API</CardTitle>
                <Badge variant="outline">Always Active</Badge>
              </div>
              <p className="text-sm text-gray-500">
                POST complaints directly to the API from any system.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>API Key</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    value={loading ? "Loading…" : showApiKey ? apiKey : maskedKey}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button variant="outline" size="icon" onClick={() => setShowApiKey((v) => !v)}>
                    {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => copy(apiKey, "API key copied!")} disabled={!apiKey}>
                    <Copy className="size-4" />
                  </Button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Send as <code className="bg-gray-100 px-1 rounded">x-api-key</code> header.
                </p>
              </div>
              <div>
                <Label>Webhook Endpoint</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={webhookUrl} readOnly className="text-sm" />
                  <Button variant="outline" size="icon" onClick={() => copy(webhookUrl, "Webhook URL copied!")}>
                    <Copy className="size-4" />
                  </Button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  POST a JSON body with <code className="bg-gray-100 px-1 rounded">summary</code>, <code className="bg-gray-100 px-1 rounded">customer_name</code>, <code className="bg-gray-100 px-1 rounded">customer_email</code>.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── IMAP Dialog ── */}
      <Dialog open={showImapDialog} onOpenChange={setShowImapDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Connect IMAP Account</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleConnectImap} className="space-y-4 pt-2">
            <div>
              <Label>Email Address</Label>
              <Input type="email" placeholder="support@yourcompany.com" value={imapForm.email}
                onChange={(e) => setImapForm((f) => ({ ...f, email: e.target.value }))} required />
            </div>
            <div>
              <Label>Password / App Password</Label>
              <Input type="password" placeholder="App-specific password recommended" value={imapForm.password}
                onChange={(e) => setImapForm((f) => ({ ...f, password: e.target.value }))} required />
            </div>
            <div>
              <Label>IMAP Host <span className="text-gray-400 text-xs font-normal">(auto-detected for Gmail/Outlook/Yahoo)</span></Label>
              <Input placeholder="imap.yourprovider.com" value={imapForm.host}
                onChange={(e) => setImapForm((f) => ({ ...f, host: e.target.value }))} />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <Label>Port</Label>
                <Input type="number" value={imapForm.port}
                  onChange={(e) => setImapForm((f) => ({ ...f, port: e.target.value }))} />
              </div>
              <div className="flex-1 flex flex-col justify-end pb-1">
                <div className="flex items-center gap-2">
                  <input type="checkbox" id="imap_ssl" checked={imapForm.use_ssl}
                    onChange={(e) => setImapForm((f) => ({ ...f, use_ssl: e.target.checked }))} className="rounded" />
                  <label htmlFor="imap_ssl" className="text-sm">Use SSL/TLS</label>
                </div>
              </div>
            </div>
            <div className="flex gap-3 pt-1">
              <Button type="submit" disabled={connectingImap} className="flex-1">
                {connectingImap ? <><Loader2 className="size-4 mr-2 animate-spin" />Testing…</> : "Connect"}
              </Button>
              <Button type="button" variant="outline" onClick={() => setShowImapDialog(false)}>Cancel</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── WhatsApp Dialog ── */}
      <Dialog open={showWaDialog} onOpenChange={setShowWaDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Connect WhatsApp Number</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-gray-500 -mt-2">
            Get these values from{" "}
            <a href="https://business.facebook.com/" target="_blank" rel="noreferrer" className="text-blue-600 underline">
              Meta Business Manager
            </a>{" "}
            → WhatsApp → API Setup.
          </p>
          <form onSubmit={handleConnectWhatsApp} className="space-y-4 pt-2">
            <div>
              <Label>Phone Number ID <span className="text-red-500">*</span></Label>
              <Input placeholder="e.g. 123456789012345" value={waForm.phone_number_id}
                onChange={(e) => setWaForm((f) => ({ ...f, phone_number_id: e.target.value }))} required />
            </div>
            <div>
              <Label>Access Token <span className="text-red-500">*</span></Label>
              <Input type="password" placeholder="System user access token" value={waForm.access_token}
                onChange={(e) => setWaForm((f) => ({ ...f, access_token: e.target.value }))} required />
            </div>
            <div>
              <Label>Business Account ID <span className="text-gray-400 text-xs font-normal">(optional)</span></Label>
              <Input placeholder="e.g. 987654321098765" value={waForm.business_account_id}
                onChange={(e) => setWaForm((f) => ({ ...f, business_account_id: e.target.value }))} />
            </div>
            <div className="flex gap-3 pt-1">
              <Button type="submit" disabled={connectingWa} className="flex-1">
                {connectingWa ? <><Loader2 className="size-4 mr-2 animate-spin" />Connecting…</> : "Connect"}
              </Button>
              <Button type="button" variant="outline" onClick={() => setShowWaDialog(false)}>Cancel</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

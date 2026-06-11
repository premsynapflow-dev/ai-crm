import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import {
  Mail, MessageSquare, Globe, Instagram, Star, Copy, Plus, Trash2,
  Loader2, Eye, EyeOff, Lock, ExternalLink, RefreshCw,
  Building2, ShoppingBag, Play, Facebook, Phone, FileUp,
  Zap, ChevronRight, IndianRupee, CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth-context";

interface Inbox {
  id: string; email: string; provider: string; status: string;
  needs_reauth: boolean; last_poll_error: string | null;
  last_poll_error_at: string | null; last_synced_at: string | null;
}
interface ChannelConn {
  id: string; channel_type: string; account_identifier: string | null;
  status: string; metadata: Record<string, unknown>;
}

// ── shared: existing connection row ──────────────────────────────────────────
function ConnRow({
  conn, iconBg, icon: Icon, label, sublabel, onDisconnect, disconnecting, onSync, syncing, onReconnect, reconnecting,
}: {
  conn: ChannelConn; iconBg: string; icon: any; label: string; sublabel?: string;
  onDisconnect: () => void; disconnecting: boolean; onSync?: () => void; syncing?: boolean;
  onReconnect?: () => void; reconnecting?: boolean;
}) {
  const isActive = conn.status === "active";
  return (
    <div className="flex items-center justify-between p-3 border dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800">
      <div className="flex items-center gap-3">
        <div className={`size-8 ${iconBg} rounded-full flex items-center justify-center shrink-0`}>
          <Icon className="size-4" />
        </div>
        <div>
          <div className="text-sm font-medium dark:text-white">{label}</div>
          {sublabel && <div className="text-xs text-gray-500">{sublabel}</div>}
          {isActive
            ? <div className="text-xs text-green-600 font-medium">● Active</div>
            : <div className="text-xs text-amber-600 font-medium">● Needs re-authorization</div>
          }
        </div>
      </div>
      <div className="flex gap-2 shrink-0">
        {!isActive && onReconnect && (
          <Button size="sm" variant="outline" className="text-amber-700 border-amber-300 hover:bg-amber-50" onClick={onReconnect} disabled={reconnecting}>
            {reconnecting ? <Loader2 className="size-4 animate-spin" /> : <><RefreshCw className="size-4 mr-1.5" />Reconnect</>}
          </Button>
        )}
        {isActive && onSync && (
          <Button size="sm" variant="outline" onClick={onSync} disabled={syncing}>
            {syncing ? <Loader2 className="size-4 animate-spin" /> : <><RefreshCw className="size-4 mr-1.5" />Sync</>}
          </Button>
        )}
        <Button size="sm" variant="outline" className="text-red-600 border-red-200 hover:bg-red-50"
          onClick={onDisconnect} disabled={disconnecting}>
          {disconnecting ? <Loader2 className="size-4 animate-spin" /> : <><Trash2 className="size-4 mr-1.5" />Disconnect</>}
        </Button>
      </div>
    </div>
  );
}

// ── locked panel ──────────────────────────────────────────────────────────────
function LockedPanel({ plan = "Max+" }: { plan?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Lock className="size-10 text-gray-300 mb-3" />
      <p className="text-gray-600 dark:text-gray-300 font-medium">Available on {plan} plans</p>
      <p className="text-sm text-gray-500 mb-4">Upgrade to unlock this integration.</p>
      <Button onClick={() => window.location.href = "/app/billing"}>View Plans</Button>
    </div>
  );
}

// ── generic credential form ───────────────────────────────────────────────────
interface Field { key: string; label: string; placeholder?: string; type?: string; hint?: string; }

function CredentialForm({
  title, fields, channelType, accountField, metaFields, onSuccess,
}: {
  title: string;
  fields: Field[];
  channelType: string;
  accountField?: string;
  metaFields?: Field[];
  onSuccess: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const set = (k: string, v: string) => setValues((p) => ({ ...p, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const credentials: Record<string, string> = {};
      const metadata: Record<string, string> = {};
      fields.forEach((f) => { credentials[f.key] = values[f.key] || ""; });
      metaFields?.forEach((f) => { metadata[f.key] = values[f.key] || ""; });
      await api.channels.connect({
        channel_type: channelType,
        account_identifier: accountField ? values[accountField] : undefined,
        credentials,
        metadata,
      });
      toast.success(`${title} connected successfully!`);
      setValues({});
      onSuccess();
    } catch (err: any) {
      toast.error(err?.message || "Connection failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {[...fields, ...(metaFields || [])].map((f) => (
        <div key={f.key}>
          <Label className="text-sm">{f.label}</Label>
          <Input
            type={f.type || "text"}
            placeholder={f.placeholder}
            value={values[f.key] || ""}
            onChange={(e) => set(f.key, e.target.value)}
            required={f.type !== "optional" as any}
            className="mt-1"
          />
          {f.hint && <p className="text-xs text-gray-400 mt-0.5">{f.hint}</p>}
        </div>
      ))}
      <Button type="submit" disabled={saving} className="w-full mt-2">
        {saving ? <><Loader2 className="size-4 mr-2 animate-spin" />Connecting…</> : `Connect ${title}`}
      </Button>
    </form>
  );
}

// ── connector tab panel ───────────────────────────────────────────────────────
function ConnectorPanel({
  channelType, title, icon: Icon, iconBg, iconColor, description, credFields, accountField, metaFields,
  existing, onDisconnect, disconnectingId, onRefresh, docsUrl, isPaidRequired, isPaid, extraContent,
}: {
  channelType: string; title: string; icon: any; iconBg: string; iconColor: string;
  description: string; credFields: Field[]; accountField?: string; metaFields?: Field[];
  existing: ChannelConn[]; onDisconnect: (id: string, label: string) => void;
  disconnectingId: string | null; onRefresh: () => void; docsUrl?: string;
  isPaidRequired?: boolean; isPaid?: boolean; extraContent?: React.ReactNode;
}) {
  if (isPaidRequired && !isPaid) return <LockedPanel plan="Max+" />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 dark:text-white">
              <div className={`size-8 ${iconBg} rounded-full flex items-center justify-center`}>
                <Icon className={`size-4 ${iconColor}`} />
              </div>
              {title}
            </CardTitle>
            {existing.length > 0 && (
              <Badge variant="outline" className="text-green-600 border-green-300">
                {existing.length} connected
              </Badge>
            )}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
          {docsUrl && (
            <a href={docsUrl} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
              Setup Guide <ExternalLink className="size-3" />
            </a>
          )}
        </CardHeader>
        <CardContent>
          {/* Existing connections */}
          {existing.length > 0 && (
            <div className="space-y-2 mb-4">
              {existing.map((conn) => (
                <ConnRow
                  key={conn.id}
                  conn={conn}
                  iconBg={iconBg}
                  icon={Icon}
                  label={conn.account_identifier || title}
                  sublabel={channelType}
                  onDisconnect={() => onDisconnect(conn.id, conn.account_identifier || title)}
                  disconnecting={disconnectingId === conn.id}
                />
              ))}
            </div>
          )}

          {/* Connect form */}
          {credFields.length > 0 && (
            <div className={existing.length > 0 ? "pt-4 border-t dark:border-gray-700" : ""}>
              <p className="text-sm font-medium mb-3 dark:text-gray-300">
                {existing.length > 0 ? "Add another account" : "Connect your account"}
              </p>
              <CredentialForm
                title={title}
                fields={credFields}
                channelType={channelType}
                accountField={accountField}
                metaFields={metaFields}
                onSuccess={onRefresh}
              />
            </div>
          )}

          {extraContent}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Revenue Sync Panel ────────────────────────────────────────────────────────
function RevenueSyncPanel({
  stripeConns, razorpayConns, onDisconnect, disconnectingId, onRefresh,
}: {
  stripeConns: ChannelConn[]; razorpayConns: ChannelConn[];
  onDisconnect: (id: string, label: string) => void;
  disconnectingId: string | null; onRefresh: () => void;
}) {
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<{ updated: number; at: string } | null>(null);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await api.revenueSync.trigger();
      setSyncResult({ updated: result.total_customers_updated, at: result.synced_at || new Date().toISOString() });
      toast.success(`Revenue sync complete — ${result.total_customers_updated} customer(s) updated`);
    } catch (err: any) {
      toast.error(err?.message || "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const hasAny = stripeConns.length > 0 || razorpayConns.length > 0;

  return (
    <>
      {/* Info banner */}
      <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-900">
        <CardContent className="p-4 flex gap-3 items-start">
          <IndianRupee className="size-5 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
              Connect your revenue data for accurate Risk Analysis
            </p>
            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
              Connecting Stripe or Razorpay lets SynapFlow calculate real Revenue at Risk using
              actual customer lifetime spend — not ticket-count estimates. Customer data is only
              read, never written. Credentials are stored encrypted at rest.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Stripe */}
      <ConnectorPanel
        channelType="stripe_revenue"
        title="Stripe"
        icon={IndianRupee}
        iconBg="bg-purple-100"
        iconColor="text-purple-600"
        description="Pull actual customer lifetime revenue from Stripe. SynapFlow queries each customer by email and sums all successful charge amounts."
        docsUrl="https://dashboard.stripe.com/apikeys"
        credFields={[
          { key: "api_key", label: "Stripe Secret Key", placeholder: "sk_live_…", type: "password", hint: "Dashboard → Developers → API Keys → Secret key. Use a restricted key with Charges: Read and Customers: Read permissions." },
        ]}
        accountField="api_key"
        existing={stripeConns}
        onDisconnect={onDisconnect}
        disconnectingId={disconnectingId}
        onRefresh={onRefresh}
      />

      {/* Razorpay */}
      <ConnectorPanel
        channelType="razorpay_revenue"
        title="Razorpay"
        icon={IndianRupee}
        iconBg="bg-blue-100"
        iconColor="text-blue-600"
        description="Pull customer payment history from your Razorpay account. SynapFlow fetches captured payments and matches them to your customers by email."
        docsUrl="https://dashboard.razorpay.com/app/keys"
        credFields={[
          { key: "key_id", label: "Key ID", placeholder: "rzp_live_…", hint: "Dashboard → Settings → API Keys → Key ID" },
          { key: "key_secret", label: "Key Secret", placeholder: "…", type: "password", hint: "Dashboard → Settings → API Keys → Key Secret" },
        ]}
        accountField="key_id"
        existing={razorpayConns}
        onDisconnect={onDisconnect}
        disconnectingId={disconnectingId}
        onRefresh={onRefresh}
      />

      {/* Sync trigger */}
      {hasAny && (
        <Card>
          <CardContent className="p-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium dark:text-white">Sync Customer Revenue</p>
              <p className="text-xs text-gray-500">
                Fetches the latest payment totals and updates actual customer values.
                {syncResult && (
                  <span className="ml-2 text-green-600">
                    Last sync: {syncResult.updated} updated · {new Date(syncResult.at).toLocaleTimeString()}
                  </span>
                )}
              </p>
            </div>
            <Button onClick={handleSync} disabled={syncing}>
              {syncing
                ? <><Loader2 className="size-4 mr-2 animate-spin" />Syncing…</>
                : <><RefreshCw className="size-4 mr-2" />Sync Now</>}
            </Button>
          </CardContent>
        </Card>
      )}
    </>
  );
}

// ── main component ────────────────────────────────────────────────────────────
export function SettingsConnections() {
  const { user } = useAuth();
  const location = useLocation();

  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [inboxes, setInboxes] = useState<Inbox[]>([]);
  const [channelConns, setChannelConns] = useState<ChannelConn[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [showImapDialog, setShowImapDialog] = useState(false);
  const [imapForm, setImapForm] = useState({ email: "", password: "", host: "", port: "993", use_ssl: true });
  const [connectingImap, setConnectingImap] = useState(false);
  const [showWaDialog, setShowWaDialog] = useState(false);
  const [waForm, setWaForm] = useState({ phone_number_id: "", access_token: "", business_account_id: "" });
  const [connectingWa, setConnectingWa] = useState(false);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const webhookUrl = `${window.location.origin}/webhook/complaints`;
  const waWebhookUrl = `${window.location.origin}/webhooks/whatsapp`;
  const maskedKey = apiKey ? apiKey.slice(0, 8) + "•".repeat(Math.max(0, apiKey.length - 8)) : "";
  const isPaid = ["max", "scale", "enterprise"].includes(user?.plan?.toLowerCase() || "");

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
        api.settings.get(), api.inboxes.list(), api.channels.list(),
      ]);
      setApiKey(settings.api_key || "");
      setInboxes(inboxList);
      setChannelConns(connList);
    } catch { toast.error("Failed to load connections."); }
    finally { setLoading(false); }
  };

  const copy = (text: string, label = "Copied!") => { navigator.clipboard.writeText(text); toast.success(label); };

  const handleConnectGmail = async () => {
    setConnectingGmail(true);
    try { const { connect_url } = await api.inboxes.getGmailConnectUrl(); window.location.href = connect_url; }
    catch { toast.error("Could not start Gmail OAuth."); setConnectingGmail(false); }
  };

  const handleSyncInbox = async (id: string) => {
    setSyncingId(id);
    try {
      const result = await api.inboxes.poll(id);
      if (result.error) toast.error(`Sync failed: ${result.error}`);
      else if (result.result) {
        const { fetched, processed } = result.result;
        toast.success(fetched === 0 ? "No new messages." : `Synced: ${fetched} fetched, ${processed} new.`);
      }
    } catch { toast.error("Sync failed."); }
    finally { setSyncingId(null); }
  };

  const handleDisconnectInbox = async (id: string, email: string) => {
    setDisconnectingId(id);
    try { await api.inboxes.disconnect(id); setInboxes((p) => p.filter((i) => i.id !== id)); toast.success(`Disconnected ${email}`); }
    catch { toast.error("Failed to disconnect."); }
    finally { setDisconnectingId(null); }
  };

  const handleConnectImap = async (e: React.FormEvent) => {
    e.preventDefault(); setConnectingImap(true);
    try {
      const inbox = await api.inboxes.connectImap({
        email: imapForm.email, password: imapForm.password,
        host: imapForm.host || undefined, port: parseInt(imapForm.port) || 993, use_ssl: imapForm.use_ssl,
      });
      setInboxes((p) => [...p, inbox]); setShowImapDialog(false);
      setImapForm({ email: "", password: "", host: "", port: "993", use_ssl: true });
      toast.success(`Connected ${inbox.email}`);
    } catch (err: any) { toast.error(err?.message || "Connection failed"); }
    finally { setConnectingImap(false); }
  };

  const handleConnectWhatsApp = async (e: React.FormEvent) => {
    e.preventDefault(); setConnectingWa(true);
    try {
      await api.channels.connectWhatsApp({ phone_number_id: waForm.phone_number_id, access_token: waForm.access_token, business_account_id: waForm.business_account_id || undefined });
      await loadAll(); setShowWaDialog(false);
      setWaForm({ phone_number_id: "", access_token: "", business_account_id: "" });
      toast.success("WhatsApp connected!");
    } catch (err: any) { toast.error(err?.message || "Connection failed"); }
    finally { setConnectingWa(false); }
  };

  const handleDisconnectChannel = async (id: string, label: string) => {
    setDisconnectingId(id);
    try { await api.channels.disconnect(id); setChannelConns((p) => p.filter((c) => c.id !== id)); toast.success(`Disconnected ${label}`); }
    catch { toast.error("Failed to disconnect."); }
    finally { setDisconnectingId(null); }
  };

  const connsOf = (type: string) => channelConns.filter((c) => c.channel_type === type);
  const gmailInboxes = inboxes.filter((i) => i.provider === "gmail");
  const imapInboxes = inboxes.filter((i) => i.provider === "imap");
  const waConns = connsOf("whatsapp");

  // Tab definitions
  type TabDef = {
    value: string; label: string; icon: any;
    count?: number; locked?: boolean;
  };

  const tabs: TabDef[] = [
    { value: "revenue",    label: "Revenue Data",   icon: IndianRupee, count: (connsOf("stripe_revenue").length + connsOf("razorpay_revenue").length) || undefined },
    { value: "gmail",      label: "Gmail",          icon: Mail,        count: gmailInboxes.length },
    { value: "imap",       label: "Email (IMAP)",    icon: Mail,        count: imapInboxes.length },
    { value: "whatsapp",   label: "WhatsApp",        icon: MessageSquare, count: waConns.length },
    { value: "widget",     label: "Live Chat",       icon: Globe },
    { value: "instagram",  label: "Instagram",       icon: Instagram,   count: connsOf("instagram").length, locked: !isPaid },
    { value: "facebook",   label: "Facebook",        icon: Facebook,    count: connsOf("facebook").length,  locked: !isPaid },
    { value: "reviews",    label: "Google Reviews",  icon: Star,        count: connsOf("google_reviews").length, locked: !isPaid },
    { value: "trustpilot", label: "Trustpilot",      icon: Star,        count: connsOf("trustpilot").length, locked: !isPaid },
    { value: "appstore",   label: "App Store",       icon: ShoppingBag, count: connsOf("app_store").length, locked: !isPaid },
    { value: "playstore",  label: "Play Store",      icon: Play,        count: connsOf("play_store").length, locked: !isPaid },
    { value: "zendesk",    label: "Zendesk",         icon: Building2,   count: connsOf("zendesk").length,   locked: !isPaid },
    { value: "freshdesk",  label: "Freshdesk",       icon: Building2,   count: connsOf("freshdesk").length, locked: !isPaid },
    { value: "intercom",   label: "Intercom",        icon: MessageSquare, count: connsOf("intercom").length, locked: !isPaid },
    { value: "hubspot",    label: "HubSpot",         icon: Zap,         count: connsOf("hubspot").length,   locked: !isPaid },
    { value: "salesforce", label: "Salesforce",      icon: Building2,   count: connsOf("salesforce").length, locked: !isPaid },
    { value: "outlook",    label: "Outlook",         icon: Mail,        count: connsOf("outlook").length,   locked: !isPaid },
    { value: "csv",        label: "CSV Import",      icon: FileUp },
    { value: "api",        label: "REST API",        icon: Globe },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold dark:text-white">Connections</h1>
        <p className="text-gray-600 dark:text-gray-400">Connect channels to ingest complaints</p>
      </div>

      <Tabs defaultValue="gmail" className="w-full">
        <TabsList className="h-auto bg-gray-100 dark:bg-gray-800 p-1 rounded-lg w-full flex flex-wrap gap-1 justify-start">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <TabsTrigger key={tab.value} value={tab.value}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors text-gray-500 dark:text-gray-400 data-[state=active]:bg-white dark:data-[state=active]:bg-gray-700 data-[state=active]:text-gray-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm hover:text-gray-700 dark:hover:text-gray-200">
                <Icon className="size-4 shrink-0" />
                <span>{tab.label}</span>
                {(tab.count ?? 0) > 0 && (
                  <Badge className="size-5 p-0 text-xs justify-center rounded-full bg-blue-100 text-blue-700 border-0">
                    {tab.count}
                  </Badge>
                )}
                {tab.locked && <Lock className="size-3 text-gray-400" />}
              </TabsTrigger>
            );
          })}
        </TabsList>

        {/* ── Revenue Data ── */}
        <TabsContent value="revenue" className="mt-6 space-y-4">
          <RevenueSyncPanel
            stripeConns={connsOf("stripe_revenue")}
            razorpayConns={connsOf("razorpay_revenue")}
            onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId}
            onRefresh={loadAll}
          />
        </TabsContent>

        {/* ── Gmail ── */}
        <TabsContent value="gmail" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="dark:text-white">Gmail Accounts</CardTitle>
                <Button size="sm" onClick={handleConnectGmail} disabled={connectingGmail}>
                  {connectingGmail ? <><Loader2 className="size-4 mr-2 animate-spin" />Redirecting…</> : <><Plus className="size-4 mr-2" />Connect Gmail</>}
                </Button>
              </div>
              <p className="text-sm text-gray-500">Authorize via Google OAuth. New emails are automatically ingested as complaints.</p>
            </CardHeader>
            <CardContent>
              {loading ? <div className="flex items-center gap-2 text-sm text-gray-400 py-4"><Loader2 className="size-4 animate-spin" /> Loading…</div>
                : gmailInboxes.length === 0 ? (
                  <div className="text-center py-8">
                    <Mail className="size-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 text-sm">No Gmail accounts connected yet.</p>
                    <Button className="mt-4" onClick={handleConnectGmail} disabled={connectingGmail}><Plus className="size-4 mr-2" />Connect Gmail</Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {gmailInboxes.map((inbox) => (
                      <ConnRow key={inbox.id} conn={{ id: inbox.id, channel_type: "gmail", account_identifier: inbox.email, status: inbox.status, metadata: {} }}
                        iconBg="bg-red-100" icon={Mail} iconColor="text-red-600"
                        label={inbox.email} sublabel="Gmail OAuth"
                        onDisconnect={() => handleDisconnectInbox(inbox.id, inbox.email)}
                        disconnecting={disconnectingId === inbox.id}
                        onSync={() => handleSyncInbox(inbox.id)} syncing={syncingId === inbox.id}
                        onReconnect={handleConnectGmail} reconnecting={connectingGmail} />
                    ))}
                    <Button variant="outline" size="sm" className="mt-2" onClick={handleConnectGmail} disabled={connectingGmail}><Plus className="size-4 mr-2" />Add account</Button>
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
                <CardTitle className="dark:text-white">Email (IMAP) Accounts</CardTitle>
                <Button size="sm" variant="outline" onClick={() => setShowImapDialog(true)}><Plus className="size-4 mr-2" />Add Account</Button>
              </div>
              <p className="text-sm text-gray-500">Works with any IMAP mailbox — Outlook, Yahoo, Zoho, custom SMTP.</p>
            </CardHeader>
            <CardContent>
              {loading ? <div className="flex items-center gap-2 text-sm text-gray-400 py-4"><Loader2 className="size-4 animate-spin" /> Loading…</div>
                : imapInboxes.length === 0 ? (
                  <div className="text-center py-8">
                    <Mail className="size-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 text-sm">No IMAP accounts connected.</p>
                    <Button className="mt-4" variant="outline" onClick={() => setShowImapDialog(true)}><Plus className="size-4 mr-2" />Add IMAP account</Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {imapInboxes.map((inbox) => (
                      <ConnRow key={inbox.id} conn={{ id: inbox.id, channel_type: "imap", account_identifier: inbox.email, status: inbox.status, metadata: {} }}
                        iconBg="bg-blue-100" icon={Mail} iconColor="text-blue-600"
                        label={inbox.email} sublabel="IMAP"
                        onDisconnect={() => handleDisconnectInbox(inbox.id, inbox.email)}
                        disconnecting={disconnectingId === inbox.id} />
                    ))}
                    <Button variant="outline" size="sm" className="mt-2" onClick={() => setShowImapDialog(true)}><Plus className="size-4 mr-2" />Add account</Button>
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
                <CardTitle className="dark:text-white">WhatsApp Business</CardTitle>
                <Button size="sm" onClick={() => setShowWaDialog(true)}><Plus className="size-4 mr-2" />Add Number</Button>
              </div>
              <p className="text-sm text-gray-500">Connect via Meta Business API. Each phone number is a separate inbox.</p>
            </CardHeader>
            <CardContent>
              {waConns.length === 0 ? (
                <div className="text-center py-8">
                  <MessageSquare className="size-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No WhatsApp numbers connected.</p>
                  <Button className="mt-4" onClick={() => setShowWaDialog(true)}><Plus className="size-4 mr-2" />Connect number</Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {waConns.map((conn) => (
                    <ConnRow key={conn.id} conn={conn} iconBg="bg-green-100" icon={MessageSquare} iconColor="text-green-600"
                      label={conn.account_identifier || "WhatsApp"} sublabel="Phone Number ID"
                      onDisconnect={() => handleDisconnectChannel(conn.id, conn.account_identifier || "number")}
                      disconnecting={disconnectingId === conn.id} />
                  ))}
                  <Button variant="outline" size="sm" className="mt-2" onClick={() => setShowWaDialog(true)}><Plus className="size-4 mr-2" />Add number</Button>
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base dark:text-white">Meta Webhook Configuration</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-gray-500">In Meta Business Manager → WhatsApp → Configuration:</p>
              <div>
                <Label className="text-xs text-gray-500">Webhook URL</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={waWebhookUrl} readOnly className="text-sm font-mono" />
                  <Button variant="outline" size="icon" onClick={() => copy(waWebhookUrl, "Copied!")}><Copy className="size-4" /></Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Live Chat Widget ── */}
        <TabsContent value="widget" className="mt-6">
          <Card>
            <CardHeader><CardTitle className="dark:text-white">Live Chat Widget</CardTitle>
              <p className="text-sm text-gray-500">Embed on your website to capture visitor complaints in real-time.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>API Key</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={loading ? "Loading…" : showApiKey ? apiKey : maskedKey} readOnly className="font-mono text-sm" />
                  <Button variant="outline" size="icon" onClick={() => setShowApiKey((v) => !v)}>{showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</Button>
                  <Button variant="outline" size="icon" onClick={() => copy(apiKey, "API key copied!")} disabled={!apiKey}><Copy className="size-4" /></Button>
                </div>
              </div>
              <div>
                <Label>Embed Code</Label>
                <textarea className="w-full mt-1 p-3 border rounded text-xs font-mono bg-gray-50 dark:bg-gray-800 resize-none dark:text-gray-300" rows={3} readOnly
                  value={`<script src="${window.location.origin}/widget.js" data-key="${apiKey || "YOUR_API_KEY"}"></script>`} />
              </div>
              <Button variant="outline" onClick={() => copy(`<script src="${window.location.origin}/widget.js" data-key="${apiKey}"></script>`, "Embed code copied!")} disabled={!apiKey}>
                <Copy className="size-4 mr-2" />Copy Embed Code
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Instagram ── */}
        <TabsContent value="instagram" className="mt-6">
          <ConnectorPanel channelType="instagram" title="Instagram DMs" icon={Instagram}
            iconBg="bg-pink-100" iconColor="text-pink-600"
            description="Receive Instagram Direct Messages as complaints. Requires a Facebook Business account with Instagram Professional account linked."
            docsUrl="https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/get-started"
            credFields={[
              { key: "access_token", label: "Page Access Token", placeholder: "EAAxxxxxx…", type: "password", hint: "From Meta Business Manager → Instagram → Generate Token" },
            ]}
            metaFields={[{ key: "page_id", label: "Page ID", placeholder: "123456789", hint: "Your Instagram Professional Account page ID" }]}
            accountField="page_id"
            existing={connsOf("instagram")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Facebook ── */}
        <TabsContent value="facebook" className="mt-6">
          <ConnectorPanel channelType="facebook" title="Facebook Page Reviews" icon={Facebook}
            iconBg="bg-blue-100" iconColor="text-blue-600"
            description="Pull Facebook Page star ratings and reviews. Negative reviews become complaints automatically."
            docsUrl="https://developers.facebook.com/docs/graph-api/reference/page/ratings"
            credFields={[
              { key: "access_token", label: "Page Access Token", placeholder: "EAAxxxxxx…", type: "password", hint: "Long-lived Page Access Token from Meta Business Manager" },
            ]}
            metaFields={[{ key: "page_id", label: "Facebook Page ID", placeholder: "123456789" }]}
            accountField="page_id"
            existing={connsOf("facebook")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Google Reviews ── */}
        <TabsContent value="reviews" className="mt-6">
          <ConnectorPanel channelType="google_reviews" title="Google My Business Reviews" icon={Star}
            iconBg="bg-yellow-100" iconColor="text-yellow-600"
            description="Poll Google My Business reviews. Low-star reviews are ingested as complaints with urgency scores based on star rating."
            docsUrl="https://developers.google.com/my-business/reference/rest/v4/accounts.locations.reviews"
            credFields={[
              { key: "access_token", label: "OAuth Access Token", placeholder: "ya29.xxx…", type: "password", hint: "Google My Business OAuth token with mybusiness.readonly scope" },
              { key: "refresh_token", label: "Refresh Token", placeholder: "1//xxx…", type: "password" },
            ]}
            metaFields={[
              { key: "account_id", label: "Account ID", placeholder: "accounts/123456789" },
              { key: "location_id", label: "Location ID", placeholder: "locations/987654321" },
            ]}
            accountField="location_id"
            existing={connsOf("google_reviews")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Trustpilot ── */}
        <TabsContent value="trustpilot" className="mt-6">
          <ConnectorPanel channelType="trustpilot" title="Trustpilot" icon={Star}
            iconBg="bg-green-100" iconColor="text-green-600"
            description="Pull Trustpilot reviews for your business unit. Reviews below 3 stars become high-priority complaints."
            docsUrl="https://documentation.trustpilot.com/consumer-api/consumer-api-overview"
            credFields={[
              { key: "api_key", label: "Trustpilot API Key", placeholder: "xxxx-xxxx-xxxx", type: "password", hint: "From Trustpilot Business → Integrations → API" },
            ]}
            metaFields={[{ key: "business_unit_id", label: "Business Unit ID", placeholder: "64a1b2c3d4e5f6a7b8c9d0e1", hint: "Found in your Trustpilot business profile URL" }]}
            accountField="business_unit_id"
            existing={connsOf("trustpilot")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── App Store ── */}
        <TabsContent value="appstore" className="mt-6">
          <ConnectorPanel channelType="app_store" title="Apple App Store Reviews" icon={ShoppingBag}
            iconBg="bg-gray-100" iconColor="text-gray-600"
            description="Poll Apple App Store customer reviews via the public iTunes RSS feed. No authentication required."
            credFields={[]}
            metaFields={[
              { key: "app_id", label: "App ID", placeholder: "123456789", hint: "Found in App Store Connect → App Information → Apple ID" },
              { key: "country", label: "Country Code", placeholder: "us", hint: "e.g. us, in, gb, au — defaults to 'us'" },
            ]}
            accountField="app_id"
            existing={connsOf("app_store")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Play Store ── */}
        <TabsContent value="playstore" className="mt-6">
          <ConnectorPanel channelType="play_store" title="Google Play Store Reviews" icon={Play}
            iconBg="bg-green-100" iconColor="text-green-700"
            description="Poll Google Play Store reviews via the Android Publisher API. Requires a service account with androidpublisher scope."
            docsUrl="https://developers.google.com/android-publisher/api-ref/rest/v3/reviews/list"
            credFields={[
              { key: "private_key", label: "Service Account Private Key (PEM)", placeholder: "-----BEGIN RSA PRIVATE KEY-----\n…", hint: "From Google Cloud Console → IAM → Service Accounts → Keys → JSON, then paste the private_key field" },
              { key: "client_email", label: "Service Account Email", placeholder: "name@project.iam.gserviceaccount.com" },
            ]}
            metaFields={[{ key: "package_name", label: "App Package Name", placeholder: "com.yourcompany.app" }]}
            accountField="package_name"
            existing={connsOf("play_store")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Zendesk ── */}
        <TabsContent value="zendesk" className="mt-6">
          <ConnectorPanel channelType="zendesk" title="Zendesk" icon={Building2}
            iconBg="bg-green-100" iconColor="text-green-700"
            description="Sync Zendesk tickets as complaints. New tickets are polled every hour and classified by AI."
            docsUrl="https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/"
            credFields={[
              { key: "subdomain", label: "Subdomain", placeholder: "yourcompany", hint: "From yourcompany.zendesk.com" },
              { key: "email", label: "Agent Email", placeholder: "agent@company.com" },
              { key: "api_token", label: "API Token", placeholder: "xxxxxxxxxxxx", type: "password", hint: "Admin → Apps & Integrations → APIs → Zendesk API → Add Token" },
            ]}
            accountField="subdomain"
            existing={connsOf("zendesk")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Freshdesk ── */}
        <TabsContent value="freshdesk" className="mt-6">
          <ConnectorPanel channelType="freshdesk" title="Freshdesk" icon={Building2}
            iconBg="bg-teal-100" iconColor="text-teal-700"
            description="Sync Freshdesk tickets. New and updated tickets are polled hourly and processed through the AI pipeline."
            docsUrl="https://developers.freshdesk.com/api/"
            credFields={[
              { key: "domain", label: "Domain", placeholder: "yourcompany.freshdesk.com" },
              { key: "api_key", label: "API Key", placeholder: "xxxxxxxxxxxx", type: "password", hint: "Profile Settings → Your API Key (bottom of page)" },
            ]}
            accountField="domain"
            existing={connsOf("freshdesk")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Intercom ── */}
        <TabsContent value="intercom" className="mt-6">
          <ConnectorPanel channelType="intercom" title="Intercom" icon={MessageSquare}
            iconBg="bg-blue-100" iconColor="text-blue-600"
            description="Sync Intercom conversations. New conversations are polled hourly. Supports reply-back from SynapFlow."
            docsUrl="https://developers.intercom.com/docs"
            credFields={[
              { key: "access_token", label: "Access Token", placeholder: "dG9rOjxxxxxxx…", type: "password", hint: "Settings → Integrations → Developer Hub → Create App → Authentication → Access Token" },
            ]}
            accountField="access_token"
            existing={connsOf("intercom")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── HubSpot ── */}
        <TabsContent value="hubspot" className="mt-6">
          <ConnectorPanel channelType="hubspot" title="HubSpot" icon={Zap}
            iconBg="bg-orange-100" iconColor="text-orange-600"
            description="Sync HubSpot support tickets via CRM API v3. Uses private app authentication (no OAuth redirect required)."
            docsUrl="https://developers.hubspot.com/docs/api/crm/tickets"
            credFields={[
              { key: "access_token", label: "Private App Token", placeholder: "pat-na1-xxxxxxxx…", type: "password", hint: "HubSpot Settings → Integrations → Private Apps → Create App → Access Token" },
            ]}
            accountField="access_token"
            existing={connsOf("hubspot")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Salesforce ── */}
        <TabsContent value="salesforce" className="mt-6">
          <ConnectorPanel channelType="salesforce" title="Salesforce" icon={Building2}
            iconBg="bg-blue-100" iconColor="text-blue-700"
            description="Sync Salesforce Cases via SOQL query. Uses OAuth2 password flow (Connected App required)."
            docsUrl="https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/"
            credFields={[
              { key: "client_id", label: "Connected App Client ID", placeholder: "3MVG…" },
              { key: "client_secret", label: "Client Secret", type: "password", placeholder: "xxxxxxxxx" },
              { key: "username", label: "Salesforce Username", placeholder: "user@company.com" },
              { key: "password", label: "Password", type: "password", placeholder: "Password + Security Token" },
              { key: "instance_url", label: "Instance URL (optional)", placeholder: "https://yourorg.my.salesforce.com", hint: "Leave blank to auto-detect via login.salesforce.com" },
            ]}
            accountField="username"
            existing={connsOf("salesforce")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── Outlook ── */}
        <TabsContent value="outlook" className="mt-6">
          <ConnectorPanel channelType="outlook" title="Outlook / Microsoft 365" icon={Mail}
            iconBg="bg-blue-100" iconColor="text-blue-600"
            description="Sync Outlook inbox via Microsoft Graph API. Requires a Microsoft Entra app with Mail.Read permission."
            docsUrl="https://learn.microsoft.com/en-us/graph/api/user-list-messages"
            credFields={[
              { key: "access_token", label: "Access Token", placeholder: "eyJ0eXAiOi…", type: "password", hint: "Initial access token from Microsoft Entra OAuth flow" },
              { key: "refresh_token", label: "Refresh Token", placeholder: "0.AXoA…", type: "password", hint: "Refresh token for automatic renewal (requires MICROSOFT_CLIENT_ID/SECRET env vars)" },
              { key: "tenant_id", label: "Tenant ID", placeholder: "common or your-tenant-uuid", hint: "Use 'common' for personal accounts, or your organisation's tenant ID" },
            ]}
            accountField="tenant_id"
            existing={connsOf("outlook")} onDisconnect={handleDisconnectChannel}
            disconnectingId={disconnectingId} onRefresh={loadAll}
            isPaidRequired isPaid={isPaid} />
        </TabsContent>

        {/* ── CSV Import ── */}
        <TabsContent value="csv" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 dark:text-white">
                <div className="size-8 bg-purple-100 rounded-full flex items-center justify-center">
                  <FileUp className="size-4 text-purple-600" />
                </div>
                CSV Bulk Import
              </CardTitle>
              <p className="text-sm text-gray-500">Upload a CSV file to bulk-import historical complaints. Supports up to 10 MB per file.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="border-2 border-dashed rounded-lg p-6 text-center">
                <FileUp className="size-10 text-gray-300 mx-auto mb-3" />
                <p className="text-sm font-medium dark:text-white">Upload CSV file</p>
                <p className="text-xs text-gray-500 mt-1">Required column: <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">message</code></p>
                <p className="text-xs text-gray-400">Optional: customer_email, customer_name, source, priority, category, received_at</p>
                <label className="mt-4 inline-block">
                  <Button variant="outline" size="sm" asChild>
                    <span className="cursor-pointer">
                      <FileUp className="size-4 mr-2" />Choose File
                    </span>
                  </Button>
                  <input type="file" accept=".csv" className="sr-only"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const formData = new FormData();
                      formData.append("file", file);
                      try {
                        const apiKeyVal = apiKey || localStorage.getItem("synapflow_api_key") || "";
                        const resp = await fetch("/api/v1/bulk-import/csv", {
                          method: "POST",
                          headers: { "x-api-key": apiKeyVal },
                          body: formData,
                        });
                        if (!resp.ok) throw new Error("Upload failed");
                        const data = await resp.json();
                        toast.success(`Import started! Job ID: ${data.job_id}. Check back shortly.`);
                      } catch (err: any) {
                        toast.error(err?.message || "Upload failed");
                      }
                      e.target.value = "";
                    }} />
                </label>
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <p>• Each row becomes one complaint, classified by AI automatically</p>
                <p>• Duplicate rows are detected via SHA-256 hash and skipped</p>
                <p>• Processing happens asynchronously — large files may take a few minutes</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── REST API ── */}
        <TabsContent value="api" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="dark:text-white">REST API</CardTitle>
                <Badge variant="outline">Always Active</Badge>
              </div>
              <p className="text-sm text-gray-500">POST complaints directly from any system — your app, CRM, or custom integration.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>API Key</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={loading ? "Loading…" : showApiKey ? apiKey : maskedKey} readOnly className="font-mono text-sm" />
                  <Button variant="outline" size="icon" onClick={() => setShowApiKey((v) => !v)}>{showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</Button>
                  <Button variant="outline" size="icon" onClick={() => copy(apiKey, "API key copied!")} disabled={!apiKey}><Copy className="size-4" /></Button>
                </div>
                <p className="text-xs text-gray-500 mt-1">Send as <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">x-api-key</code> header.</p>
              </div>
              <div>
                <Label>Webhook Endpoint</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={webhookUrl} readOnly className="text-sm" />
                  <Button variant="outline" size="icon" onClick={() => copy(webhookUrl, "Copied!")}><Copy className="size-4" /></Button>
                </div>
                <p className="text-xs text-gray-500 mt-1">POST JSON with <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">summary</code>, <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">customer_name</code>, <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">customer_email</code>.</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── IMAP Dialog ── */}
      <Dialog open={showImapDialog} onOpenChange={setShowImapDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Connect IMAP Account</DialogTitle></DialogHeader>
          <form onSubmit={handleConnectImap} className="space-y-4 pt-2">
            <div><Label>Email Address</Label><Input type="email" placeholder="support@company.com" value={imapForm.email} onChange={(e) => setImapForm((f) => ({ ...f, email: e.target.value }))} required /></div>
            <div><Label>Password / App Password</Label><Input type="password" placeholder="App-specific password recommended" value={imapForm.password} onChange={(e) => setImapForm((f) => ({ ...f, password: e.target.value }))} required /></div>
            <div><Label>IMAP Host <span className="text-gray-400 text-xs">(auto-detected for Gmail/Outlook/Yahoo)</span></Label><Input placeholder="imap.yourprovider.com" value={imapForm.host} onChange={(e) => setImapForm((f) => ({ ...f, host: e.target.value }))} /></div>
            <div className="flex gap-3">
              <div className="flex-1"><Label>Port</Label><Input type="number" value={imapForm.port} onChange={(e) => setImapForm((f) => ({ ...f, port: e.target.value }))} /></div>
              <div className="flex-1 flex flex-col justify-end pb-1"><div className="flex items-center gap-2"><input type="checkbox" id="imap_ssl" checked={imapForm.use_ssl} onChange={(e) => setImapForm((f) => ({ ...f, use_ssl: e.target.checked }))} /><label htmlFor="imap_ssl" className="text-sm">Use SSL/TLS</label></div></div>
            </div>
            <div className="flex gap-3 pt-1">
              <Button type="submit" disabled={connectingImap} className="flex-1">{connectingImap ? <><Loader2 className="size-4 mr-2 animate-spin" />Testing…</> : "Connect"}</Button>
              <Button type="button" variant="outline" onClick={() => setShowImapDialog(false)}>Cancel</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── WhatsApp Dialog ── */}
      <Dialog open={showWaDialog} onOpenChange={setShowWaDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Connect WhatsApp Number</DialogTitle></DialogHeader>
          <form onSubmit={handleConnectWhatsApp} className="space-y-4 pt-2">
            <div><Label>Phone Number ID <span className="text-red-500">*</span></Label><Input placeholder="123456789012345" value={waForm.phone_number_id} onChange={(e) => setWaForm((f) => ({ ...f, phone_number_id: e.target.value }))} required /></div>
            <div><Label>Access Token <span className="text-red-500">*</span></Label><Input type="password" placeholder="System user access token" value={waForm.access_token} onChange={(e) => setWaForm((f) => ({ ...f, access_token: e.target.value }))} required /></div>
            <div><Label>Business Account ID <span className="text-gray-400 text-xs">(optional)</span></Label><Input placeholder="987654321098765" value={waForm.business_account_id} onChange={(e) => setWaForm((f) => ({ ...f, business_account_id: e.target.value }))} /></div>
            <div className="flex gap-3 pt-1">
              <Button type="submit" disabled={connectingWa} className="flex-1">{connectingWa ? <><Loader2 className="size-4 mr-2 animate-spin" />Connecting…</> : "Connect"}</Button>
              <Button type="button" variant="outline" onClick={() => setShowWaDialog(false)}>Cancel</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

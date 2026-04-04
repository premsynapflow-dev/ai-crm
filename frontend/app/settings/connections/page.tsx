"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardFooter } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

// API hooks (to be added in lib/api/connections.ts)
import {
  fetchGmailStatus,
  connectGmail,
  disconnectGmail,
  fetchWhatsAppStatus,
  saveWhatsAppConnection,
} from "@/lib/api/connections";

export default function ConnectionsPage() {
  // Gmail state
  const [gmailStatus, setGmailStatus] = useState<{ connected: boolean; email?: string } | null>(null);
  const [gmailLoading, setGmailLoading] = useState(false);
  const [gmailError, setGmailError] = useState<string | null>(null);

  // WhatsApp state
  const [whatsappKey, setWhatsAppKey] = useState("");
  const [whatsappStatus, setWhatsAppStatus] = useState<{ connected: boolean; webhook?: string } | null>(null);
  const [whatsappLoading, setWhatsAppLoading] = useState(false);
  const [whatsappError, setWhatsAppError] = useState<string | null>(null);

  useEffect(() => {
    setGmailLoading(true);
    setWhatsAppLoading(true);
    fetchGmailStatus()
      .then(setGmailStatus)
      .catch(() => setGmailError("Failed to fetch Gmail status"))
      .finally(() => setGmailLoading(false));
    fetchWhatsAppStatus()
      .then(setWhatsAppStatus)
      .catch(() => setWhatsAppError("Failed to fetch WhatsApp status"))
      .finally(() => setWhatsAppLoading(false));
  }, []);

  // Gmail handlers
  const handleConnectGmail = async () => {
    setGmailLoading(true);
    setGmailError(null);
    try {
      await connectGmail();
      const status = await fetchGmailStatus();
      setGmailStatus(status);
    } catch {
      setGmailError("Failed to connect Gmail");
    } finally {
      setGmailLoading(false);
    }
  };
  const handleDisconnectGmail = async () => {
    setGmailLoading(true);
    setGmailError(null);
    try {
      await disconnectGmail();
      const status = await fetchGmailStatus();
      setGmailStatus(status);
    } catch {
      setGmailError("Failed to disconnect Gmail");
    } finally {
      setGmailLoading(false);
    }
  };

  // WhatsApp handlers
  const handleSaveWhatsApp = async () => {
    setWhatsAppLoading(true);
    setWhatsAppError(null);
    try {
      await saveWhatsAppConnection(whatsappKey);
      const status = await fetchWhatsAppStatus();
      setWhatsAppStatus(status);
    } catch {
      setWhatsAppError("Failed to save WhatsApp connection");
    } finally {
      setWhatsAppLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-8">
      <h1 className="text-2xl font-bold mb-6">Connections</h1>
      {/* Gmail Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <span className="font-semibold">Gmail</span>
            {gmailLoading && <Spinner className="w-4 h-4" />}
          </div>
        </CardHeader>
        <div className="px-6"> {/* CardBody replacement */}
          {gmailError && <div className="text-red-500 mb-2">{gmailError}</div>}
          <div className="mb-2">
            Status: {gmailStatus?.connected ? (
              <span className="text-green-600 font-medium">Connected</span>
            ) : (
              <span className="text-gray-500">Not connected</span>
            )}
          </div>
          {gmailStatus?.email && (
            <div className="mb-2 text-sm text-gray-700">Connected as: <span className="font-mono">{gmailStatus.email}</span></div>
          )}
        </div>
        <CardFooter className="flex gap-2">
          {gmailStatus?.connected ? (
            <Button variant="outline" onClick={handleDisconnectGmail} disabled={gmailLoading}>
              Disconnect
            </Button>
          ) : (
            <Button onClick={handleConnectGmail} disabled={gmailLoading}>
              Connect Gmail
            </Button>
          )}
        </CardFooter>
      </Card>

      {/* WhatsApp Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <span className="font-semibold">WhatsApp</span>
            {whatsappLoading && <Spinner className="w-4 h-4" />}
          </div>
        </CardHeader>
        <div className="px-6"> {/* CardBody replacement */}
          {whatsappError && <div className="text-red-500 mb-2">{whatsappError}</div>}
          <div className="mb-2">
            Status: {whatsappStatus?.connected ? (
              <span className="text-green-600 font-medium">Connected</span>
            ) : (
              <span className="text-gray-500">Not connected</span>
            )}
          </div>
          <Input
            value={whatsappKey}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setWhatsAppKey(e.target.value)}
            placeholder="Enter WhatsApp webhook or API key"
            className="mb-2"
            disabled={whatsappLoading}
          />
          {whatsappStatus?.webhook && (
            <div className="mb-2 text-sm text-gray-700">Current: <span className="font-mono">{whatsappStatus.webhook}</span></div>
          )}
        </div>
        <CardFooter>
          <Button onClick={handleSaveWhatsApp} disabled={whatsappLoading}>
            Save connection
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

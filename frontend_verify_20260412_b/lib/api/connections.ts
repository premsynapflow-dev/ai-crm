// API hooks for Connections tab
import api from "../api";

export async function fetchGmailStatus() {
  const res = await api.get("/api/connections/gmail/status");
  return res.data;
}

export async function connectGmail() {
  const res = await api.post("/api/connections/gmail/connect");
  return res.data;
}

export async function disconnectGmail() {
  const res = await api.post("/api/connections/gmail/disconnect");
  return res.data;
}

export async function fetchWhatsAppStatus() {
  const res = await api.get("/api/connections/whatsapp/status");
  return res.data;
}

export async function saveWhatsAppConnection(webhookOrKey: string) {
  const res = await api.post("/api/connections/whatsapp/save", { webhook: webhookOrKey });
  return res.data;
}

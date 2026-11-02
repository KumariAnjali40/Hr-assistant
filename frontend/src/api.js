import { getToken } from "./auth";

async function call(path, opts = {}) {
  const token = await getToken();
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${token}`, ...(opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...opts.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const listConversations = () => call("/conversations");
export const getMessages = (id) => call(`/conversations/${id}/messages`);
export const deleteConversation = (id) => call(`/conversations/${id}`, { method: "DELETE" });
export const sendFeedback = (id, rating) => call(`/messages/${id}/feedback`, { method: "POST", body: JSON.stringify({ rating }) });
export const listPolicies = () => call("/admin/policies");
export const deletePolicy = (id) => call(`/admin/policies/${id}`, { method: "DELETE" });
export const uploadPolicy = (form) => call("/admin/policies", { method: "POST", body: form });

// Server-Sent Events over fetch (EventSource can't send an Authorization header).
export async function* streamChat(message, conversationId, signal) {
  const token = await getToken();
  const res = await fetch("/api/chat", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const event = /^event: (.*)$/m.exec(raw)?.[1];
      const data = /^data: (.*)$/m.exec(raw)?.[1];
      if (event && data) yield { event, data: JSON.parse(data) };
    }
  }
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Session = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string | null;
  tool_calls: unknown | null;
  created_at: string;
};

export type Approval = {
  id: string;
  session_id?: string;
  tool_name: string;
  tool_call_id: string;
  arguments: Record<string, unknown> | null;
  status: "pending" | "approved" | "denied";
  decision_reason?: string | null;
  created_at: string;
  decided_at?: string | null;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSessions: () =>
    fetch(`${API_BASE}/sessions`).then(json<Session[]>),

  createSession: (title?: string) =>
    fetch(`${API_BASE}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title ?? null }),
    }).then(json<Session>),

  listMessages: (sessionId: string) =>
    fetch(`${API_BASE}/sessions/${sessionId}/messages`).then(
      json<ChatMessage[]>,
    ),

  listApprovals: (sessionId?: string) => {
    const qs = sessionId ? `?session_id=${sessionId}` : "";
    return fetch(`${API_BASE}/approvals${qs}`).then(json<Approval[]>);
  },

  decideApproval: (id: string, decision: "approve" | "deny", reason?: string) =>
    fetch(`${API_BASE}/approvals/${id}/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, reason: reason ?? null }),
    }).then(json<Approval>),
};

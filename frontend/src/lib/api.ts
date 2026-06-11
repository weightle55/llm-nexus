import { authHeader, type CurrentUser } from "./auth";

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

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export class UnauthorizedError extends Error {
  constructor() {
    super("unauthorized");
    this.name = "UnauthorizedError";
  }
}

async function json<T>(res: Response): Promise<T> {
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

function authedJson(extra?: Record<string, string>): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...authHeader(),
    ...(extra ?? {}),
  };
}

export const api = {
  // auth
  register: (email: string, password: string) =>
    fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then(json<TokenResponse>),

  login: (email: string, password: string) =>
    fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then(json<TokenResponse>),

  me: () =>
    fetch(`${API_BASE}/auth/me`, { headers: authHeader() }).then(
      json<CurrentUser>,
    ),

  // sessions
  listSessions: () =>
    fetch(`${API_BASE}/sessions`, { headers: authHeader() }).then(
      json<Session[]>,
    ),

  createSession: (title?: string) =>
    fetch(`${API_BASE}/sessions`, {
      method: "POST",
      headers: authedJson(),
      body: JSON.stringify({ title: title ?? null }),
    }).then(json<Session>),

  deleteSession: (sessionId: string) =>
    fetch(`${API_BASE}/sessions/${sessionId}`, {
      method: "DELETE",
      headers: authHeader(),
    }).then((res) => {
      if (res.status === 401) throw new UnauthorizedError();
      if (!res.ok && res.status !== 204) {
        throw new Error(`${res.status} ${res.statusText}`);
      }
    }),

  listMessages: (sessionId: string) =>
    fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
      headers: authHeader(),
    }).then(json<ChatMessage[]>),

  // approvals
  listApprovals: (sessionId?: string) => {
    const qs = sessionId ? `?session_id=${sessionId}` : "";
    return fetch(`${API_BASE}/approvals${qs}`, {
      headers: authHeader(),
    }).then(json<Approval[]>);
  },

  decideApproval: (id: string, decision: "approve" | "deny", reason?: string) =>
    fetch(`${API_BASE}/approvals/${id}/decide`, {
      method: "POST",
      headers: authedJson(),
      body: JSON.stringify({ decision, reason: reason ?? null }),
    }).then(json<Approval>),
};

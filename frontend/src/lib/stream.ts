import { fetchEventSource } from "@microsoft/fetch-event-source";
import { API_BASE, type Approval } from "./api";

export type StreamEvent =
  | { type: "token"; delta: string }
  | { type: "tool_call"; id: string; name: string; arguments: string }
  | {
      type: "tool_result";
      tool_call_id: string;
      name: string;
      content: string;
    }
  | { type: "approval_required"; approvals: Approval[] }
  | { type: "done"; status: string; reply?: string | null }
  | { type: "error"; detail: string };

export type StreamHandlers = {
  onEvent: (ev: StreamEvent) => void;
  onClose?: () => void;
  onError?: (err: unknown) => void;
  signal?: AbortSignal;
};

function parse(name: string, data: string): StreamEvent | null {
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(data);
  } catch {
    return null;
  }
  switch (name) {
    case "token":
      return { type: "token", delta: String(payload.delta ?? "") };
    case "tool_call":
      return {
        type: "tool_call",
        id: String(payload.id ?? ""),
        name: String(
          (payload.function as Record<string, unknown> | undefined)?.name ?? "",
        ),
        arguments: String(
          (payload.function as Record<string, unknown> | undefined)
            ?.arguments ?? "",
        ),
      };
    case "tool_result":
      return {
        type: "tool_result",
        tool_call_id: String(payload.tool_call_id ?? ""),
        name: String(payload.name ?? ""),
        content: String(payload.content ?? ""),
      };
    case "approval_required":
      return {
        type: "approval_required",
        approvals: (payload.approvals as Approval[]) ?? [],
      };
    case "done":
      return {
        type: "done",
        status: String(payload.status ?? "ok"),
        reply: (payload.reply as string | null | undefined) ?? null,
      };
    case "error":
      return { type: "error", detail: String(payload.detail ?? "unknown") };
    default:
      return null;
  }
}

async function consume(
  path: string,
  body: Record<string, unknown>,
  handlers: StreamHandlers,
) {
  try {
    await fetchEventSource(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: handlers.signal,
      openWhenHidden: true,
      onmessage(msg) {
        const ev = parse(msg.event || "message", msg.data);
        if (ev) handlers.onEvent(ev);
      },
      onclose() {
        handlers.onClose?.();
      },
      onerror(err) {
        handlers.onError?.(err);
        throw err;
      },
    });
  } catch (err) {
    handlers.onError?.(err);
  }
}

export const stream = {
  chat: (sessionId: string, message: string, handlers: StreamHandlers) =>
    consume("/chat/stream", { session_id: sessionId, message }, handlers),

  resume: (sessionId: string, handlers: StreamHandlers) =>
    consume("/chat/resume/stream", { session_id: sessionId }, handlers),
};

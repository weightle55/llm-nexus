"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Approval, type ChatMessage } from "@/lib/api";
import { stream, type StreamEvent } from "@/lib/stream";
import { MessageList, type DisplayMessage } from "./MessageList";
import { Composer } from "./Composer";
import { ApprovalModal } from "./ApprovalModal";

type StreamingMsg = {
  id: string;
  content: string;
  toolEvents: DisplayMessage[];
};

function historyToDisplay(messages: ChatMessage[]): DisplayMessage[] {
  return messages
    .filter((m) => m.role !== "system")
    .map<DisplayMessage | null>((m) => {
      if (m.role === "tool") {
        const meta = (m.tool_calls as { name?: string } | null) ?? null;
        return {
          id: m.id,
          role: "tool",
          content: m.content ?? "",
          toolName: meta?.name,
        };
      }
      if (m.role === "assistant") {
        const calls = m.tool_calls as
          | { function?: { name?: string } }[]
          | null;
        const callSummary = calls
          ?.map((c) => c.function?.name)
          .filter(Boolean)
          .join(", ");
        const content =
          (m.content && m.content.trim()) ||
          (callSummary ? `(calling tool: ${callSummary})` : "");
        if (!content) return null;
        return {
          id: m.id,
          role: "assistant",
          content,
        };
      }
      return {
        id: m.id,
        role: m.role,
        content: m.content ?? "",
      };
    })
    .filter((m): m is DisplayMessage => m !== null);
}

export function ChatView({ sessionId }: { sessionId: string }) {
  const qc = useQueryClient();

  const { data: history = [] } = useQuery({
    queryKey: ["messages", sessionId],
    queryFn: () => api.listMessages(sessionId),
  });

  const [streaming, setStreaming] = useState<StreamingMsg | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setStreaming(null);
    setApprovals([]);
    setError(null);
    abortRef.current?.abort();
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    api.listApprovals(sessionId).then((rows) => {
      const pending = rows.filter((r) => r.status === "pending");
      if (pending.length > 0) setApprovals(pending);
    });
  }, [sessionId]);

  const displayed = useMemo(() => {
    const base = historyToDisplay(history);
    if (!streaming) return base;
    const tools = streaming.toolEvents;
    const live: DisplayMessage[] = streaming.content
      ? [
          ...tools,
          {
            id: streaming.id,
            role: "assistant",
            content: streaming.content,
            streaming: true,
          },
        ]
      : tools;
    return [...base, ...live];
  }, [history, streaming]);

  function startStream(
    runner: (handlers: Parameters<typeof stream.chat>[2]) => Promise<void>,
    seedUserText?: string,
  ) {
    const ctrl = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ctrl;
    setBusy(true);
    setError(null);

    let liveId = `stream-${Date.now()}`;
    const toolEvents: DisplayMessage[] = [];
    if (seedUserText) {
      qc.setQueryData<ChatMessage[]>(["messages", sessionId], (old) => [
        ...(old ?? []),
        {
          id: `local-user-${Date.now()}`,
          role: "user",
          content: seedUserText,
          tool_calls: null,
          created_at: new Date().toISOString(),
        },
      ]);
    }
    setStreaming({ id: liveId, content: "", toolEvents });

    const onEvent = (ev: StreamEvent) => {
      if (ev.type === "token") {
        setStreaming((cur) =>
          cur ? { ...cur, content: cur.content + ev.delta } : cur,
        );
      } else if (ev.type === "tool_call") {
        toolEvents.push({
          id: `tc-${ev.id}`,
          role: "system",
          content: `→ ${ev.name}(${ev.arguments})`,
        });
        setStreaming((cur) =>
          cur ? { ...cur, toolEvents: [...toolEvents] } : cur,
        );
      } else if (ev.type === "tool_result") {
        toolEvents.push({
          id: `tr-${ev.tool_call_id}`,
          role: "tool",
          content: ev.content,
          toolName: ev.name,
        });
        setStreaming((cur) =>
          cur ? { ...cur, toolEvents: [...toolEvents] } : cur,
        );
      } else if (ev.type === "approval_required") {
        setApprovals(ev.approvals);
      } else if (ev.type === "done") {
        setStreaming(null);
        setBusy(false);
        qc.invalidateQueries({ queryKey: ["messages", sessionId] });
      } else if (ev.type === "error") {
        setError(ev.detail);
        setStreaming(null);
        setBusy(false);
      }
    };

    runner({
      onEvent,
      signal: ctrl.signal,
      onError: (err) => {
        if ((err as { name?: string })?.name === "AbortError") return;
        setError(String(err));
        setBusy(false);
        setStreaming(null);
      },
    });
  }

  function handleSend(text: string) {
    startStream(
      (handlers) => stream.chat(sessionId, text, handlers),
      text,
    );
  }

  async function handleDecide(
    id: string,
    decision: "approve" | "deny",
    reason?: string,
  ) {
    setBusy(true);
    try {
      await api.decideApproval(id, decision, reason);
      setApprovals((cur) => cur.filter((a) => a.id !== id));
      const remaining = approvals.filter((a) => a.id !== id);
      if (remaining.length === 0) {
        startStream((handlers) => stream.resume(sessionId, handlers));
      }
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full relative">
      {error && (
        <div className="bg-red-900/40 border-b border-red-800 px-4 py-2 text-xs text-red-200">
          {error}
        </div>
      )}
      <MessageList messages={displayed} />
      <Composer disabled={busy || approvals.length > 0} onSend={handleSend} />
      <ApprovalModal
        approvals={approvals}
        onDecide={handleDecide}
        busy={busy}
      />
    </div>
  );
}

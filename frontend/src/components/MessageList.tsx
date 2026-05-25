"use client";

import { useEffect, useRef } from "react";

export type DisplayMessage = {
  id: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  toolName?: string;
  streaming?: boolean;
};

function bubbleClass(role: DisplayMessage["role"]) {
  switch (role) {
    case "user":
      return "bg-blue-600 text-white";
    case "assistant":
      return "bg-neutral-200 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100";
    case "tool":
      return "bg-neutral-100 dark:bg-neutral-900 text-emerald-700 dark:text-emerald-300 border border-neutral-200 dark:border-neutral-800 font-mono text-xs";
    default:
      return "bg-neutral-100 dark:bg-neutral-900 text-neutral-500 dark:text-neutral-400 text-xs";
  }
}

export function MessageList({ messages }: { messages: DisplayMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[80%] rounded-lg px-3 py-2 whitespace-pre-wrap break-words ${bubbleClass(m.role)}`}
          >
            {m.toolName && (
              <div className="text-[10px] text-neutral-500 mb-1">
                tool · {m.toolName}
              </div>
            )}
            <span>{m.content}</span>
            {m.streaming && <span className="inline-block ml-0.5 animate-pulse">▍</span>}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

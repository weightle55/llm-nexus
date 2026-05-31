"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

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

const mdComponents: Components = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-5 my-2 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 my-2 space-y-0.5">{children}</ol>
  ),
  li: ({ children }) => <li>{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="text-blue-600 dark:text-blue-400 underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-neutral-400 dark:border-neutral-600 pl-3 my-2 italic opacity-90">
      {children}
    </blockquote>
  ),
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold mt-2 mb-1">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold mt-2 mb-1">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>
  ),
  hr: () => (
    <hr className="my-3 border-neutral-300 dark:border-neutral-700" />
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="min-w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-neutral-300/60 dark:bg-neutral-700/60">
      {children}
    </thead>
  ),
  th: ({ children }) => (
    <th className="border border-neutral-300 dark:border-neutral-700 px-2 py-1 text-left font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-neutral-300 dark:border-neutral-700 px-2 py-1">
      {children}
    </td>
  ),
  pre: ({ children }) => (
    <pre className="bg-neutral-900 dark:bg-black text-neutral-100 rounded p-3 my-2 overflow-x-auto text-xs leading-relaxed">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="bg-neutral-300/60 dark:bg-neutral-700/60 rounded px-1 py-0.5 text-xs font-mono">
        {children}
      </code>
    );
  },
};

function AssistantContent({ content }: { content: string }) {
  return (
    <div className="max-w-none break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={mdComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function MessageList({ messages }: { messages: DisplayMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {messages.map((m) => {
        const isAssistant = m.role === "assistant";
        return (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 break-words ${
                isAssistant ? "" : "whitespace-pre-wrap"
              } ${bubbleClass(m.role)}`}
            >
              {m.toolName && (
                <div className="text-[10px] text-neutral-500 mb-1">
                  tool · {m.toolName}
                </div>
              )}
              {isAssistant ? (
                <AssistantContent content={m.content} />
              ) : (
                <span>{m.content}</span>
              )}
              {m.streaming && (
                <span className="inline-block ml-0.5 animate-pulse">▍</span>
              )}
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}

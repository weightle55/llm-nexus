"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatView } from "@/components/ChatView";

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen">
      <Sidebar
        selectedId={sessionId}
        onSelect={setSessionId}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden flex items-center gap-2 px-3 py-2 border-b border-neutral-200 dark:border-neutral-800">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
            className="rounded border border-neutral-300 dark:border-neutral-800 px-2 py-1 text-sm"
          >
            ☰
          </button>
          <span className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
            llm-nexus
          </span>
        </header>
        {sessionId ? (
          <ChatView sessionId={sessionId} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
            Select a session or start a new chat.
          </div>
        )}
      </main>
    </div>
  );
}

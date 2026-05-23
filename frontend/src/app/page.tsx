"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatView } from "@/components/ChatView";

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);

  return (
    <div className="flex h-screen">
      <Sidebar selectedId={sessionId} onSelect={setSessionId} />
      <main className="flex-1 flex flex-col">
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

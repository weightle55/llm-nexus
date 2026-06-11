"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ChatView } from "@/components/ChatView";
import { api, UnauthorizedError } from "@/lib/api";
import { clearToken, getToken, type CurrentUser } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        setChecking(false);
      })
      .catch((err) => {
        if (err instanceof UnauthorizedError) {
          clearToken();
          router.replace("/login");
        } else {
          setChecking(false);
        }
      });
  }, [router]);

  function handleLogout() {
    clearToken();
    setUser(null);
    router.replace("/login");
  }

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-neutral-500">
        Loading…
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen">
      <Sidebar
        selectedId={sessionId}
        onSelect={setSessionId}
        onDeleted={(id) => {
          if (id === sessionId) setSessionId(null);
        }}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        onLogout={handleLogout}
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

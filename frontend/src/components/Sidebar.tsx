"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Session } from "@/lib/api";
import { ThemeToggle } from "./ThemeToggle";

type Props = {
  selectedId: string | null;
  onSelect: (id: string) => void;
  isOpen: boolean;
  onClose: () => void;
};

export function Sidebar({ selectedId, onSelect, isOpen, onClose }: Props) {
  const qc = useQueryClient();
  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
  });

  const createMut = useMutation({
    mutationFn: () => api.createSession(`Session ${new Date().toLocaleString()}`),
    onSuccess: (s: Session) => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      onSelect(s.id);
      onClose();
    },
  });

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          className="md:hidden fixed inset-0 bg-black/50 z-30"
          aria-hidden
        />
      )}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-40
          w-64 shrink-0 flex flex-col h-full
          border-r border-neutral-200 dark:border-neutral-800
          bg-white dark:bg-neutral-950
          transform transition-transform duration-200
          ${isOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0
        `}
      >
        <div className="p-3 border-b border-neutral-200 dark:border-neutral-800 flex gap-2 items-center">
          <button
            onClick={() => createMut.mutate()}
            disabled={createMut.isPending}
            className="flex-1 rounded bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-sm font-medium py-2 hover:opacity-90 disabled:opacity-50"
          >
            {createMut.isPending ? "Creating…" : "+ New chat"}
          </button>
          <button
            onClick={onClose}
            className="md:hidden rounded border border-neutral-300 dark:border-neutral-800 px-2 py-2 text-xs text-neutral-500"
            aria-label="Close sidebar"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="p-3 text-xs text-neutral-500">Loading…</div>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                onSelect(s.id);
                onClose();
              }}
              className={`
                w-full text-left px-3 py-2 text-sm
                border-b border-neutral-100 dark:border-neutral-900
                hover:bg-neutral-100 dark:hover:bg-neutral-900
                ${s.id === selectedId ? "bg-neutral-100 dark:bg-neutral-900" : ""}
              `}
            >
              <div className="truncate">{s.title ?? "Untitled"}</div>
              <div className="text-[10px] text-neutral-500 truncate">{s.id}</div>
            </button>
          ))}
          {!isLoading && sessions.length === 0 && (
            <div className="p-3 text-xs text-neutral-500">No sessions yet.</div>
          )}
        </div>
        <div className="p-3 border-t border-neutral-200 dark:border-neutral-800">
          <ThemeToggle />
        </div>
      </aside>
    </>
  );
}

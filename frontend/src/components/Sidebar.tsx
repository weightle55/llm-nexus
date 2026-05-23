"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Session } from "@/lib/api";

type Props = {
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export function Sidebar({ selectedId, onSelect }: Props) {
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
    },
  });

  return (
    <aside className="w-64 shrink-0 border-r border-neutral-800 flex flex-col h-full">
      <div className="p-3 border-b border-neutral-800">
        <button
          onClick={() => createMut.mutate()}
          disabled={createMut.isPending}
          className="w-full rounded bg-neutral-100 text-neutral-900 text-sm font-medium py-2 hover:bg-white disabled:opacity-50"
        >
          {createMut.isPending ? "Creating…" : "+ New chat"}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="p-3 text-xs text-neutral-500">Loading…</div>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`w-full text-left px-3 py-2 text-sm border-b border-neutral-900 hover:bg-neutral-900 ${
              s.id === selectedId ? "bg-neutral-900" : ""
            }`}
          >
            <div className="truncate">{s.title ?? "Untitled"}</div>
            <div className="text-[10px] text-neutral-500 truncate">{s.id}</div>
          </button>
        ))}
        {!isLoading && sessions.length === 0 && (
          <div className="p-3 text-xs text-neutral-500">No sessions yet.</div>
        )}
      </div>
    </aside>
  );
}

"use client";

import { useState } from "react";
import type { Approval } from "@/lib/api";

type Props = {
  approvals: Approval[];
  onDecide: (id: string, decision: "approve" | "deny", reason?: string) => void;
  busy?: boolean;
};

export function ApprovalModal({ approvals, onDecide, busy }: Props) {
  const [reason, setReason] = useState("");

  if (approvals.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xl">
        <div className="px-5 py-4 border-b border-neutral-200 dark:border-neutral-800">
          <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
            Approval required
          </h2>
          <p className="text-xs text-neutral-500 mt-1">
            The agent is requesting permission to run a privileged tool.
          </p>
        </div>
        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {approvals.map((a) => (
            <div
              key={a.id}
              className="rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 p-3"
            >
              <div className="text-xs text-neutral-500 mb-1">tool</div>
              <div className="font-mono text-emerald-700 dark:text-emerald-300 text-sm mb-2">
                {a.tool_name}
              </div>
              <div className="text-xs text-neutral-500 mb-1">arguments</div>
              <pre className="bg-neutral-100 dark:bg-neutral-900 text-emerald-700 dark:text-emerald-200 rounded p-2 text-xs overflow-x-auto whitespace-pre-wrap break-words">
                {JSON.stringify(a.arguments, null, 2)}
              </pre>
              <div className="mt-3 flex gap-2">
                <button
                  disabled={busy}
                  onClick={() => onDecide(a.id, "approve")}
                  className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    onDecide(a.id, "deny", reason.trim() || undefined)
                  }
                  className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
                >
                  Deny
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="px-5 py-3 border-t border-neutral-200 dark:border-neutral-800">
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Deny reason (optional)"
            className="w-full rounded bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-500 dark:focus:border-neutral-600"
          />
        </div>
      </div>
    </div>
  );
}

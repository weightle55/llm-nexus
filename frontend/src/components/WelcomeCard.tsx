"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function WelcomeCard() {
  const { data: caps } = useQuery({
    queryKey: ["capabilities"],
    queryFn: api.getCapabilities,
    staleTime: 1000 * 60 * 60, // 정적 — 1시간 캐시
  });

  if (!caps) return null;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-8">
      <div className="mx-auto max-w-2xl">
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 p-6 shadow-sm">
          <p className="text-sm leading-relaxed text-neutral-700 dark:text-neutral-200">
            {caps.intro}
          </p>

          <div className="mt-5 space-y-5">
            {caps.groups.map((g) => (
              <div key={g.title}>
                <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400">
                  {g.title}
                </h3>
                <ul className="mt-2 space-y-1.5">
                  {g.items.map((item) => (
                    <li key={item.label} className="flex gap-2 text-sm">
                      <span className="shrink-0 font-medium text-neutral-800 dark:text-neutral-100">
                        {item.label}
                      </span>
                      {item.approval && (
                        <span className="shrink-0 self-center rounded bg-amber-100 dark:bg-amber-900/50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                          승인 필요
                        </span>
                      )}
                      <span className="text-neutral-500 dark:text-neutral-400">
                        {item.desc}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <p className="mt-5 border-t border-neutral-100 dark:border-neutral-900 pt-4 text-xs text-neutral-400 dark:text-neutral-500">
            {caps.note}
          </p>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error in app:", error);
  }, [error]);

  return (
    <div className="flex h-screen items-center justify-center p-6">
      <div className="max-w-md w-full rounded-lg border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950 p-5">
        <h2 className="text-base font-semibold text-red-900 dark:text-red-200 mb-2">
          예기치 않은 오류가 발생했습니다
        </h2>
        <p className="text-xs text-red-800 dark:text-red-300 font-mono whitespace-pre-wrap break-words mb-4">
          {error.message || "Unknown error"}
        </p>
        <button
          onClick={reset}
          className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}

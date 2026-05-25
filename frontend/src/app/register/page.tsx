"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError("비밀번호는 6자 이상");
      return;
    }
    setBusy(true);
    try {
      const { access_token } = await api.register(email, password);
      setToken(access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-lg border border-neutral-200 dark:border-neutral-800 p-6 bg-white dark:bg-neutral-900">
        <h1 className="text-xl font-semibold mb-1">회원가입</h1>
        <p className="text-xs text-neutral-500 mb-5">llm-nexus 계정을 만든다</p>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-xs text-neutral-500 mb-1 block">이메일</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full rounded bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 px-3 py-2 text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          <div>
            <label className="text-xs text-neutral-500 mb-1 block">
              비밀번호 (6자 이상)
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete="new-password"
              className="w-full rounded bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 px-3 py-2 text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          {error && (
            <div className="text-xs text-red-600 dark:text-red-400 break-words">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {busy ? "가입 중…" : "회원가입"}
          </button>
        </form>
        <div className="mt-4 text-xs text-neutral-500 text-center">
          이미 가입함? <Link href="/login" className="underline">로그인</Link>
        </div>
      </div>
    </div>
  );
}

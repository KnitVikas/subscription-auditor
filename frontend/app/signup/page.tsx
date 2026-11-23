"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { TokenResponse } from "@/lib/types";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<TokenResponse>("/auth/signup", { email, password });
      setToken(res.access_token);
      router.push("/connect");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-6">
      <h1 className="text-2xl font-bold">Create your account</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2"
        />
        <input
          type="password"
          placeholder="Password (min 8 chars)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2"
        />
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-500 px-4 py-2.5 font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
        >
          {loading ? "Creating..." : "Sign up"}
        </button>
      </form>
      <p className="text-sm text-gray-400">
        Already have an account?{" "}
        <Link href="/login" className="text-indigo-400 hover:underline">
          Log in
        </Link>
      </p>
    </main>
  );
}

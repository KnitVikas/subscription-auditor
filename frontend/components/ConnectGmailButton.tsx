"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { DEFAULT_SCAN_DAYS, SCAN_RANGES } from "@/lib/scanRanges";

export default function ConnectGmailButton() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(DEFAULT_SCAN_DAYS);

  async function connect() {
    setLoading(true);
    setError(null);
    try {
      const { url } = await api.get<{ url: string }>(`/connections/gmail/url?days=${days}`);
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start Gmail connect");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <label className="flex items-center gap-2 text-sm text-gray-400">
        Scan emails from
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          disabled={loading}
          className="rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-gray-100"
        >
          {SCAN_RANGES.map((r) => (
            <option key={r.days} value={r.days}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
      <button
        onClick={connect}
        disabled={loading}
        className="rounded-lg bg-indigo-500 px-5 py-2.5 font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
      >
        {loading ? "Redirecting..." : "Connect Gmail (read-only)"}
      </button>
      {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
    </div>
  );
}

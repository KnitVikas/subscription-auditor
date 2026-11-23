"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import ChargesList from "@/components/ChargesList";
import SpendInsights from "@/components/SpendInsights";
import SpendSummary from "@/components/SpendSummary";
import SubscriptionList from "@/components/SubscriptionList";
import SyncStatus from "@/components/SyncStatus";
import { api } from "@/lib/api";
import { clearToken, isAuthenticated } from "@/lib/auth";
import { DEFAULT_SCAN_DAYS, SCAN_RANGES } from "@/lib/scanRanges";
import {
  Connection,
  ConnectionList,
  SubscriptionList as SubList,
  Transaction,
  TransactionList,
} from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<SubList | null>(null);
  const [charges, setCharges] = useState<Transaction[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(DEFAULT_SCAN_DAYS);
  const [rescanning, setRescanning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const gmail = connections.find((c) => c.type === "gmail") || null;
  const syncing = gmail?.sync_status === "running";

  const loadResults = useCallback(async () => {
    const [subs, txns] = await Promise.all([
      api.get<SubList>("/subscriptions"),
      api.get<TransactionList>("/transactions"),
    ]);
    setData(subs);
    setCharges(txns.transactions);
  }, []);

  const loadConnections = useCallback(async () => {
    const res = await api.get<ConnectionList>("/connections");
    setConnections(res.connections);
    return res.connections;
  }, []);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    Promise.all([loadConnections(), loadResults()]).catch((e) =>
      setError(e instanceof Error ? e.message : "Failed to load"),
    );
  }, [router, loadConnections, loadResults]);

  // While a sync is running, poll until it finishes, then refresh results.
  useEffect(() => {
    if (!syncing) return;
    pollRef.current = setInterval(async () => {
      try {
        const conns = await loadConnections();
        const g = conns.find((c) => c.type === "gmail");
        if (g && g.sync_status !== "running") {
          if (pollRef.current) clearInterval(pollRef.current);
          if (g.sync_status === "done") await loadResults();
        }
      } catch {
        /* keep polling; a transient error should not stop the UI */
      }
    }, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [syncing, loadConnections, loadResults]);

  async function rescan() {
    if (!gmail || rescanning) return;
    setRescanning(true);
    setError(null);
    try {
      await api.post(`/connections/${gmail.id}/sync?days=${days}`);
      await loadConnections();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start rescan");
    } finally {
      setRescanning(false);
    }
  }

  function logout() {
    clearToken();
    router.push("/login");
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Your subscriptions</h1>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/connect" className="text-indigo-400 hover:underline">
            Connect
          </Link>
          <Link href="/budgets" className="text-indigo-400 hover:underline">
            Budgets
          </Link>
          <Link href="/settings" className="text-indigo-400 hover:underline">
            Settings
          </Link>
          <button onClick={logout} className="text-gray-400 hover:underline">
            Log out
          </button>
        </nav>
      </header>

      {error && <p className="mb-4 text-rose-400">{error}</p>}

      {gmail && (
        <div className="mb-6 flex flex-col gap-4">
          <SyncStatus conn={gmail} />
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <label className="flex items-center gap-2">
              Rescan
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                disabled={syncing || rescanning}
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
              onClick={rescan}
              disabled={syncing || rescanning}
              className="rounded-lg bg-indigo-500 px-3 py-1.5 font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
            >
              {syncing || rescanning ? "Scanning..." : "Rescan inbox"}
            </button>
          </div>
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-8">
          <SpendSummary totals={data.totals} />
          <SpendInsights />
          <SubscriptionList subs={data.subscriptions} />
          <ChargesList charges={charges} />
        </div>
      )}

      {!data && !error && <p className="text-gray-400">Loading...</p>}
    </main>
  );
}

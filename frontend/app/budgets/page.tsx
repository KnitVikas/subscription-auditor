"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { formatMoney } from "@/lib/format";
import { Budget, BudgetList } from "@/lib/types";

const STATUS: Record<string, { label: string; className: string }> = {
  ok: { label: "On track", className: "bg-emerald-500/15 text-emerald-300" },
  near: { label: "Near limit", className: "bg-amber-500/15 text-amber-300" },
  over: { label: "Over budget", className: "bg-rose-500/15 text-rose-300" },
};

export default function BudgetsPage() {
  const router = useRouter();
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    load();
  }, [router]);

  function load() {
    api
      .get<BudgetList>("/budgets")
      .then((r) => setBudgets(r.budgets))
      .catch(() => {});
  }

  async function addBudget(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/budgets", {
        category: category.trim(),
        monthly_limit: limit,
      });
      setCategory("");
      setLimit("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add budget");
    }
  }

  async function updateLimit(b: Budget) {
    const next = prompt(`New monthly limit for ${b.category}`, b.monthly_limit);
    if (next === null) return;
    try {
      await api.patch(`/budgets/${b.id}`, { monthly_limit: next });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update");
    }
  }

  async function remove(b: Budget) {
    if (!confirm(`Delete the ${b.category} budget?`)) return;
    await api.del(`/budgets/${b.id}`);
    load();
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <Link href="/dashboard" className="text-sm text-gray-400 hover:underline">
        &larr; Back to dashboard
      </Link>
      <h1 className="mb-2 mt-4 text-2xl font-bold">Budgets</h1>
      <p className="mb-6 text-sm text-gray-400">
        Set a monthly cap per category. We compare it to your current recurring
        spend and flag anything near or over the limit.
      </p>

      <form onSubmit={addBudget} className="mb-8 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm text-gray-400">
          Category
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Streaming"
            required
            className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-400">
          Monthly limit
          <input
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            inputMode="decimal"
            placeholder="1000"
            required
            className="w-32 rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100"
          />
        </label>
        <button
          type="submit"
          className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400"
        >
          Add budget
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-rose-400">{error}</p>}

      {budgets.length === 0 ? (
        <p className="text-sm text-gray-500">No budgets yet.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {budgets.map((b) => {
            const spent = parseFloat(b.spent);
            const lim = parseFloat(b.monthly_limit);
            const pct = lim > 0 ? Math.min(100, (spent / lim) * 100) : 0;
            const status = STATUS[b.status] ?? STATUS.ok;
            return (
              <div
                key={b.id}
                className="rounded-xl border border-gray-700 bg-gray-900/60 p-4"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{b.category}</span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}
                  >
                    {status.label}
                  </span>
                </div>
                <div className="mt-2 h-2 w-full rounded-full bg-gray-800">
                  <div
                    className={`h-2 rounded-full ${
                      b.status === "over"
                        ? "bg-rose-500"
                        : b.status === "near"
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                    }`}
                    style={{ width: `${Math.max(3, pct)}%` }}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between text-sm text-gray-400">
                  <span>
                    {formatMoney(b.spent, b.currency)} of{" "}
                    {formatMoney(b.monthly_limit, b.currency)}
                  </span>
                  <span className="flex gap-3">
                    <button
                      onClick={() => updateLimit(b)}
                      className="hover:text-gray-200 hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => remove(b)}
                      className="hover:text-rose-300 hover:underline"
                    >
                      Delete
                    </button>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}

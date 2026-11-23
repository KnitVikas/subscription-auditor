"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Insights } from "@/lib/types";

const BAR_COLORS = [
  "bg-indigo-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-fuchsia-500",
  "bg-sky-500",
  "bg-rose-500",
];

function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", {
    month: "short",
    year: "2-digit",
  });
}

export default function SpendInsights() {
  const [data, setData] = useState<Insights | null>(null);

  useEffect(() => {
    api.get<Insights>("/insights/spend").then(setData).catch(() => {});
  }, []);

  if (!data || data.by_category.length === 0) return null;

  const maxMonth = data.by_month.reduce(
    (m, x) => Math.max(m, parseFloat(x.total)),
    0,
  );

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Spending insights</h2>
        {data.trend_pct !== null && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              data.trend_pct > 0
                ? "bg-rose-500/15 text-rose-300"
                : "bg-emerald-500/15 text-emerald-300"
            }`}
          >
            {data.trend_pct > 0 ? "up" : "down"}{" "}
            {Math.abs(data.trend_pct)}% vs last month
          </span>
        )}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-5">
          <p className="mb-3 text-sm text-gray-400">By category (monthly)</p>
          <div className="flex flex-col gap-3">
            {data.by_category.map((c, i) => (
              <div key={c.category}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>{c.category}</span>
                  <span className="text-gray-400">
                    {formatMoney(c.monthly, data.currency)}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-800">
                  <div
                    className={`h-2 rounded-full ${BAR_COLORS[i % BAR_COLORS.length]}`}
                    style={{ width: `${Math.max(3, c.share * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-5">
          <p className="mb-3 text-sm text-gray-400">Charges by month</p>
          {data.by_month.length === 0 ? (
            <p className="text-sm text-gray-500">No charges yet.</p>
          ) : (
            <div className="flex h-36 items-end justify-between gap-2">
              {data.by_month.map((m) => {
                const pct = maxMonth > 0 ? (parseFloat(m.total) / maxMonth) * 100 : 0;
                return (
                  <div key={m.month} className="flex flex-1 flex-col items-center gap-1">
                    <div className="flex h-28 w-full items-end">
                      <div
                        className="w-full rounded-t bg-indigo-500/80"
                        style={{ height: `${Math.max(4, pct)}%` }}
                        title={formatMoney(m.total, data.currency)}
                      />
                    </div>
                    <span className="text-[10px] text-gray-500">
                      {monthLabel(m.month)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

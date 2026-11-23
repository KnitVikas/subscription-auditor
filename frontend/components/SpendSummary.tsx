import { Totals } from "@/lib/types";
import { formatMoney } from "@/lib/format";

export default function SpendSummary({ totals }: { totals: Totals }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-5">
        <p className="text-sm text-gray-400">Monthly spend</p>
        <p className="mt-1 text-3xl font-bold">
          {formatMoney(totals.monthly, totals.currency)}
        </p>
      </div>
      <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-5">
        <p className="text-sm text-gray-400">Yearly spend</p>
        <p className="mt-1 text-3xl font-bold">
          {formatMoney(totals.yearly, totals.currency)}
        </p>
      </div>
      <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-5">
        <p className="text-sm text-gray-400">Active subscriptions</p>
        <p className="mt-1 text-3xl font-bold">{totals.count}</p>
      </div>
    </div>
  );
}

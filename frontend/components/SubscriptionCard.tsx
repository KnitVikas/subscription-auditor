import Link from "next/link";

import { Subscription } from "@/lib/types";
import { formatMoney, formatDate, daysUntil } from "@/lib/format";
import AlertBadge from "./AlertBadge";

export default function SubscriptionCard({ sub }: { sub: Subscription }) {
  const days = daysUntil(sub.next_renewal_at);
  return (
    <Link
      href={`/subscriptions/${sub.id}`}
      className="flex items-center justify-between rounded-xl border border-gray-700 bg-gray-900/60 p-4 transition hover:border-gray-500"
    >
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-800 text-sm font-bold">
          {sub.merchant_name.charAt(0)}
        </div>
        <div>
          <p className="font-medium">{sub.merchant_name}</p>
          <p className="text-sm text-gray-400">
            {sub.category ?? "Uncategorized"} &middot; {sub.cadence}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="font-semibold">{formatMoney(sub.amount, sub.currency)}</p>
        <div className="mt-1 flex flex-wrap items-center justify-end gap-2">
          <AlertBadge status={sub.status} />
          {sub.flags
            .filter((f) => f !== sub.status)
            .map((f) => (
              <AlertBadge key={f} status={f} />
            ))}
          {days !== null && days >= 0 && (
            <span className="text-xs text-gray-400">
              renews in {days}d
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

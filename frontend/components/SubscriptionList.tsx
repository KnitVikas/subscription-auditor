import { Subscription } from "@/lib/types";
import SubscriptionCard from "./SubscriptionCard";

export default function SubscriptionList({ subs }: { subs: Subscription[] }) {
  if (subs.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-gray-700 p-8 text-center text-gray-400">
        No subscriptions detected yet. If you just connected Gmail, give the sync
        a minute and refresh.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {subs.map((sub) => (
        <SubscriptionCard key={sub.id} sub={sub} />
      ))}
    </div>
  );
}

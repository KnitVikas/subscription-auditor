const LABELS: Record<string, { text: string; className: string }> = {
  active: { text: "Active", className: "bg-emerald-500/15 text-emerald-300" },
  price_hike: { text: "Price hike", className: "bg-amber-500/15 text-amber-300" },
  trial: { text: "Trial", className: "bg-blue-500/15 text-blue-300" },
  unused: { text: "Unused", className: "bg-rose-500/15 text-rose-300" },
  duplicate: { text: "Duplicate", className: "bg-fuchsia-500/15 text-fuchsia-300" },
  cancelled: { text: "Cancelled", className: "bg-gray-500/15 text-gray-400" },
  ignored: { text: "Ignored", className: "bg-gray-500/15 text-gray-400" },
};

export default function AlertBadge({ status }: { status: string }) {
  const badge = LABELS[status] ?? LABELS.active;
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.className}`}>
      {badge.text}
    </span>
  );
}

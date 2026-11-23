import { Connection } from "@/lib/types";

export default function SyncStatus({ conn }: { conn: Connection | null }) {
  if (!conn) return null;

  if (conn.sync_status === "running") {
    const pct =
      conn.sync_total > 0
        ? Math.min(100, Math.round((conn.sync_done / conn.sync_total) * 100))
        : 0;
    return (
      <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4">
        <p className="text-sm text-indigo-200">
          {conn.sync_total > 0
            ? `Scanning your inbox: ${conn.sync_done} of ${conn.sync_total} emails`
            : "Scanning your inbox..."}
        </p>
        <div className="mt-2 h-2 w-full overflow-hidden rounded bg-gray-800">
          <div
            className="h-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  }

  if (conn.sync_status === "failed") {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
        Last scan failed: {conn.sync_error || "unknown error"}. Try rescanning.
      </div>
    );
  }

  return null;
}

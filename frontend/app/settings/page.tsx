"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { clearToken, isAuthenticated } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import {
  Alert,
  AlertList,
  AlertRun,
  AlertSettings,
  EmailStatus,
} from "@/lib/types";

const ALERT_LABELS: Record<string, string> = {
  renewal: "Renewal reminder",
  trial_ending: "Trial ending",
  price_hike: "Price increase",
  budget_over: "Over budget",
};

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<AlertSettings | null>(null);
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [saved, setSaved] = useState(false);
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    api.get<AlertSettings>("/alerts/settings").then(setSettings).catch(() => {});
    api.get<EmailStatus>("/alerts/email-status").then(setEmailStatus).catch(() => {});
    loadAlerts();
  }, [router]);

  function loadAlerts() {
    api
      .get<AlertList>("/alerts")
      .then((r) => setAlerts(r.alerts))
      .catch(() => {});
  }

  function update(patch: Partial<AlertSettings>) {
    setSettings((prev) => (prev ? { ...prev, ...patch } : prev));
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    await api.patch("/alerts/settings", settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function sendNow() {
    setRunning(true);
    setRunMessage(null);
    try {
      const r = await api.post<AlertRun>("/alerts/run-now");
      const total = r.reminders + r.price_hikes + r.digests + r.budget_overages;
      const summary =
        total === 0
          ? "Nothing due right now."
          : `Sent ${r.reminders} reminder(s), ${r.price_hikes} price-hike notice(s), ${r.budget_overages} budget alert(s), ${r.digests} digest(s).`;
      const channel = r.email_configured ? "" : ` ${r.email_detail}`;
      setRunMessage(summary + channel);
      loadAlerts();
    } catch {
      setRunMessage("Failed to run alerts.");
    } finally {
      setRunning(false);
    }
  }

  async function deleteAccount() {
    if (!confirm("Delete your account and all data? This cannot be undone.")) return;
    await api.del("/account");
    clearToken();
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-lg px-6 py-10">
      <Link href="/dashboard" className="text-sm text-gray-400 hover:underline">
        &larr; Back to dashboard
      </Link>
      <h1 className="mb-8 mt-4 text-2xl font-bold">Settings</h1>

      {settings && (
        <form onSubmit={saveSettings} className="flex flex-col gap-5">
          <label className="text-sm text-gray-300">
            Remind me this many days before a renewal
            <input
              type="number"
              min={0}
              max={30}
              value={settings.renewal_lead_days}
              onChange={(e) =>
                update({ renewal_lead_days: parseInt(e.target.value, 10) || 0 })
              }
              className="mt-2 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2"
            />
          </label>

          <Toggle
            label="Weekly digest email"
            hint="A Monday summary of the week's upcoming renewals."
            checked={settings.digest_enabled}
            onChange={(v) => update({ digest_enabled: v })}
          />
          <Toggle
            label="Free-trial reminders"
            hint="Warn me before a free trial converts to a paid plan."
            checked={settings.trial_alerts}
            onChange={(v) => update({ trial_alerts: v })}
          />
          <Toggle
            label="Price-increase alerts"
            hint="Tell me when a subscription's price goes up."
            checked={settings.price_hike_alerts}
            onChange={(v) => update({ price_hike_alerts: v })}
          />
          <Toggle
            label="Over-budget alerts"
            hint="Email me when a category's spend goes over its budget."
            checked={settings.budget_alerts}
            onChange={(v) => update({ budget_alerts: v })}
          />

          <div className="flex items-center gap-3">
            <button
              type="submit"
              className="rounded-lg bg-indigo-500 px-4 py-2 font-medium text-white hover:bg-indigo-400"
            >
              Save
            </button>
            {saved && <span className="text-sm text-emerald-400">Saved.</span>}
          </div>
        </form>
      )}

      <hr className="my-10 border-gray-800" />

      <h2 className="mb-2 text-lg font-semibold">Alerts</h2>
      <p className="mb-3 text-sm text-gray-400">
        Alerts normally go out automatically. You can also send anything due right
        now.
      </p>

      {emailStatus && (
        <div
          className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
            emailStatus.deliverable
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              : "border-amber-500/40 bg-amber-500/10 text-amber-200"
          }`}
        >
          {emailStatus.detail}
        </div>
      )}
      <button
        onClick={sendNow}
        disabled={running}
        className="rounded-lg border border-gray-600 px-4 py-2 text-sm hover:bg-gray-800 disabled:opacity-60"
      >
        {running ? "Sending..." : "Send due alerts now"}
      </button>
      {runMessage && <p className="mt-2 text-sm text-gray-300">{runMessage}</p>}

      <div className="mt-5 flex flex-col gap-2">
        {alerts.length === 0 && (
          <p className="text-sm text-gray-500">No alerts yet.</p>
        )}
        {alerts.map((a) => (
          <div
            key={a.id}
            className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-2 text-sm"
          >
            <span>{ALERT_LABELS[a.type] ?? a.type}</span>
            <span className="text-gray-400">
              {a.sent_at ? `sent ${formatDate(a.sent_at)}` : formatDate(a.scheduled_for)}
            </span>
          </div>
        ))}
      </div>

      <hr className="my-10 border-gray-800" />

      <h2 className="mb-3 text-lg font-semibold text-rose-400">Danger zone</h2>
      <p className="mb-3 text-sm text-gray-400">
        Delete your account and every piece of data we hold about you.
      </p>
      <button
        onClick={deleteAccount}
        className="rounded-lg border border-rose-500/60 px-4 py-2 text-sm font-medium text-rose-400 hover:bg-rose-500/10"
      >
        Delete account
      </button>
    </main>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 accent-indigo-500"
      />
      <span>
        <span className="text-sm text-gray-200">{label}</span>
        <span className="block text-xs text-gray-500">{hint}</span>
      </span>
    </label>
  );
}

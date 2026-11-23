"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AlertBadge from "@/components/AlertBadge";
import CancelGuidePanel from "@/components/CancelGuidePanel";
import { api } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { formatDate, formatMoney } from "@/lib/format";
import { SubscriptionDetail } from "@/lib/types";

const CADENCES = ["weekly", "monthly", "yearly"];

export default function SubscriptionDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [sub, setSub] = useState<SubscriptionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    api
      .get<SubscriptionDetail>(`/subscriptions/${params.id}`)
      .then(setSub)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [params.id, router]);

  async function updateStatus(status: string) {
    const updated = await api.patch<SubscriptionDetail>(
      `/subscriptions/${params.id}`,
      { status },
    );
    setSub((prev) => (prev ? { ...prev, status: updated.status, flags: updated.flags } : prev));
  }

  if (error) return <main className="p-10 text-rose-400">{error}</main>;
  if (!sub) return <main className="p-10 text-gray-400">Loading...</main>;

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <Link href="/dashboard" className="text-sm text-gray-400 hover:underline">
        &larr; Back to dashboard
      </Link>

      <div className="mt-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{sub.merchant_name}</h1>
          <p className="mt-1 text-gray-400">
            {sub.category ?? "Uncategorized"} &middot; {sub.cadence}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <AlertBadge status={sub.status} />
          {sub.flags
            .filter((f) => f !== sub.status)
            .map((f) => (
              <AlertBadge key={f} status={f} />
            ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <Info label="Amount" value={formatMoney(sub.amount, sub.currency)} />
        <Info label="Next renewal" value={formatDate(sub.next_renewal_at)} />
        <Info label="First seen" value={formatDate(sub.first_seen_at)} />
        <Info label="Last charge" value={formatDate(sub.last_charge_at)} />
      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={() => updateStatus("cancelled")}
          className="rounded-lg bg-rose-500/90 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500"
        >
          I cancelled this
        </button>
        <button
          onClick={() => updateStatus("ignored")}
          className="rounded-lg border border-gray-600 px-4 py-2 text-sm hover:bg-gray-800"
        >
          Ignore
        </button>
        <button
          onClick={() => updateStatus("active")}
          className="rounded-lg border border-gray-600 px-4 py-2 text-sm hover:bg-gray-800"
        >
          Mark active
        </button>
      </div>

      <CorrectionForm sub={sub} onUpdated={setSub} />

      <CancelGuidePanel merchant={sub.merchant_name} />

      <h2 className="mt-10 mb-3 text-lg font-semibold">Charge history</h2>
      <div className="flex flex-col gap-2">
        {sub.history.map((c, i) => (
          <div
            key={i}
            className="flex justify-between rounded-lg border border-gray-800 px-4 py-2 text-sm"
          >
            <span className="text-gray-400">{formatDate(c.occurred_at)}</span>
            <span>{formatMoney(c.amount, sub.currency)}</span>
          </div>
        ))}
      </div>
    </main>
  );
}

function CorrectionForm({
  sub,
  onUpdated,
}: {
  sub: SubscriptionDetail;
  onUpdated: (s: SubscriptionDetail) => void;
}) {
  const router = useRouter();
  const [name, setName] = useState(sub.merchant_name);
  const [category, setCategory] = useState(sub.category ?? "");
  const [amount, setAmount] = useState(sub.amount);
  const [cadence, setCadence] = useState(sub.cadence);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function correct(field: string, value: string) {
    return api.post<SubscriptionDetail>(`/subscriptions/${sub.id}/corrections`, {
      field,
      value,
    });
  }

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      let latest: SubscriptionDetail | null = null;
      if (name.trim() && name !== sub.merchant_name) latest = await correct("merchant_name", name.trim());
      if (category !== (sub.category ?? "")) latest = await correct("category", category);
      if (amount !== sub.amount) latest = await correct("amount", amount);
      if (cadence !== sub.cadence) latest = await correct("cadence", cadence);
      if (latest) {
        onUpdated({ ...sub, ...latest });
        setMessage("Saved.");
      } else {
        setMessage("No changes to save.");
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function markNotSubscription() {
    if (!confirm("Remove this and stop treating it as a subscription?")) return;
    setSaving(true);
    try {
      await correct("not_subscription", "true");
      router.push("/dashboard");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Failed");
      setSaving(false);
    }
  }

  return (
    <section className="mt-8 rounded-xl border border-gray-800 bg-gray-900/40 p-5">
      <h2 className="text-lg font-semibold">Correct details</h2>
      <p className="mt-1 text-sm text-gray-400">
        Fix anything we got wrong. Your changes stick across future scans.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <Field label="Name">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Category">
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Uncategorized"
            className="w-full rounded-md border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label={`Amount (${sub.currency})`}>
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            className="w-full rounded-md border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Cadence">
          <select
            value={cadence}
            onChange={(e) => setCadence(e.target.value)}
            className="w-full rounded-md border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm"
          >
            {CADENCES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save changes"}
        </button>
        <button
          onClick={markNotSubscription}
          disabled={saving}
          className="text-sm text-gray-400 hover:text-rose-300 hover:underline"
        >
          Not a subscription
        </button>
        {message && <span className="text-sm text-gray-400">{message}</span>}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-gray-400">
      {label}
      {children}
    </label>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-4">
      <p className="text-sm text-gray-400">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  );
}

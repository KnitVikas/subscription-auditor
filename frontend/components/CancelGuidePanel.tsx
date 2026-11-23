"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { CancelGuide } from "@/lib/types";

const DIFFICULTY: Record<string, { label: string; className: string }> = {
  easy: { label: "Easy", className: "bg-emerald-500/15 text-emerald-300" },
  medium: { label: "Medium", className: "bg-amber-500/15 text-amber-300" },
  hard: { label: "Hard", className: "bg-rose-500/15 text-rose-300" },
};

export default function CancelGuidePanel({ merchant }: { merchant: string }) {
  const [guide, setGuide] = useState<CancelGuide | null>(null);

  useEffect(() => {
    api
      .get<CancelGuide>(`/cancel-guides/${encodeURIComponent(merchant)}`)
      .then(setGuide)
      .catch(() => setGuide(null));
  }, [merchant]);

  if (!guide) return null;
  const difficulty = DIFFICULTY[guide.difficulty] ?? DIFFICULTY.medium;

  return (
    <section className="mt-10 rounded-xl border border-gray-800 bg-gray-900/40 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">How to cancel</h2>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${difficulty.className}`}>
          {difficulty.label}
        </span>
      </div>
      {!guide.known && (
        <p className="mt-2 text-sm text-gray-400">
          We don&apos;t have specific steps for this merchant yet, so here are
          general instructions.
        </p>
      )}
      <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-gray-300">
        {guide.steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
      {guide.url && (
        <a
          href={guide.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400"
        >
          Open cancellation page
        </a>
      )}
    </section>
  );
}

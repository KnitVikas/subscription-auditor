"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import ConnectGmailButton from "@/components/ConnectGmailButton";

function ConnectInner() {
  const params = useSearchParams();
  const status = params.get("status");
  const connected = status === "connected";
  const syncFailed = status === "sync_failed";

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-6 px-6 text-center">
      <h1 className="text-3xl font-bold">Connect your inbox</h1>
      <p className="text-gray-400">
        We request <strong>read-only</strong> access to find receipt and renewal
        emails. We never send email on your behalf, and we only store the
        extracted charge details, not your email contents.
      </p>

      {connected ? (
        <div className="flex flex-col items-center gap-4">
          <div className="rounded-lg bg-emerald-500/15 px-4 py-3 text-emerald-300">
            Gmail connected. We are scanning your inbox now.
          </div>
          <Link
            href="/dashboard"
            className="rounded-lg bg-indigo-500 px-5 py-2.5 font-medium text-white hover:bg-indigo-400"
          >
            Go to dashboard
          </Link>
        </div>
      ) : syncFailed ? (
        <div className="flex flex-col items-center gap-4">
          <div className="rounded-lg bg-amber-500/15 px-4 py-3 text-amber-300">
            Gmail connected, but the first inbox scan failed. Try connecting
            again in a few minutes.
          </div>
          <ConnectGmailButton />
          <Link href="/dashboard" className="text-sm text-gray-400 hover:underline">
            Go to dashboard
          </Link>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <ConnectGmailButton />
          <Link href="/dashboard" className="text-sm text-gray-400 hover:underline">
            Skip for now
          </Link>
        </div>
      )}
    </main>
  );
}

export default function ConnectPage() {
  return (
    <Suspense>
      <ConnectInner />
    </Suspense>
  );
}

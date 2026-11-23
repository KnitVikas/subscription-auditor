import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-4xl font-bold">Subscription Auditor</h1>
      <p className="text-lg text-gray-400">
        Connect your inbox and find every recurring charge, including the ones
        you forgot about.
      </p>
      <div className="flex gap-4">
        <Link
          href="/signup"
          className="rounded-lg bg-indigo-500 px-5 py-2.5 font-medium text-white hover:bg-indigo-400"
        >
          Get started
        </Link>
        <Link
          href="/login"
          className="rounded-lg border border-gray-600 px-5 py-2.5 font-medium hover:bg-gray-800"
        >
          Log in
        </Link>
      </div>
    </main>
  );
}

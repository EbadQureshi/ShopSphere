"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearSessionToken, getSessionToken } from "@/lib/api";
import { useNotifications } from "@/components/Notifications";

type User = { id: number; name: string; email: string; is_admin: boolean };

export default function Account() {
  const router = useRouter();
  const notify = useNotifications();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getSessionToken()) {
      setLoading(false);
      return;
    }
    api.me()
      .then(setUser)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Could not load account details.");
      })
      .finally(() => setLoading(false));
  }, []);

  function signOut() {
    clearSessionToken();
    notify("You have been signed out.");
    router.push("/login");
  }

  if (loading) return <main className="mx-auto max-w-2xl px-5 py-20">Loading account...</main>;
  if (!getSessionToken()) {
    return <main className="mx-auto max-w-md px-5 py-20 text-center"><h1 className="text-3xl font-black">Sign in to view your account</h1><Link href="/login" className="mt-6 inline-block rounded-xl bg-gray-950 px-6 py-3 font-bold text-white">Sign in</Link></main>;
  }
  if (error) return <main className="mx-auto max-w-md px-5 py-20 text-center"><h1 className="text-2xl font-black">Could not load account</h1><p className="mt-3 text-red-700">{error}</p></main>;
  if (!user) return null;

  return (
    <main className="mx-auto max-w-2xl px-5 py-20">
      <section className="rounded-3xl border bg-white p-8 shadow-sm">
        <h1 className="text-3xl font-black">Your account</h1>
        <dl className="mt-8 space-y-5">
          <div><dt className="text-sm text-gray-500">Name</dt><dd className="mt-1 font-semibold">{user.name}</dd></div>
          <div><dt className="text-sm text-gray-500">Email</dt><dd className="mt-1 font-semibold">{user.email}</dd></div>
          <div><dt className="text-sm text-gray-500">Account type</dt><dd className="mt-1 font-semibold">{user.is_admin ? "Administrator" : "Customer"}</dd></div>
        </dl>
        <button type="button" onClick={signOut} className="mt-8 rounded-xl bg-gray-950 px-6 py-3 font-bold text-white hover:bg-orange-500">Sign out</button>
      </section>
    </main>
  );
}

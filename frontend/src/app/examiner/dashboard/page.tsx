"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Examiner {
  id: number;
  full_name: string;
  email: string;
  department?: string | null;
  role: "examiner";
  is_active: boolean;
}

const navigation = [
  {
    title: "Question Bank",
    description: "Open the shared Question Bank section, including all question-bank subsections and options.",
    href: "/admin/sections/question-banks",
  },
  {
    title: "Examinations",
    description: "Create and manage examinations created by your account.",
    href: "/admin/sections/examinations",
  },
  {
    title: "Account Management",
    description: "Manage your personal details, password, and recent login history.",
    href: "/account/management",
  },
];

export default function ExaminerDashboardPage() {
  const router = useRouter();
  const [examiner, setExaminer] = useState<Examiner | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) {
        router.replace("/login");
        return;
      }

      const response = await fetch(`${API_URL}/users/me`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error("Unable to load examiner account information.");
      }

      const currentUser: Examiner = await response.json();
      if (currentUser.role !== "examiner") {
        router.replace("/login");
        return;
      }
      setExaminer(currentUser);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load examiner dashboard.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  function handleLogout() {
    localStorage.removeItem("examguard_access_token");
    localStorage.removeItem("examguard_user");
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <p className="text-slate-300">Loading examiner dashboard...</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Examiner Dashboard</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-red-400/30 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-500/10"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <section className="mb-10">
          <p className="text-sm font-semibold uppercase tracking-widest text-blue-400">
            Examiner workspace
          </p>
          <h1 className="mt-3 text-3xl font-bold">
            Welcome, {examiner?.full_name || "Examiner"}
          </h1>
          {examiner?.department && (
            <p className="mt-3 text-sm text-slate-400">Department: {examiner.department}</p>
          )}
        </section>

        {error && (
          <div role="alert" className="mb-8 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">
            {error}
          </div>
        )}

        <section aria-label="Available sections">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {navigation.map((item) => (
              <article
                key={item.href}
                className="group rounded-xl border border-white/10 bg-slate-900 p-6 transition hover:border-blue-400/50 hover:bg-slate-800"
              >
                <h2 className="text-lg font-bold transition group-hover:text-blue-400">
                  {item.title}
                </h2>
                <p className="mt-3 text-sm leading-6 text-slate-400">{item.description}</p>
                <Link href={item.href} className="mt-5 inline-flex items-center gap-1 rounded-lg border border-blue-400/40 px-3 py-2 text-xs font-semibold text-blue-300 hover:bg-blue-500/10">View <span aria-hidden="true">→</span></Link>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

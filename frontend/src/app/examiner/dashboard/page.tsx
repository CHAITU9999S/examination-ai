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
    description: "Browse all question banks and manage the question banks you own.",
    href: "/admin/sections/question-banks",
  },
  {
    title: "Examinations",
    description: "Create and manage examinations created by your account.",
    href: "/admin/sections/examinations",
  },
  {
    title: "Results",
    description: "Review submitted answers, evaluate examinations, and publish student results.",
    href: "/examiner/results",
  },
  {
    title: "Account Management",
    description: "Manage your personal details, password, and login activity.",
    href: "/account/management",
  },
];

interface DashboardOverview {
  allQuestionBanks: number;
  myQuestionBanks: number;
  evaluationCompleted: number;
}

const emptyOverview: DashboardOverview = {
  allQuestionBanks: 0,
  myQuestionBanks: 0,
  evaluationCompleted: 0,
};

export default function ExaminerDashboardPage() {
  const router = useRouter();
  const [examiner, setExaminer] = useState<Examiner | null>(null);
  const [overview, setOverview] = useState<DashboardOverview>(emptyOverview);
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

      // Load overview figures independently so one unavailable statistic does not
      // prevent the Examiner from opening the rest of the dashboard.
      const headers = { Authorization: `Bearer ${token}` };
      const [allBanksResponse, myBanksResponse, overviewResponse] = await Promise.all([
        fetch(`${API_URL}/question-banks/browse`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/question-banks/`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams/dashboard/overview`, { headers, cache: "no-store" }),
      ]);

      const [allBanksData, myBanksData, overviewData] = await Promise.all([
        allBanksResponse.ok ? allBanksResponse.json() : Promise.resolve([]),
        myBanksResponse.ok ? myBanksResponse.json() : Promise.resolve([]),
        overviewResponse.ok ? overviewResponse.json() : Promise.resolve({ evaluation_completed: 0 }),
      ]);

      setOverview({
        allQuestionBanks: Array.isArray(allBanksData) ? allBanksData.length : 0,
        myQuestionBanks: Array.isArray(myBanksData) ? myBanksData.length : 0,
        myExaminations: 0,
        evaluationCompleted: Number(overviewData?.evaluation_completed || 0),
      });
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
        <section aria-label="Examination Overview" className="mb-10">
          <h2 className="mb-5 text-xl font-bold">Examination Overview</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { label: "All Question Banks", value: overview.allQuestionBanks },
              { label: "My Question Banks", value: overview.myQuestionBanks },
              { label: "Evaluations Completed", value: overview.evaluationCompleted },
            ].map((item) => (
              <article key={item.label} className="rounded-xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">{item.label}</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">{item.value.toLocaleString()}</p>
              </article>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">An evaluation is counted as completed only when results have been published for every currently assigned student in that examination.</p>
        </section>

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
          <h2 className="mb-5 text-xl font-bold">Management</h2>
          <div className="grid gap-5 sm:grid-cols-2">
            {navigation.map((item) => (
              <article
                key={item.href}
                className="group flex min-h-52 flex-col rounded-xl border border-white/10 bg-slate-900 p-6 transition hover:border-blue-400/50 hover:bg-slate-800"
              >
                <h2 className="text-lg font-bold transition group-hover:text-blue-400">
                  {item.title}
                </h2>
                <p className="mt-3 flex-1 text-sm leading-6 text-slate-400">{item.description}</p>
                <Link
                  href={item.href}
                  className="mt-5 inline-flex min-h-12 w-fit items-center justify-center gap-2 rounded-lg bg-cyan-600 px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:ring-offset-2 focus:ring-offset-slate-900"
                >
                  View <span aria-hidden="true">→</span>
                </Link>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

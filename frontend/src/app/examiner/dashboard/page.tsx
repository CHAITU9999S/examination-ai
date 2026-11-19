
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Examiner {
  id: number;
  full_name: string;
  email: string;
  department?: string | null;
  role: "examiner";
  is_active: boolean;
}

interface Exam {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  start_time?: string | null;
  end_time?: string | null;
}

const navigation = [
  {
    title: "Question Bank",
    description: "Create, view, and manage examination questions.",
    href: "/examiner/questions",
  },
  {
    title: "My Examinations",
    description: "Create examinations and manage their configurations.",
    href: "/examiner/exams",
  },
  {
    title: "Answer Grading",
    description: "Review and grade submitted subjective answers.",
    href: "/examiner/grading",
  },
  {
    title: "Result Publication",
    description: "Review completed grading and publish student results.",
    href: "/examiner/results",
  },
];

function formatDate(value?: string | null) {
  if (!value) return "Not scheduled";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Invalid date";
  }

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function ExaminerDashboardPage() {
  const router = useRouter();

  const [examiner, setExaminer] = useState<Examiner | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");

    if (!token) {
      router.replace("/login");
      return null;
    }

    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, [router]);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const userResponse = await fetch(`${API_URL}/users/me`, {
        method: "GET",
        headers,
      });

      if (userResponse.status === 401 || userResponse.status === 403) {
        router.replace("/login");
        return;
      }

      if (!userResponse.ok) {
        throw new Error("Unable to load examiner account information.");
      }

      const currentUser: Examiner = await userResponse.json();

      if (currentUser.role !== "examiner") {
        router.replace("/login");
        return;
      }

      setExaminer(currentUser);

      const examsResponse = await fetch(`${API_URL}/exams`, {
        method: "GET",
        headers,
      });

      if (!examsResponse.ok) {
        throw new Error("Unable to load your examinations.");
      }

      const data = await examsResponse.json();

      const examList = Array.isArray(data)
        ? data
        : Array.isArray(data.exams)
          ? data.exams
          : null;

      if (!examList) {
        throw new Error("Unexpected examination data returned by the server.");
      }

      setExams(examList);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load examiner dashboard."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  function handleLogout() {
    localStorage.removeItem("examguard_access_token");
    localStorage.removeItem("examguard_user");
    router.replace("/login");
  }

  const now = Date.now();

  const upcomingExams = exams.filter(
    (exam) =>
      exam.start_time &&
      new Date(exam.start_time).getTime() > now
  );

  const completedExams = exams.filter(
    (exam) =>
      exam.end_time &&
      new Date(exam.end_time).getTime() < now
  );

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <p className="text-slate-300">
          Loading examiner dashboard...
        </p>
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

            <p className="mt-1 text-sm text-slate-400">
              Examiner Dashboard
            </p>
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

          <p className="mt-2 text-slate-400">
            Manage your questions, examinations, and answer evaluation.
          </p>

          {examiner?.department && (
            <p className="mt-3 text-sm text-slate-500">
              Department: {examiner.department}
            </p>
          )}
        </section>

        {error && (
          <div
            role="alert"
            className="mb-8 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300"
          >
            {error}
          </div>
        )}

        <section className="mb-12">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-xl font-bold">
              Examination Overview
            </h2>

            <button
              type="button"
              onClick={loadDashboard}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10"
            >
              Refresh
            </button>
          </div>

          <div className="grid gap-5 sm:grid-cols-3">
            <article className="rounded-xl border border-white/10 bg-slate-900 p-6">
              <p className="text-sm text-slate-400">
                Total Examinations
              </p>
              <p className="mt-3 text-3xl font-bold">
                {exams.length}
              </p>
            </article>

            <article className="rounded-xl border border-white/10 bg-slate-900 p-6">
              <p className="text-sm text-slate-400">
                Upcoming Examinations
              </p>
              <p className="mt-3 text-3xl font-bold">
                {upcomingExams.length}
              </p>
            </article>

            <article className="rounded-xl border border-white/10 bg-slate-900 p-6">
              <p className="text-sm text-slate-400">
                Past Examinations
              </p>
              <p className="mt-3 text-3xl font-bold">
                {completedExams.length}
              </p>
            </article>
          </div>
        </section>

        <section className="mb-12">
          <h2 className="mb-5 text-xl font-bold">
            Examination Tools
          </h2>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="group rounded-xl border border-white/10 bg-slate-900 p-6 transition hover:border-blue-400/50 hover:bg-slate-800"
              >
                <h3 className="text-lg font-bold transition group-hover:text-blue-400">
                  {item.title}
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  {item.description}
                </p>

                <p className="mt-5 text-sm font-semibold text-blue-400">
                  Open →
                </p>
              </Link>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-xl font-bold">
            My Recent Examinations
          </h2>

          {exams.length === 0 ? (
            <p className="py-8 text-center text-slate-400">
              You have not created any examinations yet.
            </p>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Examination</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Questions</th>
                    <th className="px-4 py-3">Start Time</th>
                  </tr>
                </thead>

                <tbody>
                  {exams.slice(0, 5).map((exam) => (
                    <tr
                      key={exam.id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="px-4 py-4 font-semibold">
                        {exam.title}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.subject || "—"}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.duration_minutes} minutes
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.total_questions}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {formatDate(exam.start_time)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-5">
            <Link
              href="/examiner/exams"
              className="text-sm font-semibold text-blue-400 hover:text-blue-300"
            >
              Manage all examinations →
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}

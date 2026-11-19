
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Student {
  id: number;
  full_name: string;
  email: string;
  role: string;
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

function formatDate(value?: string | null) {
  if (!value) return "Not scheduled";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Invalid date";

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function getExamStatus(exam: Exam) {
  const now = Date.now();
  const start = exam.start_time
    ? new Date(exam.start_time).getTime()
    : null;
  const end = exam.end_time
    ? new Date(exam.end_time).getTime()
    : null;

  if (start !== null && !Number.isNaN(start) && now < start) {
    return "Upcoming";
  }

  if (end !== null && !Number.isNaN(end) && now > end) {
    return "Ended";
  }

  if (
    start !== null &&
    end !== null &&
    !Number.isNaN(start) &&
    !Number.isNaN(end)
  ) {
    return "Available";
  }

  return "Schedule unavailable";
}

export default function StudentDashboardPage() {
  const router = useRouter();

  const [student, setStudent] = useState<Student | null>(null);
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

      const [profileResponse, examsResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, {
          method: "GET",
          headers,
        }),
        fetch(`${API_URL}/exams`, {
          method: "GET",
          headers,
        }),
      ]);

      if (
        profileResponse.status === 401 ||
        profileResponse.status === 403 ||
        examsResponse.status === 401 ||
        examsResponse.status === 403
      ) {
        router.replace("/login");
        return;
      }

      if (!profileResponse.ok) {
        throw new Error("Unable to load student profile.");
      }

      if (!examsResponse.ok) {
        throw new Error("Unable to load available examinations.");
      }

      const profileData = await profileResponse.json();
      const examsData = await examsResponse.json();

      if (profileData.role !== "student") {
        router.replace("/login");
        return;
      }

      const examList = Array.isArray(examsData)
        ? examsData
        : Array.isArray(examsData.exams)
          ? examsData.exams
          : null;

      if (!examList) {
        throw new Error("Unexpected examination data returned by the server.");
      }

      setStudent(profileData);
      setExams(examList);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load dashboard."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  function logout() {
    localStorage.removeItem("examguard_access_token");
    localStorage.removeItem("examguard_user");
    router.replace("/login");
  }

  const availableCount = exams.filter(
    (exam) => getExamStatus(exam) === "Available"
  ).length;

  const upcomingCount = exams.filter(
    (exam) => getExamStatus(exam) === "Upcoming"
  ).length;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/student/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>

            <p className="mt-1 text-sm text-slate-400">
              Student Dashboard
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/student/results"
              className="rounded-lg border border-blue-400/30 px-4 py-2 text-sm font-semibold text-blue-300 transition hover:bg-blue-500/10"
            >
              My Results
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-red-400/30 px-4 py-2 text-sm text-red-300 transition hover:bg-red-500/10"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        {loading ? (
          <p className="py-16 text-center text-slate-400">
            Loading your dashboard...
          </p>
        ) : (
          <>
            <section>
              <h1 className="text-3xl font-bold">
                Welcome, {student?.full_name || "Student"}
              </h1>

              <p className="mt-2 text-slate-400">
                View your examinations and manage your online assessment activities.
              </p>

              {student && (
                <div className="mt-5 rounded-xl border border-white/10 bg-slate-900 p-5">
                  <p className="font-semibold">{student.full_name}</p>
                  <p className="mt-1 text-sm text-slate-400">
                    {student.email}
                  </p>
                  <p className="mt-1 text-xs capitalize text-blue-400">
                    {student.role}
                  </p>
                </div>
              )}
            </section>

            {error && (
              <div
                role="alert"
                className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300"
              >
                {error}
              </div>
            )}

            <section className="mt-8 grid gap-5 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">
                  Total examinations
                </p>
                <p className="mt-3 text-3xl font-bold">
                  {exams.length}
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">
                  Available now
                </p>
                <p className="mt-3 text-3xl font-bold text-green-400">
                  {availableCount}
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">
                  Upcoming
                </p>
                <p className="mt-3 text-3xl font-bold text-blue-400">
                  {upcomingCount}
                </p>
              </div>
            </section>

            <section className="mt-10 rounded-2xl border border-white/10 bg-slate-900 p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold">
                    Examination Overview
                  </h2>

                  <p className="mt-1 text-sm text-slate-400">
                    Check the examination schedule and availability.
                  </p>
                </div>

                <Link
                  href="/student/exams"
                  className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold transition hover:bg-blue-500"
                >
                  View All Examinations
                </Link>
              </div>

              {exams.length === 0 ? (
                <p className="py-10 text-center text-slate-400">
                  No examinations are currently available.
                </p>
              ) : (
                <div className="mt-6 grid gap-5 md:grid-cols-2">
                  {exams.slice(0, 4).map((exam) => {
                    const status = getExamStatus(exam);

                    return (
                      <article
                        key={exam.id}
                        className="rounded-xl border border-white/10 bg-slate-800/60 p-5"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <h3 className="font-semibold">
                            {exam.title}
                          </h3>

                          <span
                            className={`rounded-full px-3 py-1 text-xs ${
                              status === "Available"
                                ? "bg-green-500/10 text-green-300"
                                : status === "Upcoming"
                                  ? "bg-blue-500/10 text-blue-300"
                                  : status === "Ended"
                                    ? "bg-slate-700 text-slate-400"
                                    : "bg-amber-500/10 text-amber-300"
                            }`}
                          >
                            {status}
                          </span>
                        </div>

                        <p className="mt-2 text-sm text-slate-400">
                          Subject: {exam.subject || "Not specified"}
                        </p>

                        <div className="mt-4 space-y-2 text-sm text-slate-300">
                          <p>
                            Duration: {exam.duration_minutes} minutes
                          </p>

                          <p>
                            Questions: {exam.total_questions}
                          </p>

                          <p>
                            Starts: {formatDate(exam.start_time)}
                          </p>

                          <p>
                            Ends: {formatDate(exam.end_time)}
                          </p>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="mt-8 rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6">
              <h2 className="text-lg font-bold">
                Ready for your examination?
              </h2>

              <p className="mt-2 text-sm text-slate-300">
                Open the examinations page to check the schedule and start
                an eligible examination.
              </p>

              <Link
                href="/student/exams"
                className="mt-5 inline-block rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold transition hover:bg-blue-500"
              >
                Go to Examinations
              </Link>
            </section>

            <div className="mt-8 flex justify-end">
              <button
                type="button"
                onClick={loadDashboard}
                className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10"
              >
                Refresh Dashboard
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

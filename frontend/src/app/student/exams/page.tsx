
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Exam {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  start_time?: string | null;
  end_time?: string | null;
  negative_marking?: boolean;
  proctoring_enabled?: boolean;
  created_by_name?: string | null;
  created_by_role?: string | null;
}

function formatDate(value?: string | null) {
  if (!value) return "Not scheduled";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Invalid date";

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }) + " IST";
}

function getExamStatus(exam: Exam) {
  const now = Date.now();

  const start = exam.start_time
    ? new Date(exam.start_time).getTime()
    : null;

  const end = exam.end_time
    ? new Date(exam.end_time).getTime()
    : null;

  if (
    start !== null &&
    !Number.isNaN(start) &&
    now < start
  ) {
    return "Upcoming";
  }

  if (
    end !== null &&
    !Number.isNaN(end) &&
    now >= end
  ) {
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

export default function StudentExamsPage() {
  const router = useRouter();

  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [startingExamId, setStartingExamId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

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

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(`${API_URL}/exams`, {
        method: "GET",
        headers,
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load available examinations.");
      }

      const data = await response.json();

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
          : "Unable to load examinations."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadExams();
  }, [loadExams]);

  async function startExam(exam: Exam) {
    setError("");
    setMessage("");

    if (getExamStatus(exam) !== "Available") {
      setError("This examination is not currently available.");
      return;
    }

    setStartingExamId(exam.id);

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(
        `${API_URL}/exam-sessions/start/${exam.id}`,
        {
          method: "POST",
          headers,
          body: undefined,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to start this examination."
        );
      }

      const sessionId = data.session_id ?? data.id;

      const examToken =
        data.access_token ??
        data.exam_token ??
        data.exam_access_token ??
        data.token;
      const examRefreshToken = data.refresh_token;

      if (!sessionId || !examToken || !examRefreshToken) {
        throw new Error(
          "The server did not return the examination session ID and secure exam token."
        );
      }

      // Keep the examination token in this browser tab only.
      sessionStorage.setItem(
        `examguard_exam_token_${sessionId}`,
        examToken
      );
      sessionStorage.setItem(
        `examguard_exam_refresh_${sessionId}`,
        examRefreshToken
      );

      sessionStorage.setItem(
        "examguard_active_exam_session",
        String(sessionId)
      );
      sessionStorage.setItem(
        `examguard_exam_id_${sessionId}`,
        String(data.exam_id ?? exam.id)
      );

      router.push(`/student/exam/${sessionId}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to start examination."
      );
    } finally {
      setStartingExamId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link
              href="/student/dashboard"
              className="text-2xl font-bold"
            >
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>

            <p className="mt-1 text-sm text-slate-400">
              Student / Examinations
            </p>
          </div>

          <Link
            href="/student/dashboard"
            className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">
              Available Examinations
            </h1>

            <p className="mt-2 text-slate-400">
              Check your examination schedule and start an eligible exam.
            </p>
          </div>

          <button
            type="button"
            onClick={loadExams}
            disabled={loading}
            className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>

        {error && (
          <div
            role="alert"
            className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300"
          >
            {error}
          </div>
        )}

        {message && (
          <div
            role="status"
            className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-300"
          >
            {message}
          </div>
        )}

        {loading ? (
          <p className="py-16 text-center text-slate-400">
            Loading examinations...
          </p>
        ) : exams.length === 0 ? (
          <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-10 text-center">
            <h2 className="text-xl font-semibold">
              No examinations found
            </h2>

            <p className="mt-2 text-sm text-slate-400">
              There are currently no examinations available to display.
            </p>
          </section>
        ) : (
          <section className="mt-8 grid gap-6 md:grid-cols-2">
            {exams.map((exam) => {
              const status = getExamStatus(exam);
              const isStarting = startingExamId === exam.id;

              return (
                <article
                  key={exam.id}
                  className="rounded-2xl border border-white/10 bg-slate-900 p-6"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-xl font-bold">
                        {exam.title}
                      </h2>

                      <p className="mt-1 text-sm text-slate-400">
                        {exam.subject || "Subject not specified"}
                      </p>
                    </div>

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

                  <div className="mt-6 space-y-3 text-sm text-slate-300">
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">Created by</span>
                      <span className="text-right">
                        {exam.created_by_name || "Not available"}
                        {exam.created_by_role ? ` (${exam.created_by_role === "admin" ? "Admin" : "Examiner"})` : ""}
                      </span>
                    </div>

                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">Duration</span>
                      <span>{exam.duration_minutes} minutes</span>
                    </div>

                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">Questions</span>
                      <span>{exam.total_questions}</span>
                    </div>

                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">Starts</span>
                      <span className="text-right">
                        {formatDate(exam.start_time)}
                      </span>
                    </div>

                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">Ends</span>
                      <span className="text-right">
                        {formatDate(exam.end_time)}
                      </span>
                    </div>

                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">
                        Negative marking
                      </span>
                      <span>
                        {exam.negative_marking ? "Enabled" : "Disabled"}
                      </span>
                    </div>

                    <div className="flex justify-between gap-4">
                      <span className="text-slate-400">
                        AI proctoring
                      </span>
                      <span>
                        {exam.proctoring_enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => startExam(exam)}
                    disabled={status !== "Available" || startingExamId !== null}
                    className="mt-7 w-full rounded-lg bg-blue-600 px-5 py-3 font-semibold transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                  >
                    {isStarting
                      ? "Starting Examination..."
                      : status === "Available"
                        ? "Start Examination"
                        : status === "Upcoming"
                          ? "Not Started Yet"
                          : status === "Ended"
                            ? "Examination Ended"
                            : "Unavailable"}
                  </button>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}

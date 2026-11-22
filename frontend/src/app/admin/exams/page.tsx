
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
  created_by?: number | null;
  created_by_name?: string | null;
  created_by_role?: string | null;
  max_marks?: number | null;
}

function formatDate(value?: string | null): string {
  if (!value) return "Not scheduled";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Invalid date";
  }

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }) + " IST";
}

function getExamStatus(exam: Exam): string {
  const now = Date.now();

  const start = exam.start_time
    ? new Date(exam.start_time).getTime()
    : null;

  const end = exam.end_time
    ? new Date(exam.end_time).getTime()
    : null;

  if (start !== null && now < start) {
    return "Upcoming";
  }

  if (end !== null && now > end) {
    return "Completed";
  }

  if (start !== null && end !== null) {
    return "Scheduled / Available";
  }

  return "Schedule unavailable";
}

export default function AdminExamsPage() {
  const router = useRouter();

  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("newest");

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
        throw new Error("Unable to load examination records.");
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
          : "Unable to load examination records."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadExams();
  }, [loadExams]);

  const visibleExams = [...exams]
    .filter((exam) => {
      const search = searchTerm.trim().toLowerCase();
      if (!search) return true;
      return [exam.title, exam.subject, exam.created_by_name, exam.created_by_role]
        .some((value) => String(value || "").toLowerCase().includes(search));
    })
    .sort((first, second) => {
      if (sortBy === "title-asc") return first.title.localeCompare(second.title);
      if (sortBy === "title-desc") return second.title.localeCompare(first.title);
      if (sortBy === "duration-short") return first.duration_minutes - second.duration_minutes;
      if (sortBy === "duration-long") return second.duration_minutes - first.duration_minutes;
      if (sortBy === "questions-low") return first.total_questions - second.total_questions;
      if (sortBy === "questions-high") return second.total_questions - first.total_questions;
      if (sortBy === "marks-low") return (first.max_marks ?? -1) - (second.max_marks ?? -1);
      if (sortBy === "marks-high") return (second.max_marks ?? -1) - (first.max_marks ?? -1);
      if (sortBy === "oldest") return first.id - second.id;
      return second.id - first.id;
    });

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link
              href="/admin/dashboard"
              className="text-2xl font-bold"
            >
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>

            <p className="mt-1 text-sm text-slate-400">
              Administrator / Examinations
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/staff/manage-exams"
              className="rounded-lg border border-cyan-500/40 px-4 py-2.5 text-sm font-semibold text-cyan-300 hover:bg-cyan-500/10"
            >
              Manage My Examinations
            </Link>
            <Link
              href="/examiner/exams"
              className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold hover:bg-blue-500"
            >
              Create Examination
            </Link>
          </div>

          <Link
            href="/admin/dashboard"
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
              Examinations
            </h1>

            <p className="mt-2 text-slate-400">
              View all examinations and see who created each one. Manage your own examinations in the separate management section.
            </p>
          </div>

          <button
            type="button"
            onClick={loadExams}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold transition hover:bg-blue-500 disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh Examinations"}
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

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">
                All Examinations
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                {visibleExams.length} examination(s) found
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <input
                type="search"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search by name, subject, or creator"
                aria-label="Search examinations"
                className="min-w-[240px] rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
              />
              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
                aria-label="Sort examinations"
                className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="title-asc">Name A to Z</option>
                <option value="title-desc">Name Z to A</option>
                <option value="duration-short">Shortest time</option>
                <option value="duration-long">Longest time</option>
                <option value="questions-low">Fewest questions</option>
                <option value="questions-high">Most questions</option>
                <option value="marks-low">Lowest maximum marks</option>
                <option value="marks-high">Highest maximum marks</option>
              </select>
            </div>
          </div>

          {loading ? (
            <p className="py-12 text-center text-slate-400">
              Loading examinations...
            </p>
          ) : visibleExams.length === 0 ? (
            <div className="py-12 text-center">
              <p className="font-semibold text-slate-300">
                {exams.length === 0 ? "No examinations found." : "No examinations match your search."}
              </p>
            </div>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[1000px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Examination</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Created By</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Questions</th>
                    <th className="px-4 py-3">Maximum Marks</th>
                    <th className="px-4 py-3">Start Time</th>
                    <th className="px-4 py-3">End Time</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Settings</th>
                    <th className="px-4 py-3">Questions</th>
                  </tr>
                </thead>

                <tbody>
                  {visibleExams.map((exam) => (
                    <tr
                      key={exam.id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="px-4 py-4">
                        <p className="font-semibold">{exam.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Exam ID: {exam.id}
                        </p>
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.subject || "—"}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        <span className="font-medium text-white">{exam.created_by_name || "Unknown"}</span>
                        <span className="mt-1 block text-xs capitalize text-slate-400">{exam.created_by_role || "—"}</span>
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.duration_minutes} minutes
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.total_questions ?? "—"}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.max_marks === null || exam.max_marks === undefined ? "Not available yet" : exam.max_marks}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {formatDate(exam.start_time)}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {formatDate(exam.end_time)}
                      </td>

                      <td className="px-4 py-4">
                        <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-300">
                          {getExamStatus(exam)}
                        </span>
                      </td>

                      <td className="px-4 py-4">
                        <div className="space-y-1 text-xs text-slate-400">
                          <p>
                            Proctoring:{" "}
                            {exam.proctoring_enabled ? "Enabled" : "Disabled"}
                          </p>

                          <p>
                            Negative marking:{" "}
                            {exam.negative_marking ? "Enabled" : "Disabled"}
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/staff/examinations/${exam.id}`}
                            className="rounded-lg border border-white/20 px-3 py-2 text-xs text-cyan-300 hover:bg-white/10"
                          >
                            View Questions
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

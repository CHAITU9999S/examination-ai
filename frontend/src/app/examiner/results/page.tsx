"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReviewSession {
  session_id: number;
  exam_id: number;
  exam_title: string;
  student_id: number;
  student_name: string;
  submitted_at?: string | null;
  result_ready: boolean;
  is_published: boolean;
  obtained_marks?: number | null;
  total_marks?: number | null;
  percentage?: number | null;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

export default function ExaminerResultsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<ReviewSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishingId, setPublishingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/grading/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error("Unable to load submitted examination sessions.");
      }
      const data = await response.json();
      setSessions(Array.isArray(data.sessions) ? data.sessions : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sessions.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  async function publishResult(sessionId: number) {
    if (!window.confirm("Publish this result so the student can view it?")) {
      return;
    }
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    setPublishingId(sessionId);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        `${API_URL}/grading/sessions/${sessionId}/publish`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to publish this result.");
      }
      setMessage(`Result for session #${sessionId} published successfully.`);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish result.");
    } finally {
      setPublishingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/examiner/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Examiner / Result Publication</p>
          </div>
          <Link href="/examiner/dashboard" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Result Review & Publication</h1>
            <p className="mt-2 text-slate-400">
              Publish only after all subjective answers have been graded.
            </p>
          </div>
          <button
            type="button"
            onClick={loadSessions}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}
        {message && <div role="status" className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-300">{message}</div>}

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          {loading ? (
            <p className="py-12 text-center text-slate-400">Loading submitted sessions...</p>
          ) : sessions.length === 0 ? (
            <p className="py-12 text-center text-slate-400">No submitted sessions are available for review.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Examination</th>
                    <th className="px-4 py-3">Student</th>
                    <th className="px-4 py-3">Submitted</th>
                    <th className="px-4 py-3">Score</th>
                    <th className="px-4 py-3">Publication</th>
                    <th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.session_id} className="border-b border-white/5 last:border-0">
                      <td className="px-4 py-4 font-semibold">{session.exam_title}</td>
                      <td className="px-4 py-4">{session.student_name}</td>
                      <td className="px-4 py-4 text-slate-400">{formatDate(session.submitted_at)}</td>
                      <td className="px-4 py-4 tabular-nums">
                        {session.result_ready
                          ? `${session.obtained_marks} / ${session.total_marks}`
                          : "Awaiting grading"}
                      </td>
                      <td className="px-4 py-4">
                        {session.is_published ? "Published" : "Not published"}
                      </td>
                      <td className="px-4 py-4">
                        {session.is_published ? (
                          <span className="text-green-300">Student can view</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => publishResult(session.session_id)}
                            disabled={publishingId === session.session_id}
                            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold hover:bg-blue-500 disabled:opacity-50"
                          >
                            {publishingId === session.session_id ? "Publishing..." : "Publish result"}
                          </button>
                        )}
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

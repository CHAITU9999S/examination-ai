"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ExaminerActivity {
  id: number;
  actor_user_id: number;
  actor_name: string;
  action: string;
  details: Record<string, unknown>;
  created_at: string | null;
}

function formatAction(action: string) {
  return action.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function formatDate(value: string | null) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown time"
    : date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "medium" });
}

function describeActivity(log: ExaminerActivity) {
  const details = log.details || {};
  const title = typeof details.title === "string" ? details.title : "";
  const bankName = typeof details.bank_name === "string" ? details.bank_name : "";
  const examId = typeof details.exam_id === "number" ? `Exam #${details.exam_id}` : "";
  const bankId = typeof details.bank_id === "number" ? `Bank #${details.bank_id}` : "";
  const questionId = typeof details.question_id === "number" ? `Question #${details.question_id}` : "";
  return [title, bankName, examId, bankId, questionId].filter(Boolean).join(" · ") || "—";
}

export default function ExaminerActivityLogsPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<ExaminerActivity[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    try {
      const response = await fetch(`${API_URL}/admin/examiner-activity-logs`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to load Examiner activity logs.");
      if (!Array.isArray(data)) throw new Error("The server returned an invalid activity log list.");
      setLogs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Examiner activity logs.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const visibleLogs = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return [...logs]
      .filter((log) => {
        if (!term) return true;
        return [log.actor_name, log.action, formatAction(log.action), describeActivity(log), JSON.stringify(log.details || {})]
          .some((value) => String(value || "").toLowerCase().includes(term));
      })
      .sort((a, b) => {
        if (sortBy === "oldest") return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
        if (sortBy === "examiner") return a.actor_name.localeCompare(b.actor_name);
        if (sortBy === "action") return formatAction(a.action).localeCompare(formatAction(b.action));
        return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
      });
  }, [logs, searchTerm, sortBy]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/admin/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Administrator / Examiner Activity Logs</p>
          </div>
          <AdminSectionNavigation previousHref="/admin/sections/examiners" previousLabel="Examiners" />
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Examiner Activity Logs</h1>
            <p className="mt-2 text-slate-400">Examinations and question banks added, updated, or deleted by Examiners.</p>
          </div>
          <button type="button" onClick={loadLogs} disabled={loading} className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}

        <div className="mt-8 flex flex-wrap gap-3">
          <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search Examiner, action, examination, bank, or details" aria-label="Search Examiner activity logs" className="min-w-[240px] flex-1 rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort Examiner activity logs" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="examiner">Examiner A to Z</option>
            <option value="action">Action A to Z</option>
          </select>
        </div>

        <section className="mt-4 rounded-xl border border-white/10 bg-slate-900 p-5">
          {loading ? (
            <p className="py-12 text-center text-slate-400">Loading Examiner activity logs...</p>
          ) : visibleLogs.length === 0 ? (
            <p className="py-12 text-center text-slate-400">
              {logs.length === 0 ? "No Examiner examination or question-bank activity has been recorded yet." : "No activity logs match your search."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3 font-medium">Date and time</th>
                    <th className="px-4 py-3 font-medium">Examiner</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Examination / Question Bank</th>
                    <th className="px-4 py-3 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleLogs.map((log) => (
                    <tr key={log.id} className="border-b border-white/5 align-top last:border-0">
                      <td className="whitespace-nowrap px-4 py-4 text-slate-300">{formatDate(log.created_at)}</td>
                      <td className="px-4 py-4 font-medium">{log.actor_name}</td>
                      <td className="px-4 py-4">{formatAction(log.action)}</td>
                      <td className="px-4 py-4 text-slate-300">{describeActivity(log)}</td>
                      <td className="max-w-md px-4 py-4 text-xs text-slate-400">
                        <pre className="whitespace-pre-wrap break-words">{JSON.stringify(log.details || {}, null, 2)}</pre>
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

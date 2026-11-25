"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AdminSectionNavigation from "../../admin/components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Exam {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  max_marks?: number | null;
  assigned_question_count?: number;
  exam_status?: string;
  created_by?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  selection_rules?: { group_counts?: Record<string, number> } | null;
}

function formatDate(value?: string | null) {
  if (!value) return "Not assigned";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }) + " IST";
}

function statusFor(exam: Exam) {
  if (exam.exam_status === "schedule_not_assigned") return "Exam starting date and time not assigned";
  if (exam.exam_status === "scheduled") return "Scheduled — " + formatDate(exam.start_time);
  if (exam.exam_status === "ongoing") return "Exam is ongoing";
  if (exam.exam_status === "results_published") return "Result published";
  if (exam.exam_status === "completed_not_evaluated") return "Exam completed, not evaluated";
  const now = Date.now();
  const start = exam.start_time ? new Date(exam.start_time).getTime() : null;
  const end = exam.end_time ? new Date(exam.end_time).getTime() : null;
  if (start === null || end === null) return "Exam starting date and time not assigned";
  if (now < start) return "Scheduled — " + formatDate(exam.start_time);
  if (now <= end) return "Exam is ongoing";
  return "Exam schedule ended — evaluation status is shown for each student";
}

function groupSummary(exam: Exam) {
  const groups = exam.selection_rules?.group_counts;
  if (!groups) return "Question type and difficulty counts configured in the examination";
  return Object.entries(groups).filter(([, count]) => Number(count) > 0).map(([key, count]) => {
    const [difficulty, type] = key.split("|");
    return `${type.replaceAll("_", " ")} / ${difficulty}: ${count}`;
  }).join(" · ") || "No type/difficulty breakdown configured";
}

export default function ManageExamsPage() {
  const router = useRouter();
  const [exams, setExams] = useState<Exam[]>([]);
  const [dashboardHref, setDashboardHref] = useState("/examiner/dashboard");
  const [previousHref, setPreviousHref] = useState("/examiner/dashboard");
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("newest");

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return null; }
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  }, [router]);

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const [profileResponse, examsResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams?mine=true`, { headers, cache: "no-store" }),
      ]);
      if (profileResponse.status === 401 || examsResponse.status === 401) { router.replace("/login"); return; }
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await examsResponse.json().catch(() => []);
      if (!profileResponse.ok || !examsResponse.ok) throw new Error(data.detail || "Unable to load your examinations.");
      if (profile.role !== "admin" && profile.role !== "examiner") { router.replace("/login"); return; }
      const admin = profile.role === "admin";
      setIsAdmin(admin);
      setDashboardHref(admin ? "/admin/dashboard" : "/examiner/dashboard");
      setPreviousHref(admin ? "/admin/sections/examinations" : "/examiner/dashboard");
      const all = Array.isArray(data) ? data : Array.isArray(data.exams) ? data.exams : [];
      setExams(all.filter((exam: Exam) => Number(exam.created_by) === Number(profile.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load your examinations.");
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => { void loadExams(); }, [loadExams]);

  const visibleExams = useMemo(() => [...exams]
    .filter((exam) => !searchTerm.trim() || [exam.title, exam.subject].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name-asc") return a.title.localeCompare(b.title);
      if (sortBy === "name-desc") return b.title.localeCompare(a.title);
      if (sortBy === "duration-asc") return a.duration_minutes - b.duration_minutes;
      if (sortBy === "duration-desc") return b.duration_minutes - a.duration_minutes;
      if (sortBy === "questions-asc") return a.total_questions - b.total_questions;
      if (sortBy === "questions-desc") return b.total_questions - a.total_questions;
      if (sortBy === "start-asc") return (a.start_time || "").localeCompare(b.start_time || "");
      if (sortBy === "start-desc") return (b.start_time || "").localeCompare(a.start_time || "");
      return b.id - a.id;
    }), [exams, searchTerm, sortBy]);

  async function deleteExam(exam: Exam) {
    if (!window.confirm(`Delete "${exam.title}" and its related examination records? This cannot be undone.`)) return;
    setWorkingId(exam.id);
    setError("");
    setMessage("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(`${API_URL}/exams/${exam.id}`, { method: "DELETE", headers });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to delete this examination.");
      setMessage(data.message || `"${exam.title}" was deleted.`);
      await loadExams();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete this examination.");
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div><Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Manage Examinations</p></div>
          <div className="flex flex-wrap items-center gap-2">
            {isAdmin ? <AdminSectionNavigation previousHref={previousHref} previousLabel="Previous Section" dashboardHref={dashboardHref} /> : <Link href={dashboardHref} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">Dashboard</Link>}
            <Link href="/examiner/exams" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-500">+ Create Examination</Link>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div><h1 className="text-3xl font-bold">Manage My Examinations</h1><p className="mt-2 text-slate-400">Only examinations created by the currently logged-in account appear here.</p></div>
          <button type="button" onClick={loadExams} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">Refresh</button>
        </div>
        {message && <div role="status" className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-300">{message}</div>}
        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleExams.length} examination(s)</p>
            <div className="flex flex-wrap gap-3">
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search examination name or subject" aria-label="Search examinations" className="min-w-[240px] rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort examinations" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                <option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name-asc">Name A to Z</option><option value="name-desc">Name Z to A</option><option value="duration-asc">Shortest duration</option><option value="duration-desc">Longest duration</option><option value="questions-asc">Fewest questions</option><option value="questions-desc">Most questions</option><option value="start-asc">Earliest start</option><option value="start-desc">Latest start</option>
              </select>
            </div>
          </div>
          {loading ? <p className="py-12 text-center text-slate-400">Loading examinations...</p> : visibleExams.length === 0 ? <p className="py-12 text-center text-slate-400">{exams.length ? "No examinations match your search." : "You have not created any examinations yet."}</p> : (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleExams.map((exam) => (
                <article key={exam.id} className="flex flex-col rounded-xl border border-white/10 bg-slate-800/60 p-5">
                  <div className="flex-1">
                    <h2 className="text-lg font-bold">{exam.title}</h2>
                    <p className="mt-1 text-sm text-slate-400">{exam.subject || "No subject"}</p>
                    <p className="mt-4 text-xs font-semibold text-cyan-300">{statusFor(exam)}</p>
                    <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div><dt className="text-xs text-slate-500">Start time</dt><dd className="mt-1 text-slate-200">{formatDate(exam.start_time)}</dd></div>
                      <div><dt className="text-xs text-slate-500">End time</dt><dd className="mt-1 text-slate-200">{formatDate(exam.end_time)}</dd></div>
                      <div><dt className="text-xs text-slate-500">Questions in bank</dt><dd className="mt-1">{exam.assigned_question_count ?? "—"}</dd></div><div><dt className="text-xs text-slate-500">Questions per student</dt><dd className="mt-1">{exam.total_questions}</dd></div>
                      <div><dt className="text-xs text-slate-500">Maximum time</dt><dd className="mt-1">{exam.duration_minutes} minutes</dd></div>
                      <div><dt className="text-xs text-slate-500">Maximum marks</dt><dd className="mt-1">{exam.max_marks ?? "Not available"}</dd></div>
                      <div><dt className="text-xs text-slate-500">Exam ID</dt><dd className="mt-1">#{exam.id}</dd></div>
                    </dl>
                    <p className="mt-4 text-xs leading-5 text-slate-400">{groupSummary(exam)}</p>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2 border-t border-white/10 pt-4">
                    <Link href={`/staff/manage-exams/${exam.id}`} className="rounded-lg bg-cyan-600 px-3 py-2 text-xs font-semibold hover:bg-cyan-500">Students & Evaluation</Link>
                    <Link href={`/examiner/exams/${exam.id}/question-bank`} className="rounded-lg border border-white/20 px-3 py-2 text-xs hover:bg-white/10">Question Bank</Link>
                    <button type="button" onClick={() => deleteExam(exam)} disabled={workingId !== null} className="rounded-lg border border-red-500/40 px-3 py-2 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-50">{workingId === exam.id ? "Deleting..." : "Delete"}</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

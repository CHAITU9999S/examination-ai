"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AdminSectionNavigation from "../components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
interface Exam {
  id: number; title: string; subject?: string | null; duration_minutes: number;
  total_questions: number; start_time?: string | null; end_time?: string | null;
  created_by_name?: string | null; created_by_role?: string | null; max_marks?: number | null;
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
  return "Exam schedule ended";
}
export default function AdminExamsPage() {
  const router = useRouter();
  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [profileResponse, examResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams`, { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await examResponse.json().catch(() => []);
      if (!profileResponse.ok || !examResponse.ok) throw new Error(data.detail || "Unable to load examinations.");
      if (profile.role !== "admin") { router.replace("/login"); return; }
      const list = Array.isArray(data) ? data : Array.isArray(data.exams) ? data.exams : [];
      setExams(list);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load examinations."); }
    finally { setLoading(false); }
  }, [router]);
  useEffect(() => { void load(); }, [load]);
  const visible = useMemo(() => [...exams].filter((exam) => !search.trim() || [exam.title, exam.subject, exam.created_by_name, exam.created_by_role].some((value) => String(value || "").toLowerCase().includes(search.trim().toLowerCase()))).sort((a,b) => {
    if (sort === "name-asc") return a.title.localeCompare(b.title);
    if (sort === "name-desc") return b.title.localeCompare(a.title);
    if (sort === "start-asc") return (a.start_time || "").localeCompare(b.start_time || "");
    if (sort === "start-desc") return (b.start_time || "").localeCompare(a.start_time || "");
    if (sort === "duration-asc") return a.duration_minutes - b.duration_minutes;
    if (sort === "duration-desc") return b.duration_minutes - a.duration_minutes;
    return b.id - a.id;
  }), [exams, search, sort]);
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Examinations — read only</p></div>
        <AdminSectionNavigation previousHref="/admin/sections/examinations" previousLabel="Previous Section" />
      </div></header>
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-3xl font-bold">Examinations</h1><p className="mt-2 text-slate-400">All examinations created by Admins and Examiners. This area is for viewing only.</p></div><button type="button" onClick={load} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">Refresh</button></div>
        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-400">{visible.length} examination(s)</p><div className="flex flex-wrap gap-3">
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search exam, subject, or creator" aria-label="Search examinations" className="min-w-[240px] rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"/>
            <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort examinations" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name-asc">Name A to Z</option><option value="name-desc">Name Z to A</option><option value="start-asc">Earliest start</option><option value="start-desc">Latest start</option><option value="duration-asc">Shortest duration</option><option value="duration-desc">Longest duration</option></select>
          </div></div>
          {loading ? <p className="py-12 text-center text-slate-400">Loading examinations...</p> : visible.length === 0 ? <p className="py-12 text-center text-slate-400">{exams.length ? "No examinations match your search." : "No examinations found."}</p> : (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{visible.map((exam) => (
              <article key={exam.id} className="flex flex-col rounded-xl border border-white/10 bg-slate-800/60 p-5">
                <div className="flex-1"><h2 className="text-lg font-bold">{exam.title}</h2><p className="mt-1 text-sm text-slate-400">{exam.subject || "No subject"}</p>
                  <p className="mt-4 text-xs font-semibold text-cyan-300">{statusFor(exam)}</p>
                  <p className="mt-3 text-sm text-slate-300">Created by: <span className="font-semibold text-white">{exam.created_by_name || "Unknown"}</span> <span className="capitalize text-slate-400">({exam.created_by_role || "—"})</span></p>
                  <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div><dt className="text-xs text-slate-500">Start</dt><dd className="mt-1">{formatDate(exam.start_time)}</dd></div><div><dt className="text-xs text-slate-500">End</dt><dd className="mt-1">{formatDate(exam.end_time)}</dd></div>
                    <div><dt className="text-xs text-slate-500">Questions in bank</dt><dd className="mt-1">{exam.assigned_question_count ?? "—"}</dd></div><div><dt className="text-xs text-slate-500">Questions per student</dt><dd className="mt-1">{exam.total_questions}</dd></div><div><dt className="text-xs text-slate-500">Maximum time</dt><dd className="mt-1">{exam.duration_minutes} minutes</dd></div>
                    <div><dt className="text-xs text-slate-500">Maximum marks</dt><dd className="mt-1">{exam.max_marks ?? "Not available"}</dd></div><div><dt className="text-xs text-slate-500">Exam ID</dt><dd className="mt-1">#{exam.id}</dd></div>
                  </dl>
                  {exam.selection_rules?.group_counts && <p className="mt-4 text-xs text-slate-400">{Object.entries(exam.selection_rules.group_counts).filter(([,n]) => n > 0).map(([key,n]) => `${key.replace("|"," / ")}: ${n}`).join(" · ")}</p>}
                </div>
                <div className="mt-5 border-t border-white/10 pt-4"><Link href={`/admin/exams/${exam.id}`} className="inline-flex rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold hover:bg-cyan-500">View Examination & Students</Link></div>
              </article>
            ))}</div>
          )}
        </section>
      </div>
    </main>
  );
}

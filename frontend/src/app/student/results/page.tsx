"use client";
import { formatISTDateTime } from "@/lib/utils";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
interface QuestionGroup {
  difficulty: string; question_type: string; count: number;
  marks_per_question: number; negative_marks_per_question: number;
  question_time_limit_seconds?: number | null;
}
interface ExamResultItem {
  id: number; title: string; subject?: string | null; creator_name: string;
  creator_role?: string | null; assigned_by_name?: string | null; assigned_by_role?: string | null; duration_minutes: number; total_questions: number;
  question_breakdown: QuestionGroup[]; maximum_marks: number;
  negative_marking: boolean; total_possible_negative_marks: number;
  start_time?: string | null; end_time?: string | null;
  session_id?: number | null; category: string; submitted_at?: string | null;
  result_published: boolean; obtained_marks?: number | null;
  negative_marks?: number | null; result_total_marks?: number | null;
  percentage?: number | null; grade?: string | null; published_at?: string | null;
  instructions: string[]; randomize_questions: boolean; proctoring_enabled: boolean;
}
function formatDate(value?: string | null) {
  return formatISTDateTime(value, "—");
}
export default function StudentResultsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ExamResultItem[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("latest");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loadResults = useCallback(async () => {
    setLoading(true); setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    try {
      const response = await fetch(API_URL + "/exams/student-overview", {
        headers: { Authorization: "Bearer " + token }, cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) { router.replace("/login"); return; }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to load your examination history.");
      }
      const data = await response.json();
      if (!Array.isArray(data.examinations)) throw new Error("Unexpected examination data returned by the server.");
      const now = Date.now();
      setItems(data.examinations.filter((exam: ExamResultItem) =>
        exam.end_time && new Date(exam.end_time).getTime() <= now
      ).sort((a: ExamResultItem, b: ExamResultItem) =>
        new Date(b.end_time || 0).getTime() - new Date(a.end_time || 0).getTime()
      ));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load results."); }
    finally { setLoading(false); }
  }, [router]);
  useEffect(() => { loadResults(); }, [loadResults]);
  const completedCount = useMemo(() => items.filter(item => item.category === "completed").length, [items]);
  const visibleItems = useMemo(() => [...items]
    .filter((item) => !searchTerm.trim() || [
      item.title, item.subject, item.creator_name, item.assigned_by_name,
    ].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "oldest") return new Date(a.end_time || 0).getTime() - new Date(b.end_time || 0).getTime();
      if (sortBy === "name") return a.title.localeCompare(b.title);
      if (sortBy === "completed") return Number(b.category === "completed") - Number(a.category === "completed");
      if (sortBy === "marks") return Number(b.obtained_marks || 0) - Number(a.obtained_marks || 0);
      return new Date(b.end_time || 0).getTime() - new Date(a.end_time || 0).getTime();
    }), [items, searchTerm, sortBy]);
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div><Link href="/student/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Student / Results</p></div>
        <Link href="/student/dashboard" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Dashboard</Link>
      </div></header>
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div><h1 className="text-3xl font-bold">Examination Results</h1><p className="mt-2 text-slate-400">Scheduled examinations whose end time has passed, including completed and expired attempts.</p></div>
          <button type="button" onClick={loadResults} disabled={loading} className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50">{loading ? "Refreshing..." : "Refresh"}</button>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-slate-900 p-5"><p className="text-sm text-slate-400">Examinations with ended schedules</p><p className="mt-2 text-3xl font-bold">{items.length}</p></div>
          <div className="rounded-xl border border-white/10 bg-slate-900 p-5"><p className="text-sm text-slate-400">Completed</p><p className="mt-2 text-3xl font-bold text-emerald-300">{completedCount}</p></div>
          <div className="rounded-xl border border-white/10 bg-slate-900 p-5"><p className="text-sm text-slate-400">Results published</p><p className="mt-2 text-3xl font-bold text-blue-300">{items.filter(item => item.result_published).length}</p></div>
        </div>
        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}
        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleItems.length} of {items.length} examination(s)</p>
            <div className="flex flex-wrap gap-3">
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search exam, subject, creator, or assigner" aria-label="Search examination results" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort examination results" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                <option value="latest">Latest ended first</option><option value="oldest">Earliest ended first</option><option value="name">Exam name A to Z</option><option value="completed">Completed first</option><option value="marks">Highest obtained marks</option>
              </select>
            </div>
          </div>
          {loading ? <p className="py-12 text-center text-slate-400">Loading examination history...</p> :
            visibleItems.length === 0 ? <p className="py-12 text-center text-slate-400">{items.length === 0 ? "No examination schedules have ended yet." : "No results match your search."}</p> :
            <div className="grid gap-5 xl:grid-cols-2">{visibleItems.map(exam => <article key={exam.id} className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">{exam.title}</h2><p className="mt-1 text-sm text-slate-400">{exam.subject || "Subject not specified"}</p></div>
                <span className={"rounded-full px-3 py-1 text-xs " + (exam.category === "completed" ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300")}>{exam.category === "completed" ? "Completed" : "Expired"}</span>
              </div>
              <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                <p><span className="text-slate-500">Created by:</span> {exam.creator_name} {exam.creator_role ? "(" + exam.creator_role + ")" : ""}</p>
                <p><span className="text-slate-500">Assigned by:</span> {exam.assigned_by_name || "Unknown"} {exam.assigned_by_role ? "(" + exam.assigned_by_role + ")" : ""}</p>
                <p><span className="text-slate-500">Duration:</span> {exam.duration_minutes} minutes</p>
                <p><span className="text-slate-500">Questions:</span> {exam.total_questions}</p>
                <p><span className="text-slate-500">Maximum marks:</span> {exam.maximum_marks}</p>
                <p><span className="text-slate-500">Scheduled start:</span> {formatDate(exam.start_time)}</p>
                <p><span className="text-slate-500">Scheduled end:</span> {formatDate(exam.end_time)}</p>
                <p><span className="text-slate-500">Negative marking:</span> {exam.negative_marking ? "Enabled" : "Disabled"}</p>
              </div>
              {exam.question_breakdown.length > 0 && <div className="mt-4 rounded-lg border border-white/10 bg-slate-900 p-3"><p className="text-xs font-semibold text-slate-300">Question breakdown</p><div className="mt-2 flex flex-wrap gap-2">{exam.question_breakdown.map((group, index) =>
                <span key={index} className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-300">{group.question_type.replaceAll("_", " ")} · {group.difficulty} · {group.count} × {group.marks_per_question} marks</span>)}</div></div>}
              <p className="mt-3 text-sm text-slate-400">Question order: {exam.randomize_questions ? "Randomized" : "Configured order"} · AI proctoring: {exam.proctoring_enabled ? "Enabled" : "Disabled"}</p>
              {exam.instructions.length > 0 && <div className="mt-4 rounded-lg border border-blue-400/20 bg-blue-500/5 p-3">
                <p className="text-sm font-semibold text-blue-200">Creator instructions</p>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-300">{exam.instructions.map((instruction, index) => <li key={index}>{instruction}</li>)}</ul>
              </div>}
              <div className="mt-5 rounded-lg border border-white/10 bg-slate-900 p-4">
                {exam.result_published ? <>
                  <p className="text-sm font-semibold text-emerald-300">Result Published</p>
                  <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    <p>Obtained marks: <strong>{exam.obtained_marks ?? "—"}</strong></p>
                    <p>Negative marks: <strong>{exam.negative_marks ?? "0"}</strong></p>
                    <p>Total marks: <strong>{exam.result_total_marks ?? exam.maximum_marks}</strong></p>
                    <p>Grade: <strong>{exam.grade || "—"}</strong></p>
                  </div>

                </> : <p className="font-semibold text-amber-300">Result Not Declared</p>}
                {exam.session_id && <Link href={"/student/results/" + exam.session_id} className="mt-4 inline-block font-semibold text-blue-300 hover:text-blue-200">View detailed performance →</Link>}
                {exam.category === "expired" && <Link href={"/student/results/exam/" + exam.id} className="mt-3 inline-block font-semibold text-cyan-300 hover:text-cyan-200">View question paper and answers →</Link>}
              </div>
            </article>)}</div>}
        </section>
      </div>
    </main>
  );
}

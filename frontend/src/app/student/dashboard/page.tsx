"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { formatISTDateTime } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TWELVE_HOURS = 12 * 60 * 60 * 1000;
interface Student { id: number; full_name: string; email: string; role: string; }
interface QuestionGroup {
  difficulty: string; question_type: string; count: number;
  marks_per_question: number; negative_marks_per_question: number;
  question_time_limit_seconds?: number | null;
}
interface Exam {
  id: number; title: string; subject?: string | null; creator_name: string;
  creator_role?: string | null; assigned_by_name?: string | null; assigned_by_role?: string | null; duration_minutes: number; total_questions: number;
  question_breakdown: QuestionGroup[]; maximum_marks: number; negative_marking: boolean;
  total_possible_negative_marks: number; randomize_questions: boolean; proctoring_enabled: boolean;
  start_time?: string | null; end_time?: string | null; instructions: string[];
  session_id?: number | null; session_status?: string | null; is_paused: boolean;
  is_pending: boolean; is_in_progress: boolean; can_start: boolean;
  category: "available" | "upcoming" | "completed" | "expired";
  submitted_at?: string | null; result_published: boolean;
  obtained_marks?: number | null; negative_marks?: number | null;
  result_total_marks?: number | null; percentage?: number | null; grade?: string | null;
}
function formatDate(value?: string | null) {
  if (!value) return "Not scheduled";
  return formatISTDateTime(value, "—");
}
function expiringSoon(exam: Exam) {
  if (exam.category !== "available" || !exam.end_time) return false;
  const remaining = new Date(exam.end_time).getTime() - Date.now();
  return remaining > 0 && remaining <= TWELVE_HOURS;
}
function sortByDate(items: Exam[], field: "start_time" | "end_time" | "submitted_at", direction: "asc" | "desc") {
  return [...items].sort((a, b) => {
    const av = a[field] ? new Date(a[field] as string).getTime() : (direction === "asc" ? Number.MAX_SAFE_INTEGER : 0);
    const bv = b[field] ? new Date(b[field] as string).getTime() : (direction === "asc" ? Number.MAX_SAFE_INTEGER : 0);
    return direction === "asc" ? av - bv : bv - av;
  });
}
function ExamCard({ exam, action }: { exam: Exam; action: ReactNode }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="text-lg font-bold">{exam.title}</h3><p className="mt-1 text-sm text-slate-400">{exam.subject || "Subject not specified"}</p></div>
        <div className="flex flex-wrap gap-2">
          {expiringSoon(exam) && <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs text-amber-300">Expiring Soon</span>}
          {exam.is_pending && <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs text-amber-300">Pending</span>}
          {exam.is_in_progress && <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-300">In Progress</span>}
          {!expiringSoon(exam) && !exam.is_pending && !exam.is_in_progress && <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs capitalize text-blue-300">{exam.category}</span>}
        </div>
      </div>
      <div className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
        <p><span className="text-slate-500">Created by:</span> {exam.creator_name} {exam.creator_role ? "(" + exam.creator_role + ")" : ""}</p>
        <p><span className="text-slate-500">Assigned by:</span> {exam.assigned_by_name || "Unknown"} {exam.assigned_by_role ? "(" + exam.assigned_by_role + ")" : ""}</p>
        <p><span className="text-slate-500">Duration:</span> {exam.duration_minutes} minutes</p>
        <p><span className="text-slate-500">Questions:</span> {exam.total_questions}</p>
        <p><span className="text-slate-500">Maximum marks:</span> {exam.maximum_marks}</p>
        <p><span className="text-slate-500">Starts:</span> {formatDate(exam.start_time)}</p>
        <p><span className="text-slate-500">Ends:</span> {formatDate(exam.end_time)}</p>
        <p><span className="text-slate-500">Negative marking:</span> {exam.negative_marking ? "Enabled (maximum penalty " + exam.total_possible_negative_marks + ")" : "Disabled"}</p>
        <p><span className="text-slate-500">Question order:</span> {exam.randomize_questions ? "Randomized" : "Configured order"}</p>
        <p><span className="text-slate-500">AI proctoring:</span> {exam.proctoring_enabled ? "Enabled" : "Disabled"}</p>
      </div>
      {exam.question_breakdown.length > 0 && <div className="mt-5 rounded-xl border border-white/10 bg-slate-800/60 p-4">
        <h4 className="text-sm font-semibold">Question type and difficulty</h4>
        <div className="mt-3 flex flex-wrap gap-2">{exam.question_breakdown.map((group, index) =>
          <span key={index} className="rounded-lg bg-slate-700 px-3 py-2 text-xs text-slate-200">
            {group.question_type.replaceAll("_", " ")} · {group.difficulty} · {group.count} × {group.marks_per_question} marks{exam.negative_marking && group.negative_marks_per_question > 0 ? " · −" + group.negative_marks_per_question + " each" : ""}
          </span>)}</div>
        {exam.question_breakdown.some(group => group.question_time_limit_seconds) && <p className="mt-3 text-xs text-slate-400">
          Per-question time limits: {exam.question_breakdown.filter(group => group.question_time_limit_seconds).map(group =>
            group.question_type + " (" + group.difficulty + "): " + group.question_time_limit_seconds + "s").join("; ")}
        </p>}
      </div>}
      {exam.instructions.length > 0 && <div className="mt-5 rounded-xl border border-blue-400/20 bg-blue-500/5 p-4">
        <h4 className="text-sm font-semibold text-blue-200">Instructions from examination creator</h4>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-300">
          {exam.instructions.map((instruction, index) => <li key={index}>{instruction}</li>)}
        </ul>
      </div>}
      {exam.category === "completed" && <div className="mt-5 rounded-xl border border-white/10 bg-slate-800/60 p-4">
        {exam.result_published ? <>
          <p className="text-sm font-semibold text-emerald-300">Result Published</p>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <p>Obtained marks: <strong>{exam.obtained_marks ?? "—"}</strong></p>
            <p>Negative marks: <strong>{exam.negative_marks ?? "0"}</strong></p>
            <p>Total marks: <strong>{exam.result_total_marks ?? exam.maximum_marks}</strong></p>
            <p>Grade: <strong>{exam.grade || "—"}</strong></p>
          </div>
        </> : <p className="text-sm font-semibold text-amber-300">Result Not Declared</p>}
        {exam.session_id && <Link href={"/student/results/" + exam.session_id} className="mt-3 inline-block text-sm font-semibold text-blue-300 hover:text-blue-200">View detailed performance →</Link>}
      </div>}
      <div className="mt-6">{action}</div>
    </article>
  );
}
export default function StudentDashboardPage() {
  const router = useRouter();
  const [student, setStudent] = useState<Student | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [startingExamId, setStartingExamId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("nearest");
  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return null; }
    return { Authorization: "Bearer " + token, "Content-Type": "application/json" };
  }, [router]);
  const loadDashboard = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const headers = getHeaders(); if (!headers) return;
      const responses = await Promise.all([
        fetch(API_URL + "/users/me", { headers, cache: "no-store" }),
        fetch(API_URL + "/exams/student-overview", { headers, cache: "no-store" }),
      ]);
      const profileResponse = responses[0]; const overviewResponse = responses[1];
      if ([profileResponse.status, overviewResponse.status].some(value => value === 401 || value === 403)) { router.replace("/login"); return; }
      if (!profileResponse.ok) throw new Error("Unable to load student profile.");
      if (!overviewResponse.ok) {
        const data = await overviewResponse.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to load your examinations.");
      }
      const profile = await profileResponse.json(); const overview = await overviewResponse.json();
      if (profile.role !== "student") { router.replace("/login"); return; }
      if (!Array.isArray(overview.examinations)) throw new Error("Unexpected examination data returned by the server.");
      setStudent(profile); setExams(overview.examinations);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load dashboard."); }
    finally { setLoading(false); }
  }, [getHeaders, router]);
  useEffect(() => { loadDashboard(); }, [loadDashboard]);
  function logout() {
    localStorage.removeItem("examguard_access_token"); localStorage.removeItem("examguard_user"); router.replace("/login");
  }
  const available = useMemo(() => sortByDate(exams.filter(exam => exam.category === "available"), "start_time", "asc"), [exams]);
  const upcoming = useMemo(() => sortByDate(exams.filter(exam => exam.category === "upcoming"), "start_time", "asc"), [exams]);
  const completed = useMemo(() => sortByDate(exams.filter(exam => exam.category === "completed"), "submitted_at", "desc"), [exams]);
  const expired = useMemo(() => sortByDate(exams.filter(exam => exam.category === "expired"), "end_time", "desc"), [exams]);
  const overview = useMemo(() => {
    const filtered = exams.filter(exam => (exam.title + " " + (exam.subject || "") + " " + exam.creator_name + " " + (exam.assigned_by_name || "")).toLowerCase().includes(search.toLowerCase()));
    if (sort === "latest") return sortByDate(filtered, "end_time", "desc");
    if (sort === "completed") return sortByDate(filtered, "submitted_at", "desc");
    return sortByDate(filtered, "start_time", "asc");
  }, [exams, search, sort]);
  async function startExam(exam: Exam) {
    if (startingExamId !== null) return;
    setError("");
    if (!exam.can_start) {
      setError(exam.start_time && Date.now() < new Date(exam.start_time).getTime() ? "This examination has not started yet." : "This examination is no longer available to start.");
      return;
    }
    setStartingExamId(exam.id);
    try {
      const headers = getHeaders(); if (!headers) return;
      const response = await fetch(API_URL + "/exam-sessions/start/" + exam.id, { method: "POST", headers });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 || response.status === 403) { router.replace("/login"); return; }
      if (!response.ok) throw new Error(data.detail || "Unable to start or resume this examination.");
      const sessionId = data.session_id ?? data.id;
      const examToken = data.access_token ?? data.exam_token ?? data.exam_access_token ?? data.token;
      if (!sessionId || !examToken || !data.refresh_token) throw new Error("The server did not return secure examination session credentials.");
      sessionStorage.setItem("examguard_exam_token_" + sessionId, examToken);
      sessionStorage.setItem("examguard_exam_refresh_" + sessionId, data.refresh_token);
      sessionStorage.setItem("examguard_active_exam_session", String(sessionId));
      sessionStorage.setItem("examguard_exam_id_" + sessionId, String(data.exam_id ?? exam.id));
      router.push("/student/exam/" + sessionId);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to start examination."); }
    finally { setStartingExamId(null); }
  }
  const section = (title: string, count: number, description: string, items: Exam[], kind: Exam["category"]) => (
    <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
      <div><h2 className="text-xl font-bold">{title} <span className="ml-2 text-blue-300">({count})</span></h2><p className="mt-1 text-sm text-slate-400">{description}</p></div>
      {items.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">No examinations in this section.</p> :
        <div className="mt-5 grid gap-5 xl:grid-cols-2">{items.map(exam => <ExamCard key={exam.id} exam={exam} action={
          kind === "available" ? <button type="button" onClick={() => startExam(exam)} disabled={!exam.can_start || startingExamId !== null}
            className="min-h-12 w-full rounded-lg bg-cyan-600 px-6 py-3 text-sm font-bold text-white transition hover:bg-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
            {startingExamId === exam.id ? "Opening Examination..." : exam.is_pending || exam.is_in_progress ? "Resume Examination" : exam.can_start ? "Start Examination" : "Not Started Yet"}
          </button> :
          kind === "completed" ? <button type="button" disabled className="w-full cursor-not-allowed rounded-lg bg-emerald-900/50 px-5 py-3 font-semibold text-emerald-300">Completed</button> :
          kind === "expired" ? <button type="button" disabled className="w-full cursor-not-allowed rounded-lg bg-red-900/50 px-5 py-3 font-semibold text-red-300">Expired</button> :
          <p className="rounded-lg border border-white/10 px-4 py-3 text-center text-sm text-slate-400">Schedule not assigned yet · Start button unavailable</p>
        } />)}</div>}
    </section>
  );
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div><Link href="/student/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Student Dashboard</p></div>
        <div className="flex flex-wrap items-center gap-3"><Link href="/student/results" className="rounded-lg border border-cyan-400/35 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 transition hover:border-cyan-300/60 hover:bg-cyan-500/20 focus:outline-none focus:ring-2 focus:ring-cyan-300">Results</Link>
          <Link href="/account/management" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">Account Management</Link>
          <button type="button" onClick={logout} className="rounded-lg border border-red-400/30 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10">Logout</button></div>
      </div></header>
      <div className="mx-auto max-w-7xl px-6 py-10">
        {loading ? <p className="py-16 text-center text-slate-400">Loading your dashboard...</p> : <>
          <section><h1 className="text-3xl font-bold">Welcome, {student?.full_name || "Student"}</h1>
            <p className="mt-2 text-slate-400">View your assigned examinations, schedules, progress, and published results.</p>
            {student && <div className="mt-5 rounded-xl border border-white/10 bg-slate-900 p-5"><p className="font-semibold">{student.full_name}</p><p className="mt-1 text-sm text-slate-400">{student.email}</p><p className="mt-1 text-xs capitalize text-blue-400">{student.role}</p></div>}
          </section>
          {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}
          <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Examination Overview</h2><p className="mt-1 text-sm text-slate-400">All assigned examinations across the four sections.</p></div>
              <button type="button" onClick={loadDashboard} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">Refresh</button></div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search by exam, subject, or creator" className="rounded-lg border border-white/15 bg-slate-800 px-4 py-3 text-sm text-white outline-none focus:border-blue-400" />
              <select value={sort} onChange={event => setSort(event.target.value)} className="rounded-lg border border-white/15 bg-slate-800 px-4 py-3 text-sm text-white"><option value="nearest">Nearest schedule first</option><option value="latest">Latest schedule first</option><option value="completed">Latest completed first</option></select>
            </div>
            {overview.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">No matching examinations.</p> :
              <div className="mt-5 grid gap-5 xl:grid-cols-2">{overview.map(exam => <ExamCard key={exam.id} exam={exam} action={
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span className="capitalize text-slate-300">{exam.category === "available" && expiringSoon(exam) ? "Expiring Soon" : exam.is_pending ? "Pending" : exam.is_in_progress ? "In Progress" : exam.category}</span>
                  {exam.session_id ? <Link className="font-semibold text-blue-300 hover:text-blue-200" href={"/student/results/" + exam.session_id}>{exam.result_published ? "View published result →" : "View performance status →"}</Link> :
                    <span className="text-slate-500">{exam.category === "completed" ? "Result Not Declared" : ""}</span>}</div>
              } />)}</div>}
          </section>
          <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[["Available Examinations", available.length, "text-green-300"], ["Upcoming Examinations", upcoming.length, "text-blue-300"], ["Completed Examinations", completed.length, "text-emerald-300"], ["Unattempted / Expired", expired.length, "text-red-300"]].map(([label, count, color]) =>
              <div key={String(label)} className="rounded-2xl border border-white/10 bg-slate-900 p-5"><p className="text-sm text-slate-400">{label}</p><p className={"mt-3 text-3xl font-bold " + color}>{count}</p></div>)}
          </section>
          {section("Available Examinations", available.length, "Scheduled examinations you can start or resume. Expiring Soon means the scheduled end time is within the next 12 hours.", available, "available")}
          {section("Upcoming Examinations", upcoming.length, "Assigned examinations for which the creator has not assigned a complete schedule yet.", upcoming, "upcoming")}
          {section("Completed Examinations", completed.length, "Submitted or automatically submitted examinations, newest submission first.", completed, "completed")}
          {section("Unattempted / Expired Examinations", expired.length, "Examinations whose schedule ended without a completed submission.", expired, "expired")}
        </>}
      </div>
    </main>
  );
}

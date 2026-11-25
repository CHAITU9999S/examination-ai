"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Attempt {
  session_id: number;
  exam_id: number;
  exam_title: string;
  exam_subject?: string | null;
  exam_start_time?: string | null;
  exam_end_time?: string | null;
  creator_name?: string | null;
  started_at?: string | null;
  submitted_at?: string | null;
  session_status: string;
  obtained_marks?: number | null;
  total_marks?: number | null;
  percentage?: number | null;
  grade?: string | null;
  result_published: boolean;
  marks_status: string;
}

interface StudentPerformance {
  student_id: number;
  student_name: string;
  student_email: string;
  department?: string | null;
  attempts: Attempt[];
}

function dateText(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }) + " IST";
}

export default function AdminPerformancePage() {
  const router = useRouter();
  const [students, setStudents] = useState<StudentPerformance[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("name-asc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${API_URL}/admin/performance`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) throw new Error(data.detail || "Unable to load student performance.");
      setStudents(Array.isArray(data.students) ? data.students : []);
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load performance."))
      .finally(() => setLoading(false));
  }, [router]);

  const visibleStudents = useMemo(() => [...students]
    .filter((student) => {
      if (!searchTerm.trim()) return true;
      const term = searchTerm.trim().toLowerCase();
      return [student.student_name, student.student_email, student.department,
        ...student.attempts.flatMap((attempt) => [attempt.exam_title, attempt.exam_subject, attempt.creator_name])]
        .some((value) => String(value || "").toLowerCase().includes(term));
    })
    .sort((a, b) => {
      if (sortBy === "attempts-high") return b.attempts.length - a.attempts.length || a.student_name.localeCompare(b.student_name);
      if (sortBy === "attempts-low") return a.attempts.length - b.attempts.length || a.student_name.localeCompare(b.student_name);
      if (sortBy === "recent") return String(b.attempts[0]?.submitted_at || b.attempts[0]?.started_at || "").localeCompare(String(a.attempts[0]?.submitted_at || a.attempts[0]?.started_at || ""));
      return sortBy === "name-desc" ? b.student_name.localeCompare(a.student_name) : a.student_name.localeCompare(b.student_name);
    }), [students, searchTerm, sortBy]);

  const totalAttempts = students.reduce((count, student) => count + student.attempts.length, 0);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student performance</p></div>
          <AdminSectionNavigation previousHref="/admin/sections/students" previousLabel="Students" />
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-5 py-8">
        <h1 className="text-3xl font-bold">Student Performance</h1>
        <p className="mt-2 text-sm text-slate-400">Review each student's completed examination attempts, marks, and exact question paper.</p>
        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleStudents.length} student(s) · {totalAttempts} completed attempt(s)</p>
            <div className="flex flex-wrap gap-3">
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search student, department, or exam" aria-label="Search student performance" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                <option value="name-asc">Student A to Z</option><option value="name-desc">Student Z to A</option><option value="recent">Most recent attempt</option><option value="attempts-high">Most attempts</option><option value="attempts-low">Fewest attempts</option>
              </select>
            </div>
          </div>
          {loading ? <p className="py-10 text-center text-slate-400">Loading student performance...</p> : visibleStudents.length === 0 ? <p className="py-10 text-center text-slate-400">No students found.</p> : (
            <div className="space-y-5">
              {visibleStudents.map((student) => (
                <article key={student.student_id} className="rounded-xl border border-white/10 bg-slate-800/60 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><h2 className="text-lg font-semibold">{student.student_name}</h2><p className="mt-1 text-xs text-slate-400">{student.student_email} · {student.department || "Department not set"} · Student ID {student.student_id}</p></div>
                    <span className="rounded-lg bg-slate-900 px-3 py-2 text-xs text-slate-300">{student.attempts.length} attempted examination(s)</span>
                  </div>
                  {student.attempts.length === 0 ? <p className="mt-4 rounded-lg bg-slate-900/70 p-4 text-sm text-slate-400">No completed examination attempts yet.</p> : (
                    <div className="mt-4 space-y-3">
                      {student.attempts.map((attempt) => (
                        <div key={attempt.session_id} className="rounded-lg border border-white/10 bg-slate-900/80 p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div><h3 className="font-semibold">{attempt.exam_title}</h3><p className="mt-1 text-xs text-slate-400">{attempt.exam_subject || "Subject not specified"} · Created by {attempt.creator_name || "Not available"}</p></div>
                            <Link href={`/staff/manage-exams/${attempt.exam_id}/evaluation/${attempt.session_id}?view=1`} className="rounded-lg border border-cyan-400/40 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10">View Questions</Link>
                          </div>
                          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
                            <div><p className="text-xs text-slate-500">Exam date and time</p><p className="mt-1 text-slate-300">Start: {dateText(attempt.exam_start_time)}</p><p className="mt-1 text-slate-300">End: {dateText(attempt.exam_end_time)}</p></div>
                            <div><p className="text-xs text-slate-500">Student attempted</p><p className="mt-1 text-slate-300">Started: {dateText(attempt.started_at)}</p><p className="mt-1 text-slate-300">Submitted: {dateText(attempt.submitted_at)}</p></div>
                            <div><p className="text-xs text-slate-500">Marks obtained</p><p className="mt-1 font-semibold tabular-nums">{attempt.obtained_marks === null || attempt.obtained_marks === undefined ? "Not evaluated" : `${attempt.obtained_marks} / ${attempt.total_marks ?? "—"}`}</p><p className="mt-1 text-xs text-slate-400">{attempt.marks_status}{attempt.grade ? ` · Grade ${attempt.grade}` : ""}{attempt.percentage !== null && attempt.percentage !== undefined ? ` · ${Number(attempt.percentage).toFixed(2)}%` : ""}</p></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

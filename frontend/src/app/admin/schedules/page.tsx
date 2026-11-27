"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface StudentScheduleItem {
  student_id: number;
  student_name: string;
  student_email: string;
  department?: string | null;
  total_assigned_examinations: number;
  total_taken_examinations: number;
  attempts: Array<{ exam_title: string; exam_subject?: string | null }>;
}

export default function AdminSchedulesPage() {
  const router = useRouter();
  const [students, setStudents] = useState<StudentScheduleItem[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("name-asc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadStudents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) { router.replace("/login"); return; }
      const headers = { Authorization: `Bearer ${token}` };
      const [profileResponse, performanceResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/admin/student-performance`, { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await performanceResponse.json().catch(() => ({}));
      if ([profileResponse, performanceResponse].some((response) => response.status === 401 || response.status === 403)) { router.replace("/login"); return; }
      if (!profileResponse.ok) throw new Error(profile.detail || "Unable to verify your account.");
      if (!performanceResponse.ok) throw new Error(data.detail || "Unable to load student schedules.");
      if (profile.role !== "admin") { router.replace("/login"); return; }
      setStudents(Array.isArray(data.students) ? data.students : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load student schedules.");
    } finally { setLoading(false); }
  }, [router]);

  useEffect(() => { void loadStudents(); }, [loadStudents]);

  const visibleStudents = useMemo(() => [...students]
    .filter((student) => !searchTerm.trim() || [
      student.student_name, student.student_email, student.department,
      ...student.attempts.flatMap((attempt) => [attempt.exam_title, attempt.exam_subject]),
    ].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => sortBy === "name-desc"
      ? b.student_name.localeCompare(a.student_name)
      : sortBy === "assigned-high"
        ? b.total_assigned_examinations - a.total_assigned_examinations || a.student_name.localeCompare(b.student_name)
        : a.student_name.localeCompare(b.student_name)),
  [students, searchTerm, sortBy]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student Schedule</p></div>
          <AdminSectionNavigation previousHref="/admin/sections/students" previousLabel="Students" />
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h1 className="text-3xl font-bold">Student Schedule</h1><p className="mt-2 text-sm text-slate-400">Select a student to view all examinations assigned to them, including scheduled and examinations without a schedule.</p></div>
          <button type="button" onClick={loadStudents} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2.5 text-sm disabled:opacity-50">{loading ? "Refreshing..." : "Refresh Students"}</button>
        </div>
        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleStudents.length} student(s)</p>
            <div className="flex flex-wrap gap-3">
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search student or examination" aria-label="Search students or examinations" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                <option value="name-asc">Student A to Z</option><option value="name-desc">Student Z to A</option><option value="assigned-high">Most assigned examinations</option>
              </select>
            </div>
          </div>
          {loading ? <p className="py-10 text-center text-slate-400">Loading students...</p> : visibleStudents.length === 0 ? <p className="py-10 text-center text-slate-400">No students found.</p> : (
            <div className="space-y-3">
              {visibleStudents.map((student) => (
                <Link key={student.student_id} href={`/admin/student-examinations/${student.student_id}?scope=schedule`} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-800/60 p-4 hover:bg-white/5">
                  <span><span className="block font-semibold">{student.student_name}</span><span className="mt-1 block text-xs text-slate-400">{student.student_email} · {student.department || "Department not set"} · Student ID {student.student_id}</span></span>
                  <span className="flex flex-wrap items-center gap-2 text-xs"><span className="rounded-lg bg-slate-900 px-3 py-2">{student.total_assigned_examinations} assigned</span><span className="rounded-lg bg-slate-900 px-3 py-2">{student.total_taken_examinations} attempted</span><span className="font-semibold text-cyan-300">View schedule →</span></span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

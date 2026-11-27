"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { formatISTDateTime } from "@/lib/utils";
import AdminSectionNavigation from "../../components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Attempt {
  assignment_id: number;
  session_id?: number | null;
  exam_id: number;
  exam_title: string;
  exam_subject?: string | null;
  creator_name?: string | null;
  assigned_by_name?: string | null;
  assigned_at?: string | null;
  started_at?: string | null;
  submitted_at?: string | null;
  status_label: string;
  is_taken: boolean;
  total_questions: number;
  obtained_marks?: number | null;
  total_marks?: number | null;
  percentage?: number | null;
  grade?: string | null;
  result_published: boolean;
  marks_status: string;
}

interface StudentItem {
  student_id: number;
  student_name: string;
  student_email: string;
  department?: string | null;
  total_assigned_examinations: number;
  total_taken_examinations: number;
  attempts: Attempt[];
}

function dateText(value?: string | null) {
  return formatISTDateTime(value);
}

function StudentExaminationsPageContent() {
  const params = useParams<{ studentId: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const studentId = Number(params.studentId);
  const scope = search.get("scope") === "global" ? "global" : "tracking";
  const requestedReturnTo = search.get("return_to");
  const fallbackReturnTo = scope === "global" ? "/admin/student-performance" : "/admin/performance";
  const returnTo = requestedReturnTo && requestedReturnTo.startsWith("/admin/") && !requestedReturnTo.startsWith("//")
    ? requestedReturnTo
    : fallbackReturnTo;
  const [student, setStudent] = useState<StudentItem | null>(null);
  const [role, setRole] = useState<"admin" | "examiner" | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("recent");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const dashboardHref = role === "examiner" ? "/examiner/dashboard" : "/admin/dashboard";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) {
        router.replace("/login");
        return;
      }
      const headers = { Authorization: `Bearer ${token}` };
      const [profileResponse, dataResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/admin/${scope === "global" ? "student-performance" : "performance"}`, { headers, cache: "no-store" }),
      ]);
      if (profileResponse.status === 401 || profileResponse.status === 403 || dataResponse.status === 401 || dataResponse.status === 403) {
        router.replace("/login");
        return;
      }
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await dataResponse.json().catch(() => ({}));
      if (!profileResponse.ok) throw new Error(profile.detail || "Unable to verify your account.");
      if (!dataResponse.ok) throw new Error(data.detail || "Unable to load the student's examinations.");
      if (scope === "global" ? profile.role !== "admin" : !["admin", "examiner"].includes(profile.role)) {
        router.replace("/login");
        return;
      }
      const selectedStudent = (Array.isArray(data.students) ? data.students : []).find(
        (item: StudentItem) => item.student_id === studentId
      );
      if (!selectedStudent) throw new Error("This student is not available in your permitted records.");
      setRole(profile.role);
      setStudent(selectedStudent);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the student's examinations.");
    } finally {
      setLoading(false);
    }
  }, [router, scope, studentId]);

  useEffect(() => {
    if (!Number.isInteger(studentId) || studentId <= 0) {
      setError("Invalid student.");
      setLoading(false);
      return;
    }
    void load();
  }, [load, studentId]);

  const attemptedExams = useMemo(() => (student?.attempts || [])
    .filter((attempt) => attempt.is_taken)
    .filter((attempt) => !searchTerm.trim() || [
      attempt.exam_title,
      attempt.exam_subject,
      attempt.creator_name,
      attempt.assigned_by_name,
    ].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name-asc") return a.exam_title.localeCompare(b.exam_title);
      if (sortBy === "name-desc") return b.exam_title.localeCompare(a.exam_title);
      if (sortBy === "oldest") return String(a.assigned_at || "").localeCompare(String(b.assigned_at || ""));
      if (sortBy === "marks-high") return (b.obtained_marks ?? -Infinity) - (a.obtained_marks ?? -Infinity);
      return String(b.assigned_at || "").localeCompare(String(a.assigned_at || ""));
    }), [student, searchTerm, sortBy]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">{scope === "global" ? "Administrator / Student Performance" : `${role === "examiner" ? "Examiner" : "Administrator"} / Student Tracking`}</p>
          </div>
          <AdminSectionNavigation previousHref={returnTo} previousLabel="Back to Students" dashboardHref={dashboardHref} />
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-5 py-8">
        {loading ? (
          <p className="py-12 text-center text-slate-400">Loading assigned examinations...</p>
        ) : error ? (
          <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>
        ) : student ? (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold">{student.student_name}</h1>
                <p className="mt-2 text-sm text-slate-400">{student.student_email} · {student.department || "Department not set"} · Student ID {student.student_id}</p>
                <p className="mt-1 text-sm text-slate-400">{scope === "global" ? "All Admin- and Examiner-assigned examinations" : "Examinations assigned by your account only"}</p>
              </div>
              <button type="button" onClick={load} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">Refresh</button>
            </div>
            <section className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-slate-900 p-4"><p className="text-sm text-slate-400">Assigned examinations</p><p className="mt-1 text-2xl font-bold">{student.total_assigned_examinations}</p></div>
              <div className="rounded-xl border border-white/10 bg-slate-900 p-4"><p className="text-sm text-slate-400">Examinations attempted</p><p className="mt-1 text-2xl font-bold">{student.total_taken_examinations}</p></div>
              <div className="rounded-xl border border-white/10 bg-slate-900 p-4"><p className="text-sm text-slate-400">Attempted reports available</p><p className="mt-1 text-2xl font-bold">{attemptedExams.length}</p></div>
            </section>
            <section className="mt-6 rounded-2xl border border-white/10 bg-slate-900 p-5">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-slate-400">{attemptedExams.length} attempted examination(s)</p>
                <div className="flex flex-wrap gap-3">
                  <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search examinations" aria-label="Search examinations" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
                  <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort examinations" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                    <option value="recent">Recently assigned</option>
                    <option value="oldest">Oldest assigned</option>
                    <option value="name-asc">Examination A to Z</option>
                    <option value="name-desc">Examination Z to A</option>
                    <option value="marks-high">Highest marks first</option>
                  </select>
                </div>
              </div>
              {attemptedExams.length === 0 ? (
                <p className="py-10 text-center text-slate-400">No attempted examinations are available for this student in your permitted records.</p>
              ) : (
                <div className="space-y-3">
                  {attemptedExams.map((attempt) => (
                    <Link
                      key={attempt.assignment_id}
                      href={attempt.session_id ? `/staff/manage-exams/${attempt.exam_id}/evaluation/${attempt.session_id}?view=1&return_to=${encodeURIComponent(returnTo)}` : returnTo}
                      className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-800/60 p-4 hover:bg-white/5"
                    >
                      <span>
                        <span className="block font-semibold">{attempt.exam_title}</span>
                        <span className="mt-1 block text-xs text-slate-400">{attempt.exam_subject || "Subject not specified"} · Created by {attempt.creator_name || "Unknown"} · Assigned by {attempt.assigned_by_name || "Unknown"}</span>
                        <span className="mt-1 block text-xs text-slate-500">Assigned {dateText(attempt.assigned_at)} · Started {dateText(attempt.started_at)} · Submitted {dateText(attempt.submitted_at)}</span>
                        <span className="mt-1 block text-xs text-slate-400">{attempt.marks_status}</span>
                      </span>
                      <span className="flex flex-wrap items-center gap-3">
                        <span className="rounded-lg bg-green-500/10 px-3 py-2 text-xs text-green-300">{attempt.status_label}</span>
                        <span className="text-sm font-semibold text-cyan-300">{attempt.result_published && attempt.obtained_marks !== null && attempt.obtained_marks !== undefined ? `${attempt.obtained_marks} / ${attempt.total_marks} marks` : "View performance report"} →</span>
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </>
        ) : null}
      </div>
    </main>
  );
}

export default function StudentExaminationsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-slate-950 p-8 text-center text-slate-400">Loading assigned examinations...</main>}>
      <StudentExaminationsPageContent />
    </Suspense>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AdminSectionNavigation from "../components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Attempt {
  assignment_id: number;
  session_id?: number | null;
  exam_id: number;
  exam_title: string;
  exam_subject?: string | null;
  exam_start_time?: string | null;
  exam_end_time?: string | null;
  creator_name?: string | null;
  assigned_at?: string | null;
  started_at?: string | null;
  submitted_at?: string | null;
  session_status: string;
  status_label: string;
  is_started: boolean;
  is_taken: boolean;
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  partially_correct_answers: number;
  unanswered_questions: number;
  positive_marks: number;
  negative_marks: number;
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
  total_assigned_examinations: number;
  total_taken_examinations: number;
  total_started_examinations: number;
  attempts: Attempt[];
}

function dateText(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Asia/Kolkata",
      }) + " IST";
}

function marksText(value?: number | null) {
  return value === null || value === undefined ? "Not evaluated" : Number(value).toFixed(2).replace(/\.00$/, "");
}

export default function StudentTrackingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromExaminations = searchParams.get("from") === "examinations";
  const [students, setStudents] = useState<StudentPerformance[]>([]);
  const [role, setRole] = useState<"admin" | "examiner" | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("name-asc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const dashboardHref = role === "examiner" ? "/examiner/dashboard" : "/admin/dashboard";

  const loadStudents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) {
        router.replace("/login");
        return;
      }

      const headers = { Authorization: \`Bearer \${token}\` };
      const [profileResponse, performanceResponse] = await Promise.all([
        fetch(\`\${API_URL}/users/me\`, { headers, cache: "no-store" }),
        fetch(\`\${API_URL}/admin/performance\`, { headers, cache: "no-store" }),
      ]);

      if (profileResponse.status === 401 || profileResponse.status === 403 ||
          performanceResponse.status === 401 || performanceResponse.status === 403) {
        router.replace("/login");
        return;
      }

      const profile = await profileResponse.json().catch(() => ({}));
      const data = await performanceResponse.json().catch(() => ({}));
      if (!profileResponse.ok) throw new Error(profile.detail || "Unable to verify your account.");
      if (!performanceResponse.ok) throw new Error(data.detail || "Unable to load Student Tracking.");
      if (profile.role !== "admin" && profile.role !== "examiner") {
        router.replace("/login");
        return;
      }

      setRole(profile.role);
      setStudents(Array.isArray(data.students) ? data.students : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Student Tracking.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadStudents();
  }, [loadStudents]);

  const visibleStudents = useMemo(() => [...students]
    .filter((student) => {
      const term = searchTerm.trim().toLowerCase();
      if (!term) return true;
      return [
        student.student_name,
        student.student_email,
        student.department,
        ...student.attempts.flatMap((attempt) => [
          attempt.exam_title,
          attempt.exam_subject,
          attempt.creator_name,
        ]),
      ].some((value) => String(value || "").toLowerCase().includes(term));
    })
    .sort((a, b) => {
      if (sortBy === "assigned-high") return b.total_assigned_examinations - a.total_assigned_examinations || a.student_name.localeCompare(b.student_name);
      if (sortBy === "assigned-low") return a.total_assigned_examinations - b.total_assigned_examinations || a.student_name.localeCompare(b.student_name);
      if (sortBy === "taken-high") return b.total_taken_examinations - a.total_taken_examinations || a.student_name.localeCompare(b.student_name);
      if (sortBy === "taken-low") return a.total_taken_examinations - b.total_taken_examinations || a.student_name.localeCompare(b.student_name);
      if (sortBy === "recent") return String(b.attempts[0]?.assigned_at || "").localeCompare(String(a.attempts[0]?.assigned_at || ""));
      return sortBy === "name-desc" ? b.student_name.localeCompare(a.student_name) : a.student_name.localeCompare(b.student_name);
    }), [students, searchTerm, sortBy]);

  const totalAssignments = students.reduce((sum, student) => sum + student.total_assigned_examinations, 0);
  const totalTaken = students.reduce((sum, student) => sum + student.total_taken_examinations, 0);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">{role === "examiner" ? "Examiner" : "Administrator"} / Student Tracking</p>
          </div>
          <AdminSectionNavigation
            previousHref={role === "examiner" || fromExaminations ? "/admin/sections/examinations" : "/admin/sections/students"}
            previousLabel={role === "examiner" || fromExaminations ? "Examinations" : "Students"}
            dashboardHref={dashboardHref}
          />
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Student Tracking</h1>
            <p className="mt-2 text-sm text-slate-400">
              Select a student to view assigned examinations, then select an examination to see its performance summary.
            </p>
          </div>
          <button type="button" onClick={loadStudents} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">
            Refresh
          </button>
        </div>

        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}

        <section className="mt-7 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-slate-900 p-4">
            <p className="text-sm text-slate-400">Students</p>
            <p className="mt-1 text-2xl font-bold">{students.length}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900 p-4">
            <p className="text-sm text-slate-400">Assigned examinations</p>
            <p className="mt-1 text-2xl font-bold">{totalAssignments}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900 p-4">
            <p className="text-sm text-slate-400">Examinations taken</p>
            <p className="mt-1 text-2xl font-bold">{totalTaken}</p>
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleStudents.length} student(s) found</p>
            <div className="flex flex-wrap gap-3">
              <input
                type="search"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search student or examination"
                aria-label="Search students and examinations"
                className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"
              />
              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
                aria-label="Sort students"
                className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"
              >
                <option value="name-asc">Student A to Z</option>
                <option value="name-desc">Student Z to A</option>
                <option value="assigned-high">Most assigned</option>
                <option value="assigned-low">Fewest assigned</option>
                <option value="taken-high">Most examinations taken</option>
                <option value="taken-low">Fewest examinations taken</option>
                <option value="recent">Recently assigned</option>
              </select>
            </div>
          </div>

          {loading ? (
            <p className="py-10 text-center text-slate-400">Loading students and assigned examinations...</p>
          ) : visibleStudents.length === 0 ? (
            <p className="py-10 text-center text-slate-400">No students found.</p>
          ) : (
            <div className="space-y-3">
              {visibleStudents.map((student) => {
                const studentOpen = selectedStudentId === student.student_id;
                return (
                  <article key={student.student_id} className="overflow-hidden rounded-xl border border-white/10 bg-slate-800/60">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedStudentId(studentOpen ? null : student.student_id);
                        setSelectedAssignmentId(null);
                      }}
                      aria-expanded={studentOpen}
                      className="flex w-full flex-wrap items-center justify-between gap-4 p-4 text-left hover:bg-white/5"
                    >
                      <span>
                        <span className="block font-semibold">{student.student_name}</span>
                        <span className="mt-1 block text-xs text-slate-400">{student.student_email} · {student.department || "Department not set"} · Student ID {student.student_id}</span>
                      </span>
                      <span className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded-lg bg-slate-900 px-3 py-2">{student.total_assigned_examinations} assigned</span>
                        <span className="rounded-lg bg-slate-900 px-3 py-2">{student.total_taken_examinations} taken</span>
                        <span className="text-blue-300">{studentOpen ? "▲ Close" : "▼ View examinations"}</span>
                      </span>
                    </button>

                    {studentOpen && (
                      <div className="border-t border-white/10 p-4">
                        <h2 className="font-semibold">Assigned examinations for {student.student_name}</h2>
                        {student.attempts.length === 0 ? (
                          <p className="mt-3 rounded-lg bg-slate-900 p-4 text-sm text-slate-400">No examinations assigned by your account.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {student.attempts.map((attempt) => {
                              const assignmentOpen = selectedAssignmentId === attempt.assignment_id;
                              return (
                                <div key={attempt.assignment_id} className="rounded-lg border border-white/10 bg-slate-900/80">
                                  <button
                                    type="button"
                                    onClick={() => setSelectedAssignmentId(assignmentOpen ? null : attempt.assignment_id)}
                                    aria-expanded={assignmentOpen}
                                    className="flex w-full flex-wrap items-center justify-between gap-3 p-4 text-left hover:bg-white/5"
                                  >
                                    <span>
                                      <span className="block font-semibold">{attempt.exam_title}</span>
                                      <span className="mt-1 block text-xs text-slate-400">
                                        {attempt.exam_subject || "Subject not specified"} · Created by {attempt.creator_name || "Not available"} · Assigned {dateText(attempt.assigned_at)}
                                      </span>
                                    </span>
                                    <span className="flex flex-wrap items-center gap-2">
                                      <span className={attempt.is_taken ? "rounded-lg bg-green-500/10 px-3 py-2 text-xs text-green-300" : attempt.is_started ? "rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-300" : "rounded-lg bg-slate-800 px-3 py-2 text-xs text-slate-300"}>
                                        {attempt.status_label}
                                      </span>
                                      <span className="text-xs text-blue-300">{assignmentOpen ? "▲ Hide summary" : "▼ View summary"}</span>
                                    </span>
                                  </button>

                                  {assignmentOpen && (
                                    <div className="border-t border-white/10 p-4">
                                      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Questions given</p>
                                          <p className="mt-1 text-xl font-semibold">{attempt.total_questions}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Correct answers</p>
                                          <p className="mt-1 text-xl font-semibold text-green-300">{attempt.correct_answers}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Wrong answers</p>
                                          <p className="mt-1 text-xl font-semibold text-red-300">{attempt.wrong_answers}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Partially correct answers</p>
                                          <p className="mt-1 text-xl font-semibold text-amber-300">{attempt.partially_correct_answers}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Unanswered questions</p>
                                          <p className="mt-1 text-xl font-semibold">{attempt.unanswered_questions}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Positive marks</p>
                                          <p className="mt-1 text-xl font-semibold text-green-300">{marksText(attempt.positive_marks)}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-800 p-3">
                                          <p className="text-xs text-slate-400">Negative marks</p>
                                          <p className="mt-1 text-xl font-semibold text-red-300">{marksText(attempt.negative_marks)}</p>
                                        </div>
                                      </div>
                                      <div className="mt-3 grid gap-3 rounded-lg bg-slate-800 p-4 text-sm sm:grid-cols-2">
                                        <div>
                                          <p className="text-xs text-slate-400">Marks awarded</p>
                                          <p className="mt-1 text-lg font-semibold">{marksText(attempt.obtained_marks)} / {marksText(attempt.total_marks)}</p>
                                          <p className="mt-1 text-xs text-slate-400">{attempt.marks_status}{attempt.percentage !== null && attempt.percentage !== undefined ? \` · \${Number(attempt.percentage).toFixed(2)}%\` : ""}{attempt.grade ? \` · Grade \${attempt.grade}\` : ""}</p>
                                        </div>
                                        <div>
                                          <p className="text-xs text-slate-400">Examination timing</p>
                                          <p className="mt-1">Scheduled start: {dateText(attempt.exam_start_time)}</p>
                                          <p className="mt-1">Student started: {dateText(attempt.started_at)}</p>
                                          <p className="mt-1">Student submitted: {dateText(attempt.submitted_at)}</p>
                                        </div>
                                      </div>
                                      {attempt.session_id && (
                                        <Link
                                          href={\`/staff/manage-exams/\${attempt.exam_id}/evaluation/\${attempt.session_id}?view=1&return_to=%2Fadmin%2Fperformance%3Ffrom%3Dexaminations\`}
                                          className="mt-4 inline-flex rounded-lg border border-cyan-400/40 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10"
                                        >
                                          View question-by-question answers
                                        </Link>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

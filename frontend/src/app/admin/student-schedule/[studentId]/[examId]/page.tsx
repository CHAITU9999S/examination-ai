"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { formatISTDateTime } from "@/lib/utils";
import AdminSectionNavigation from "../../../components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ExamDetails {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  start_time?: string | null;
  end_time?: string | null;
  created_by_name?: string | null;
  created_by_role?: string | null;
}

export default function StudentScheduleExamDetailsPage() {
  const params = useParams<{ studentId: string; examId: string }>();
  const router = useRouter();
  const studentId = Number(params.studentId);
  const examId = Number(params.examId);
  const [exam, setExam] = useState<ExamDetails | null>(null);
  const [studentName, setStudentName] = useState("");
  const [assignment, setAssignment] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) { router.replace("/login"); return; }
      const headers = { Authorization: `Bearer ${token}` };
      const [profileResponse, examResponse, performanceResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams/${examId}`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/admin/student-performance`, { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      const examData = await examResponse.json().catch(() => ({}));
      const performance = await performanceResponse.json().catch(() => ({}));
      if ([profileResponse, examResponse, performanceResponse].some((response) => response.status === 401 || response.status === 403)) { router.replace("/login"); return; }
      if (!profileResponse.ok || !examResponse.ok || !performanceResponse.ok) throw new Error(examData.detail || performance.detail || "Unable to load examination details.");
      if (profile.role !== "admin") { router.replace("/login"); return; }
      const student = (Array.isArray(performance.students) ? performance.students : []).find((item: { student_id: number }) => Number(item.student_id) === studentId);
      const selectedAssignment = student?.attempts?.find((item: { exam_id: number }) => Number(item.exam_id) === examId);
      if (!student || !selectedAssignment) throw new Error("This examination is not assigned to the selected student.");
      setExam(examData);
      setStudentName(student.student_name);
      setAssignment(selectedAssignment);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load examination details.");
    } finally { setLoading(false); }
  }, [examId, router, studentId]);

  useEffect(() => {
    if (!Number.isInteger(studentId) || !Number.isInteger(examId) || studentId <= 0 || examId <= 0) {
      setError("Invalid student or examination.");
      setLoading(false);
      return;
    }
    void load();
  }, [examId, load, studentId]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student Schedule / Examination Details</p></div>
          <AdminSectionNavigation previousHref={`/admin/student-examinations/${studentId}?scope=schedule`} previousLabel="Back to Student Schedule" />
        </div>
      </header>
      <div className="mx-auto max-w-5xl space-y-6 px-5 py-8">
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        {loading ? <p className="py-12 text-center text-slate-400">Loading examination details...</p> : exam && assignment && (
          <>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <p className="text-sm text-cyan-300">Assigned to {studentName}</p>
              <h1 className="mt-2 text-3xl font-bold">{exam.title}</h1>
              <p className="mt-2 text-slate-400">{exam.subject || "No subject"}</p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Created by</p><p className="mt-1 font-semibold">{exam.created_by_name || "Unknown"}</p><p className="text-xs capitalize text-slate-400">{exam.created_by_role || "—"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Maximum time</p><p className="mt-1 font-semibold">{exam.duration_minutes} minutes</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Questions per student</p><p className="mt-1 font-semibold">{exam.total_questions}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Schedule starts (IST)</p><p className="mt-1 font-semibold">{formatISTDateTime(exam.start_time, "Not scheduled")}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Schedule ends (IST)</p><p className="mt-1 font-semibold">{formatISTDateTime(exam.end_time, "Not scheduled")}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Assignment status</p><p className="mt-1 font-semibold">{String(assignment.status_label || "Assigned")}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Assigned by</p><p className="mt-1 font-semibold">{String(assignment.assigned_by_name || "Unknown")}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Assigned on (IST)</p><p className="mt-1 font-semibold">{formatISTDateTime(String(assignment.assigned_at || ""))}</p></div>
              </div>
            </section>
            <p className="text-sm text-slate-400">This page shows examination details for this student. The question paper is not opened from Student Schedule.</p>
          </>
        )}
      </div>
    </main>
  );
}

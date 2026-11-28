"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AdminSectionNavigation from "../../../components/AdminSectionNavigation";
import ProctoringReportPanel from "@/components/ProctoringReportPanel";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReportQuestion {
  question_id: number;
  question_order: number;
  question_text: string;
  question_type: string;
  difficulty: string;
  maximum_marks: number;
  negative_marks?: number | null;
  awarded_marks?: number | null;
  student_answer?: string | null;
  student_selected_options?: string[];
  correct_answer?: string | null;
  correct_options?: string[];
  options?: string[];
  question_image_url?: string | null;
  expected_answer_image_url?: string | null;
  student_answer_image_url?: string | null;
}

interface StudentReport {
  exam_id: number;
  session_id?: number | null;
  exam_title: string;
  subject?: string | null;
  student_id: number;
  session_status: string;
  paper_is_preview: boolean;
  result_published: boolean;
  obtained_marks?: number | null;
  total_marks?: number | null;
  percentage?: number | null;
  grade?: string | null;
  exam_details?: {
    duration_minutes?: number | null;
    total_questions?: number | null;
    total_marks?: number | null;
    negative_marking_enabled?: boolean | null;
    proctoring_enabled?: boolean | null;
    max_tab_switch_warnings?: number | null;
    start_time?: string | null;
    end_time?: string | null;
    creator_name?: string | null;
    assigned_by_name?: string | null;
  };
  positive_marks_earned?: number | null;
  negative_marks_deducted?: number | null;
  maximum_positive_marks?: number | null;
  configured_negative_marks?: number | null;
  evaluated_questions?: number | null;
  correct_questions?: number | null;
  wrong_questions?: number | null;
  partially_correct_questions?: number | null;
  paper: ReportQuestion[];
}

export default function AdminStudentPerformanceReportPage() {
  const params = useParams<{ examId: string; studentId: string }>();
  const router = useRouter();
  const examId = Number(params.examId);
  const studentId = Number(params.studentId);
  const [report, setReport] = useState<StudentReport | null>(null);
  const [studentName, setStudentName] = useState("");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [questionImage, setQuestionImage] = useState("");
  const [expectedAnswerImage, setExpectedAnswerImage] = useState("");
  const [studentAnswerImage, setStudentAnswerImage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) { router.replace("/login"); return; }
      const headers = { Authorization: `Bearer ${token}` };
      const [profileResponse, reportResponse, performanceResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/results/exams/${examId}/students/${studentId}/paper`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/admin/student-performance`, { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await reportResponse.json().catch(() => ({}));
      const performance = await performanceResponse.json().catch(() => ({}));
      if ([profileResponse, reportResponse, performanceResponse].some((response) => response.status === 401 || response.status === 403)) {
        router.replace("/login");
        return;
      }
      if (!profileResponse.ok || !reportResponse.ok || !performanceResponse.ok) {
        throw new Error(data.detail || performance.detail || "Unable to load the examination report.");
      }
      if (profile.role !== "admin") { router.replace("/login"); return; }
      const student = (Array.isArray(performance.students) ? performance.students : []).find((item: { student_id: number }) => Number(item.student_id) === studentId);
      if (!student) throw new Error("This student is not available in Admin Student Performance.");
      setStudentName(student.student_name);
      setReport(data);
      setQuestionIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the examination report.");
    } finally { setLoading(false); }
  }, [examId, router, studentId]);

  useEffect(() => {
    if (!Number.isInteger(examId) || !Number.isInteger(studentId) || examId <= 0 || studentId <= 0) {
      setError("Invalid student or examination.");
      setLoading(false);
      return;
    }
    void load();
  }, [examId, load, studentId]);

  const question = report?.paper?.[questionIndex] || null;

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];
    const token = localStorage.getItem("examguard_access_token");
    const loadImage = async (url?: string | null) => {
      if (!url || !token) return "";
      const response = await fetch(API_URL + url, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
      if (!response.ok) return "";
      const objectUrl = URL.createObjectURL(await response.blob());
      objectUrls.push(objectUrl);
      return objectUrl;
    };
    Promise.all([
      loadImage(question?.question_image_url),
      loadImage(question?.expected_answer_image_url),
      loadImage(question?.student_answer_image_url),
    ]).then(([prompt, expected, submitted]) => {
      if (!cancelled) {
        setQuestionImage(prompt);
        setExpectedAnswerImage(expected);
        setStudentAnswerImage(submitted);
      }
    }).catch(() => {
      if (!cancelled) {
        setQuestionImage("");
        setExpectedAnswerImage("");
        setStudentAnswerImage("");
      }
    });
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [question?.question_image_url, question?.expected_answer_image_url, question?.student_answer_image_url]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student Performance Report</p></div>
          <AdminSectionNavigation previousHref={`/admin/student-examinations/${studentId}?scope=global`} previousLabel="Back to Student Examinations" />
        </div>
      </header>
      <div className="mx-auto max-w-5xl space-y-6 px-5 py-8">
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        {loading ? <p className="py-12 text-center text-slate-400">Loading student report...</p> : report && (
          <>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <p className="text-sm text-cyan-300">{studentName}</p>
              <h1 className="mt-2 text-3xl font-bold">{report.exam_title}</h1>
              <p className="mt-1 text-slate-400">{report.subject || "No subject"}</p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Session status</p><p className="mt-1 font-semibold capitalize">{report.session_status.replaceAll("_", " ")}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Total marks obtained</p><p className="mt-1 font-semibold">{report.obtained_marks ?? "Not finalised"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Maximum / total marks</p><p className="mt-1 font-semibold">{report.total_marks ?? report.exam_details?.total_marks ?? "Not available"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Result status</p><p className="mt-1 font-semibold">{report.result_published ? "Published" : "Not published"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Percentage / Grade</p><p className="mt-1 font-semibold">{report.result_published ? `${report.percentage ?? "—"}% / ${report.grade || "—"}` : "Not published"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Positive marks earned</p><p className="mt-1 font-semibold">{report.positive_marks_earned ?? "Not evaluated"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Negative marks deducted</p><p className="mt-1 font-semibold">{report.negative_marks_deducted ?? "Not evaluated"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Correct / Wrong</p><p className="mt-1 font-semibold">{report.correct_questions ?? "—"} / {report.wrong_questions ?? "—"}</p></div>
                <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Partially correct / evaluated</p><p className="mt-1 font-semibold">{report.partially_correct_questions ?? "—"} / {report.evaluated_questions ?? "—"}</p></div>
              </div>
              <div className="mt-4 rounded-xl bg-slate-800/70 p-4 text-sm text-slate-300">
                <h2 className="font-semibold text-white">Examination details</h2>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <p>Duration: {report.exam_details?.duration_minutes != null ? `${report.exam_details.duration_minutes} minutes` : "Not available"}</p>
                  <p>Questions in this paper: {report.exam_details?.total_questions ?? report.paper.length}</p>
                  <p>Positive marks available: {report.maximum_positive_marks ?? report.exam_details?.total_marks ?? "Not available"}</p>
                  <p>Configured negative marks: {report.configured_negative_marks ?? "Not available"}</p>
                  <p>Negative marking: {report.exam_details?.negative_marking_enabled == null ? "Not available" : report.exam_details.negative_marking_enabled ? "Enabled" : "Disabled"}</p>
                  <p>AI proctoring: {report.exam_details?.proctoring_enabled == null ? "Not available" : report.exam_details.proctoring_enabled ? "Enabled" : "Disabled"}</p>
                  <p>Maximum tab-switch warnings: {report.exam_details?.max_tab_switch_warnings ?? "Not available"}</p>
                  <p>Created by: {report.exam_details?.creator_name || "Not available"}</p>
                  <p>Assigned by: {report.exam_details?.assigned_by_name || "Not available"}</p>
                  <p>Starts: {report.exam_details?.start_time ? new Date(report.exam_details.start_time).toLocaleString() : "Not available"}</p>
                  <p>Ends: {report.exam_details?.end_time ? new Date(report.exam_details.end_time).toLocaleString() : "Not available"}</p>
                </div>
              </div>
            </section>
            <ProctoringReportPanel sessionId={report.session_id} />
            {report.paper_is_preview && <p className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-200">No examination session was created for this student. The questions below are a generated paper preview using the current examination selection settings; no submitted answers or marks are recorded.</p>}
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h2 className="text-xl font-bold">Assigned Question Paper</h2><p className="mt-1 text-sm text-slate-400">Question {questionIndex + 1} of {report.paper.length}</p></div>
                <span className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-cyan-300">{report.paper.length} question(s)</span>
              </div>
              {question ? (
                <article className="mt-5 rounded-xl border border-white/10 bg-slate-800/60 p-5">
                  <p className="text-xs text-cyan-300">Question {question.question_order} · {question.question_type} · {question.difficulty}</p>
                  <p className="mt-3 whitespace-pre-wrap text-base">{question.question_text}</p>
                  {questionImage && <img src={questionImage} alt="Question prompt" className="mt-4 max-h-80 rounded-lg object-contain" />}
                  {question.options?.length ? <div className="mt-4 space-y-2">{question.options.map((option, index) => <p key={index} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-200">{option}</p>)}</div> : null}
                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="rounded-lg border border-white/10 bg-slate-900 p-4"><p className="text-xs font-semibold text-cyan-300">Expected answer</p><p className="mt-2 whitespace-pre-wrap text-sm text-slate-200">{question.correct_answer || (question.correct_options?.length ? question.correct_options.join(", ") : "No expected answer configured.")}</p>{expectedAnswerImage && <img src={expectedAnswerImage} alt="Expected answer" className="mt-3 max-h-72 rounded-lg object-contain" />}</div>
                    <div className="rounded-lg border border-white/10 bg-slate-900 p-4"><p className="text-xs font-semibold text-cyan-300">Submitted answer</p><p className="mt-2 whitespace-pre-wrap text-sm text-slate-200">{question.student_selected_options?.length ? question.student_selected_options.join(", ") : question.student_answer || "Not attempted"}</p>{studentAnswerImage && <img src={studentAnswerImage} alt="Student submitted answer" className="mt-3 max-h-72 rounded-lg object-contain" />}</div>
                  </div>
                  <div className="mt-4 rounded-lg border border-white/10 bg-slate-900 p-4"><p className="text-xs text-slate-400">Final marks awarded / Maximum marks · Negative marks: {question.negative_marks ?? "Not available"}</p><p className="mt-1 text-xl font-bold">{question.awarded_marks ?? "Not finalised"} / {question.maximum_marks}</p></div>
                </article>
              ) : <p className="py-10 text-center text-slate-400">No question paper is available.</p>}
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <button type="button" onClick={() => setQuestionIndex((value) => Math.max(0, value - 1))} disabled={questionIndex <= 0} className="rounded-lg border border-white/20 px-5 py-2.5 text-sm font-semibold hover:bg-white/10 disabled:opacity-40">← Previous</button>
                <span className="text-sm text-slate-400">Question {report.paper.length ? questionIndex + 1 : 0} / {report.paper.length}</span>
                <button type="button" onClick={() => setQuestionIndex((value) => Math.min(report.paper.length - 1, value + 1))} disabled={questionIndex >= report.paper.length - 1} className="rounded-lg bg-cyan-600 px-5 py-2.5 text-sm font-semibold hover:bg-cyan-500 disabled:opacity-40">Next →</button>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

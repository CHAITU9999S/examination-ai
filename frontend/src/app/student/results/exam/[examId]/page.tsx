"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import StudentReportImage from "@/components/StudentReportImage";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PaperQuestion {
  question_id: number;
  question_text: string;
  question_type: string;
  maximum_marks: number;
  awarded_marks?: number | null;
  student_answer?: string | null;
  student_selected_options?: string[];
  correct_answer?: string | null;
  correct_options: string[];
  options: string[];
  question_image_url?: string | null;
  expected_answer_image_url?: string | null;
  student_answer_image_url?: string | null;
}
interface PaperReport {
  exam_title: string;
  subject?: string | null;
  session_status: string;
  paper: PaperQuestion[];
}

export default function StudentAssignedPaperReportPage() {
  const params = useParams<{ examId: string }>();
  const router = useRouter();
  const [report, setReport] = useState<PaperReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) { router.replace("/login"); return; }
      try {
        const response = await fetch(API_URL + "/results/exams/" + params.examId + "/paper", {
          headers: { Authorization: "Bearer " + token },
          cache: "no-store",
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Unable to load the assigned question paper.");
        }
        const data = await response.json();
        if (!cancelled) setReport(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load the question paper.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (params.examId) void load();
    return () => { cancelled = true; };
  }, [params.examId, router]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/student/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Student / Question Paper Report</p>
          </div>
          <Link href="/student/results" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Results</Link>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-6 py-10">
        {loading ? <p className="py-12 text-center text-slate-400">Loading question paper report...</p> :
          error ? <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">{error}</div> :
          report ? <>
            <h1 className="text-3xl font-bold">{report.exam_title}</h1>
            <p className="mt-2 text-slate-400">{report.subject || "Subject not specified"} · Assigned paper · {report.session_status.replaceAll("_", " ")}</p>
            <p className="mt-4 text-sm text-slate-400">This report is available after the examination ends. It shows the question paper assigned to your account, the correct answers, and any answers you submitted.</p>
            <section className="mt-8 space-y-5">
              {report.paper.map((question, index) => (
                <article key={question.question_id} className="rounded-xl border border-white/10 bg-slate-900 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Question {index + 1} · {question.question_type.replaceAll("_", " ")}</p>
                      <h2 className="mt-2 whitespace-pre-wrap font-semibold">{question.question_text}</h2>
                      {question.question_image_url && <StudentReportImage url={question.question_image_url} alt="Question image" />}
                    </div>
                    <p className="text-sm font-semibold text-slate-300">Marks: {question.awarded_marks ?? "—"} / {question.maximum_marks}</p>
                  </div>
                  {question.options.length > 0 && <div className="mt-4 space-y-2">
                    {question.options.map((option, optionIndex) => <p key={optionIndex} className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-300">{option}</p>)}
                  </div>}
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border border-white/10 bg-slate-800 p-3">
                      <p className="text-xs font-semibold text-slate-400">Your answer</p>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-200">{question.student_selected_options?.length ? question.student_selected_options.join(", ") : question.student_answer?.trim() || (question.student_answer_image_url ? "Image answer submitted" : "Not attempted")}</p>
                      {question.student_answer_image_url && <StudentReportImage url={question.student_answer_image_url} alt="Your submitted answer image" />}
                    </div>
                    <div className="rounded-lg border border-emerald-400/20 bg-emerald-500/5 p-3">
                      <p className="text-xs font-semibold text-emerald-300">Correct answer</p>
                      {question.correct_options.length > 0 ?
                        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-200">{question.correct_options.map((option, optionIndex) => <li key={optionIndex}>{option}</li>)}</ul> :
                        <p className="mt-2 whitespace-pre-wrap text-sm text-slate-200">{question.correct_answer?.trim() || "No model answer provided"}</p>}
                      {question.expected_answer_image_url && <StudentReportImage url={question.expected_answer_image_url} alt="Expected answer image" />}
                    </div>
                  </div>
                </article>
              ))}
            </section>
          </> : null}
      </div>
    </main>
  );
}

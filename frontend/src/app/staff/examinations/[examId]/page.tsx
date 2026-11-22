"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ExamDetails {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  created_by_name?: string | null;
  created_by_role?: string | null;
  can_edit?: boolean;
}
interface Question {
  question_id: number;
  question_order: number;
  question_text: string;
  question_type: string;
  difficulty: string;
  marks: number;
  options?: { id: number; option_text: string; is_correct: boolean }[];
  expected_answer?: string | null;
  model_answer_text?: string | null;
  question_time_limit_seconds?: number | null;
}

export default function ExaminationDetailsPage() {
  const params = useParams<{ examId: string }>();
  const router = useRouter();
  const examId = String(params.examId || "");
  const [exam, setExam] = useState<ExamDetails | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDetails = useCallback(async () => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    const headers = { Authorization: `Bearer ${token}` };
    setLoading(true);
    setError("");
    try {
      const [examResponse, questionsResponse] = await Promise.all([
        fetch(`${API_URL}/exams/${examId}`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams/${examId}/questions`, { headers, cache: "no-store" }),
      ]);
      if (examResponse.status === 401 || questionsResponse.status === 401) { router.replace("/login"); return; }
      const examData = await examResponse.json().catch(() => ({}));
      const questionData = await questionsResponse.json().catch(() => ({}));
      if (!examResponse.ok || !questionsResponse.ok) {
        throw new Error(examData.detail || questionData.detail || "Unable to open this examination.");
      }
      setExam(examData);
      setQuestions(Array.isArray(questionData.questions) ? questionData.questions : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open this examination.");
    } finally {
      setLoading(false);
    }
  }, [examId, router]);

  useEffect(() => { void loadDetails(); }, [loadDetails]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/staff/examinations" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Examination details</p></div>
          <Link href="/staff/examinations" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Examinations</Link>
        </div>
      </header>
      <div className="mx-auto max-w-6xl space-y-6 px-5 py-8">
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        {loading ? <p className="py-12 text-center text-slate-400">Loading examination...</p> : exam && (
          <>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <h1 className="text-3xl font-bold">{exam.title}</h1>
              <p className="mt-2 text-slate-400">{exam.subject || "No subject entered"}</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl bg-slate-800/70 p-4"><p className="text-xs text-slate-400">Created by</p><p className="mt-1 font-semibold">{exam.created_by_name || "Unknown"}</p><p className="text-xs capitalize text-slate-400">{exam.created_by_role || "—"}</p></div>
                <div className="rounded-xl bg-slate-800/70 p-4"><p className="text-xs text-slate-400">Maximum time</p><p className="mt-1 font-semibold">{exam.duration_minutes} minutes</p></div>
                <div className="rounded-xl bg-slate-800/70 p-4"><p className="text-xs text-slate-400">Questions</p><p className="mt-1 font-semibold">{exam.total_questions}</p></div>
                <div className="rounded-xl bg-slate-800/70 p-4"><p className="text-xs text-slate-400">Assigned questions</p><p className="mt-1 font-semibold">{questions.length}</p></div>
              </div>
              {exam.can_edit && <Link href={`/examiner/exams/${exam.id}/question-bank`} className="mt-5 inline-flex rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold hover:bg-cyan-500">Manage My Examination</Link>}
              {!exam.can_edit && <p className="mt-5 text-sm text-slate-400">You can view this examination, but only its creator can make changes.</p>}
            </section>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-bold">Examination Questions</h2><p className="text-sm text-slate-400">{questions.length} question(s), shown in examination order</p></div>
              {questions.length === 0 ? <p className="py-10 text-center text-slate-400">No questions have been added yet.</p> : (
                <div className="mt-5 space-y-4">{questions.map((question) => (
                  <article key={question.question_id} className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
                    <p className="text-xs text-cyan-300">Question {question.question_order} · {question.question_type} · {question.difficulty} · {question.marks} marks</p>
                    <p className="mt-3 whitespace-pre-wrap">{question.question_text}</p>
                    {question.options && question.options.length > 0 && <ul className="mt-3 space-y-2 text-sm text-slate-300">{question.options.map((option) => <li key={option.id} className="rounded-lg bg-slate-900/70 px-3 py-2">{option.option_text}{option.is_correct ? <span className="ml-2 text-green-300">(Correct answer)</span> : null}</li>)}</ul>}
                    {question.expected_answer && <p className="mt-3 text-sm text-slate-400">Expected answer: {question.expected_answer}</p>}
                    {question.model_answer_text && <p className="mt-2 text-sm text-slate-400">Model answer: {question.model_answer_text}</p>}
                    <p className="mt-3 text-xs text-slate-400">Question time: {question.question_time_limit_seconds ? `${question.question_time_limit_seconds} seconds` : "Not set"}</p>
                  </article>
                ))}</div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}

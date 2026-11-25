"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AdminSectionNavigation from "../../../admin/components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Question = {
  id: number; question_text: string; question_type: string; difficulty: string;
  marks: number; expected_answer?: string | null; model_answer_text?: string | null;
  question_image_available?: boolean;
  options: { id: number; option_text: string; is_correct: boolean }[];
};
type Bank = {
  id: number; name: string; subject?: string | null; description?: string | null;
  question_count: number; created_by_name: string; created_by_role: string;
};

export default function QuestionBankViewPage() {
  const { bankId } = useParams<{ bankId: string }>();
  const router = useRouter();
  const [bank, setBank] = useState<Bank | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dashboardHref, setDashboardHref] = useState("/admin/dashboard");

  const load = useCallback(async () => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    setLoading(true);
    try {
      const headers = { Authorization: "Bearer " + token };
      const [profileResponse, banksResponse, questionsResponse] = await Promise.all([
        fetch(API_URL + "/users/me", { headers, cache: "no-store" }),
        fetch(API_URL + "/question-banks/browse", { headers, cache: "no-store" }),
        fetch(API_URL + "/question-banks/" + bankId + "/questions", { headers, cache: "no-store" }),
      ]);
      if (profileResponse.ok) {
        const profile = await profileResponse.json().catch(() => ({}));
        setDashboardHref(profile.role === "examiner" ? "/examiner/dashboard" : "/admin/dashboard");
      }
      const banks = await banksResponse.json().catch(() => []);
      const questionsData = await questionsResponse.json().catch(() => ({}));
      if (!banksResponse.ok || !questionsResponse.ok) throw new Error(questionsData.detail || "Unable to open this question bank.");
      const found = (Array.isArray(banks) ? banks : []).find((item: Bank) => item.id === Number(bankId));
      if (!found) throw new Error("Question bank not found.");
      setBank(found);
      setQuestions(Array.isArray(questionsData) ? questionsData : []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open this question bank.");
    } finally { setLoading(false); }
  }, [bankId, router]);

  useEffect(() => { void load(); }, [load]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <div><Link href="/staff/question-banks" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="text-sm text-slate-400">View Question Bank</p></div>
          <AdminSectionNavigation previousHref="/staff/question-banks" previousLabel="All Question Banks" dashboardHref={dashboardHref} />
        </div>
      </header>
      <div className="mx-auto max-w-6xl space-y-6 px-6 py-10">
        {error && <p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}
        {loading ? <p className="py-12 text-center text-slate-400">Loading question bank...</p> : bank && (
          <>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <h1 className="text-3xl font-bold">{bank.name}</h1>
              <p className="mt-2 text-slate-400">{bank.subject || "No subject"}{bank.description ? " · " + bank.description : ""}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Questions</p><p className="mt-1 font-semibold">{questions.length}</p></div>
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Created by</p><p className="mt-1 font-semibold">{bank.created_by_name}</p></div>
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Owner role</p><p className="mt-1 font-semibold capitalize">{bank.created_by_role}</p></div>
              </div>
              <p className="mt-4 text-sm text-slate-400">This page is read-only. To use questions in your own examination, select them during examination creation.</p>
            </section>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <h2 className="text-xl font-semibold">Questions ({questions.length})</h2>
              {questions.length === 0 ? <p className="py-8 text-slate-400">This question bank has no questions.</p> : (
                <div className="mt-4 space-y-3">{questions.map((question, index) => (
                  <article key={question.id} className="rounded-xl border border-white/10 bg-slate-800/70 p-5">
                    <p className="text-xs text-cyan-300">Question {index + 1} · {question.question_type} · {question.difficulty} · {question.marks} marks</p>
                    <p className="mt-3 whitespace-pre-wrap">{question.question_text}</p>
                    {question.options?.map((option) => <p key={option.id} className="mt-2 text-sm text-slate-300">{option.option_text}</p>)}
                    {question.expected_answer && <p className="mt-3 text-sm text-slate-400">Expected answer: {question.expected_answer}</p>}
                    {question.model_answer_text && <p className="mt-2 text-sm text-slate-400">Model answer: {question.model_answer_text}</p>}
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

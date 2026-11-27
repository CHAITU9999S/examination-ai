"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AdminSectionNavigation from "../../../admin/components/AdminSectionNavigation";
import { formatISTDateTime } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Question = {
  id: number; question_text: string; question_type: string; difficulty: string;
  marks: number; negative_marks?: number; expected_answer?: string | null;
  model_answer_text?: string | null; question_image_available?: boolean;
  expected_answer_image_available?: boolean;
  options: { id: number; option_text: string; is_correct: boolean }[];
};
type Bank = {
  id: number; name: string; subject?: string | null; description?: string | null;
  question_count: number; maximum_marks: number; question_types: Record<string, number>;
  difficulty_counts: Record<string, number>; created_by_name: string;
  created_by_role: string; created_at?: string | null;
};
type Preview = { prompt?: string; expected?: string };

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  return formatISTDateTime(value);
}

export default function QuestionBankViewPage() {
  const { bankId } = useParams<{ bankId: string }>();
  const router = useRouter();
  const [bank, setBank] = useState<Bank | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionSearch, setQuestionSearch] = useState("");
  const [questionSort, setQuestionSort] = useState("bank-order");
  const [previews, setPreviews] = useState<Record<number, Preview>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dashboardHref, setDashboardHref] = useState("/admin/dashboard");

  const load = useCallback(async () => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    setLoading(true);
    setError("");
    try {
      const headers = { Authorization: "Bearer " + token };
      const [profileResponse, banksResponse, questionsResponse] = await Promise.all([
        fetch(API_URL + "/users/me", { headers, cache: "no-store" }),
        fetch(API_URL + "/question-banks/browse", { headers, cache: "no-store" }),
        fetch(API_URL + "/question-banks/" + bankId + "/questions", { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      const banks = await banksResponse.json().catch(() => []);
      const questionsData = await questionsResponse.json().catch(() => ({}));
      if (profileResponse.status === 401 || banksResponse.status === 401 || questionsResponse.status === 401) { router.replace("/login"); return; }
      if (!profileResponse.ok || !banksResponse.ok || !questionsResponse.ok) throw new Error(questionsData.detail || banks.detail || "Unable to open this question bank.");
      if (profile.role !== "admin" && profile.role !== "examiner") { router.replace("/login"); return; }
      setDashboardHref(profile.role === "examiner" ? "/examiner/dashboard" : "/admin/dashboard");
      const found = (Array.isArray(banks) ? banks : []).find((item: Bank) => item.id === Number(bankId));
      if (!found) throw new Error("Question bank not found.");
      const questionList: Question[] = Array.isArray(questionsData) ? questionsData : [];
      setBank(found);
      setQuestions(questionList);

      const nextPreviews: Record<number, Preview> = {};
      await Promise.all(questionList.map(async (question) => {
        const fetchPreview = async (url: string) => {
          const response = await fetch(url, { headers });
          return response.ok ? URL.createObjectURL(await response.blob()) : undefined;
        };
        const [prompt, expected] = await Promise.all([
          question.question_image_available ? fetchPreview(API_URL + "/questions/" + question.id + "/image") : Promise.resolve(undefined),
          question.expected_answer_image_available ? fetchPreview(API_URL + "/questions/" + question.id + "/expected-answer-image") : Promise.resolve(undefined),
        ]);
        nextPreviews[question.id] = { prompt, expected };
      }));
      setPreviews(nextPreviews);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open this question bank.");
    } finally { setLoading(false); }
  }, [bankId, router]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => () => {
    Object.values(previews).forEach((preview) => {
      if (preview.prompt) URL.revokeObjectURL(preview.prompt);
      if (preview.expected) URL.revokeObjectURL(preview.expected);
    });
  }, [previews]);

  const visibleQuestions = useMemo(() => {
    const term = questionSearch.trim().toLowerCase();
    const filtered = questions.filter((question) => !term || [
      question.question_text, question.question_type, question.difficulty,
      question.expected_answer, question.model_answer_text, String(question.id),
    ].some((value) => String(value || "").toLowerCase().includes(term)));
    if (questionSort === "bank-order") return filtered;
    return filtered.sort((a, b) => {
      if (questionSort === "name") return a.question_text.localeCompare(b.question_text);
      if (questionSort === "type") return a.question_type.localeCompare(b.question_type);
      if (questionSort === "difficulty") return a.difficulty.localeCompare(b.difficulty);
      if (questionSort === "marks-low") return a.marks - b.marks;
      if (questionSort === "marks-high") return b.marks - a.marks;
      return b.id - a.id;
    });
  }, [questions, questionSearch, questionSort]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div><Link href="/staff/question-banks" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="text-sm text-slate-400">View Question Bank · Read only</p></div>
          <AdminSectionNavigation previousHref="/staff/question-banks" previousLabel="All Question Banks" dashboardHref={dashboardHref} />
        </div>
      </header>
      <div className="mx-auto max-w-7xl space-y-6 px-6 py-10">
        {error && <p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}
        {loading ? <p className="py-12 text-center text-slate-400">Loading question bank...</p> : bank && (
          <>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <h1 className="text-3xl font-bold">{bank.name}</h1>
              <p className="mt-2 text-cyan-300">{bank.subject || "Subject not specified"}</p>
              {bank.description && <p className="mt-2 text-slate-400">{bank.description}</p>}
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Questions</p><p className="mt-1 font-semibold">{questions.length}</p></div>
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Maximum marks</p><p className="mt-1 font-semibold">{Number(bank.maximum_marks || 0).toLocaleString()}</p></div>
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Created by</p><p className="mt-1 font-semibold">{bank.created_by_name}</p><p className="text-xs capitalize text-slate-400">{bank.created_by_role}</p></div>
                <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Created date & time</p><p className="mt-1 text-sm font-semibold">{formatDate(bank.created_at)}</p></div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {["easy","medium","hard"].map(level => <span key={level} className="rounded-md bg-slate-800 px-3 py-2 text-xs capitalize">{level}: {bank.difficulty_counts?.[level] || 0}</span>)}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries({MCQ:"MCQ",multi_select:"Multi-select",short_answer:"Short answer",long_answer:"Long answer",image_upload:"Image upload"}).map(([key,label]) => <span key={key} className="rounded-md bg-slate-800 px-3 py-2 text-xs">{label}: {bank.question_types?.[key] || 0}</span>)}
              </div>
              <p className="mt-4 text-sm text-slate-400">This section is read-only. The question order and saved question content are shown as stored by the creator.</p>
            </section>
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">Questions ({visibleQuestions.length} of {questions.length})</h2>
                <div className="flex flex-wrap gap-3">
                  <input type="search" value={questionSearch} onChange={(event) => setQuestionSearch(event.target.value)} placeholder="Search questions in this bank" aria-label="Search bank questions" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
                  <select value={questionSort} onChange={(event) => setQuestionSort(event.target.value)} aria-label="Sort bank questions" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                    <option value="bank-order">Saved bank order</option><option value="newest">Newest first</option><option value="name">Question A to Z</option><option value="type">Question type</option><option value="difficulty">Difficulty</option><option value="marks-low">Lowest marks</option><option value="marks-high">Highest marks</option>
                  </select>
                </div>
              </div>
              {questions.length === 0 ? <p className="py-8 text-slate-400">This question bank has no questions.</p> : visibleQuestions.length === 0 ? <p className="py-8 text-slate-400">No questions match your search.</p> : (
                <div className="mt-4 space-y-4">{visibleQuestions.map((question, index) => (
                  <article key={question.id} className="rounded-xl border border-white/10 bg-slate-800/70 p-5">
                    <p className="text-xs text-cyan-300">Question {index + 1} · {question.question_type} · {question.difficulty} · {question.marks} marks</p>
                    {question.question_text && <p className="mt-3 whitespace-pre-wrap">{question.question_text}</p>}
                    {previews[question.id]?.prompt && <img src={previews[question.id].prompt} alt={"Question " + (index + 1) + " prompt"} className="mt-3 max-h-64 max-w-full rounded-lg bg-white object-contain" />}
                    {question.options?.map((option) => <p key={option.id} className="mt-2 text-sm text-slate-300">{option.option_text}{option.is_correct ? <span className="ml-2 text-emerald-300">(Correct answer)</span> : null}</p>)}
                    {question.expected_answer && <p className="mt-3 whitespace-pre-wrap text-sm text-slate-300">Expected answer: {question.expected_answer}</p>}
                    {question.model_answer_text && <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">Model answer: {question.model_answer_text}</p>}
                    {previews[question.id]?.expected && <div className="mt-3"><p className="text-xs text-emerald-300">Expected-answer image</p><img src={previews[question.id].expected} alt={"Question " + (index + 1) + " expected answer"} className="mt-2 max-h-64 max-w-full rounded-lg bg-white object-contain" /></div>}
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

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Bank = {
  id: number;
  name: string;
  subject?: string | null;
  question_count: number;
  question_types: Record<string, number>;
  created_by_name: string;
  created_by_role: string;
};
type Question = {
  id: number;
  question_text: string;
  question_type: string;
  difficulty: string;
  marks: number;
  options: { id: number; option_text: string; is_correct: boolean }[];
};
type Exam = { title: string; total_questions: number; can_edit: boolean };

export default function SelectBankForExamPage() {
  const { examId } = useParams<{ examId: string }>();
  const router = useRouter();
  const [banks, setBanks] = useState<Bank[]>([]);
  const [exam, setExam] = useState<Exam | null>(null);
  const [dashboardHref, setDashboardHref] = useState("/examiner/dashboard");
  const [dashboardHref, setDashboardHref] = useState("/examiner/dashboard");
  const [activeBankId, setActiveBankId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [loadingQuestions, setLoadingQuestions] = useState(false);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return null;
    }
    return { Authorization: "Bearer " + token, "Content-Type": "application/json" };
  }, [router]);

  useEffect(() => {
    const headers = getHeaders();
    if (!headers) return;
    Promise.all([
      fetch(API_URL + "/question-banks/browse", { headers, cache: "no-store" }),
      fetch(API_URL + "/exams/" + examId, { headers, cache: "no-store" }),
      fetch(API_URL + "/users/me", { headers, cache: "no-store" }),
    ]).then(async ([banksResponse, examResponse, profileResponse]) => {
      const bankData = await banksResponse.json().catch(() => []);
      const examData = await examResponse.json().catch(() => ({}));
      const profile = await profileResponse.json().catch(() => ({}));
      if (profileResponse.ok && profile.role === "admin") setDashboardHref("/admin/dashboard");
      const profile = await profileResponse.json().catch(() => ({}));
      if (profileResponse.ok && profile.role === "admin") setDashboardHref("/admin/dashboard");
      if (!banksResponse.ok || !examResponse.ok) {
        throw new Error(bankData.detail || examData.detail || "Unable to load question banks.");
      }
      if (!examData.can_edit) {
        throw new Error("Only the examination creator can select its questions.");
      }
      setBanks(Array.isArray(bankData) ? bankData : []);
      setExam(examData);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load question banks."));
  }, [examId, getHeaders]);

  const visibleBanks = useMemo(() => [...banks]
    .filter((bank) => [bank.name, bank.subject, bank.created_by_name, bank.created_by_role]
      .some((value) => String(value || "").toLowerCase().includes(search.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "questions-low") return a.question_count - b.question_count;
      if (sortBy === "questions-high") return b.question_count - a.question_count;
      return b.id - a.id;
    }), [banks, search, sortBy]);

  async function openBank(bankId: number) {
    setActiveBankId(bankId);
    setQuestions([]);
    setError("");
    const headers = getHeaders();
    if (!headers) return;
    setLoadingQuestions(true);
    try {
      const response = await fetch(API_URL + "/question-banks/" + bankId + "/questions", { headers, cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to open this question bank.");
      setQuestions(Array.isArray(data) ? data : []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open this question bank.");
    } finally {
      setLoadingQuestions(false);
    }
  }

  function toggleQuestion(id: number, checked: boolean) {
    setSelected((current) => checked
      ? (current.includes(id) ? current : [...current, id])
      : current.filter((item) => item !== id));
  }

  async function saveSelection() {
    if (!exam) return;
    // Partial and empty pools are allowed during setup; eligibility is checked before an exam starts.
    setError("");
    setWorking(true);
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(API_URL + "/question-banks/select-for-exam/" + examId, {
        method: "POST",
        headers,
        body: JSON.stringify({ question_ids: selected }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to copy the selected questions.");
      router.push("/examiner/exams/" + examId + "/question-bank");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to copy the selected questions.");
    } finally {
      setWorking(false);
    }
  }

  const activeBank = banks.find((bank) => bank.id === activeBankId);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div>
            <Link href="/staff/examinations" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="text-sm text-slate-400">Choose questions for your examination</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/staff/question-banks" className="rounded-lg border border-white/20 px-4 py-2 text-sm">Question Banks</Link>
            <Link href="/examiner/question-banks" className="rounded-lg border border-cyan-500/40 px-4 py-2 text-sm text-cyan-300">Manage Question Bank</Link>
            <Link href={dashboardHref} className="rounded-lg border border-white/20 px-4 py-2 text-sm">Dashboard</Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-6 px-6 py-10">
        <div>
          <h1 className="text-3xl font-bold">Select Questions</h1>
          <p className="mt-2 text-slate-400">{exam?.title || "Loading examination..."}. Open any question bank and select individual questions. You can select questions from more than one bank.</p>
          {exam && <p className="mt-2 text-sm text-cyan-300">Selected for the pool: {selected.length}. Each student receives {exam.total_questions} eligible questions.</p>}
        </div>
        {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>}

        <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">All Question Banks ({visibleBanks.length})</h2>
            <div className="flex flex-wrap gap-2">
              <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search banks or owner" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm">
                <option value="newest">Newest first</option>
                <option value="name">Name A to Z</option>
                <option value="questions-low">Fewest questions</option>
                <option value="questions-high">Most questions</option>
              </select>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {visibleBanks.map((bank) => (
              <button key={bank.id} type="button" onClick={() => openBank(bank.id)} className={"rounded-xl border p-4 text-left " + (activeBankId === bank.id ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 bg-slate-800/70 hover:bg-slate-800")}>
                <span className="block font-semibold">{bank.name}</span>
                <span className="mt-1 block text-sm text-slate-400">{bank.question_count} questions · {bank.subject || "No subject"}</span>
                <span className="mt-1 block text-xs text-slate-400">Owner: {bank.created_by_name} ({bank.created_by_role})</span>
                <span className="mt-2 block text-xs text-cyan-300">{Object.entries(bank.question_types || {}).map(([type, count]) => type + ": " + count).join(" · ") || "No questions yet"}</span>
              </button>
            ))}
            {visibleBanks.length === 0 && <p className="py-6 text-slate-400">No question banks match your search.</p>}
          </div>
        </section>

        {activeBank && (
          <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="text-xl font-semibold">{activeBank.name}</h2><p className="text-sm text-slate-400">Owner: {activeBank.created_by_name} · {questions.length} questions</p></div>
              <button type="button" onClick={() => setActiveBankId(null)} className="rounded-lg border border-white/20 px-3 py-2 text-sm">Close bank</button>
            </div>
            {loadingQuestions ? <p className="py-8 text-center text-slate-400">Loading questions...</p> : questions.length === 0 ? <p className="py-8 text-slate-400">This question bank has no questions yet.</p> : (
              <div className="mt-4 space-y-2">
                {questions.map((question) => (
                  <label key={question.id} className="flex items-start gap-3 rounded-lg bg-slate-800/70 p-4">
                    <input type="checkbox" checked={selected.includes(question.id)} onChange={(event) => toggleQuestion(question.id, event.target.checked)} className="mt-1" />
                    <span className="min-w-0 flex-1">
                      <span className="block whitespace-pre-wrap">{question.question_text}</span>
                      <span className="mt-1 block text-xs text-slate-400">{question.question_type} · {question.difficulty} · Source bank: {question.marks} marks (not copied)</span>
                      {question.options?.map((option) => <span key={option.id} className="mt-1 block text-sm text-slate-400">{option.option_text}</span>)}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </section>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="min-w-0 flex-1">
            <p className="text-sm text-slate-400">Select any number of questions from one or more banks, or select none and create questions directly in the examination. The pool may be larger than the paper. Each student paper uses the configured type/difficulty counts. Source-bank marks are not copied; set exam marks in Question Paper Marks Settings. Original banks remain unchanged.</p>
            {exam && selected.length < exam.total_questions && <p className="mt-2 text-xs text-amber-300">The pool currently has fewer than {exam.total_questions} questions. Add more eligible questions before students start.</p>}
          </div>
          <button type="button" disabled={working || !exam} onClick={saveSelection} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold disabled:opacity-50">{working ? "Copying questions..." : "Continue with selected questions"}</button>
        </div>
      </div>
    </main>
  );
}

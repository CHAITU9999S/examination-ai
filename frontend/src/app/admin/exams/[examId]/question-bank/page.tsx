"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Question {
  question_id: number;
  question_order: number;
  question_text: string;
  question_type: string;
  difficulty: string;
  marks: number;
  tags?: string[];
  question_time_limit_seconds?: number | null;
}
interface BankData {
  exam_id: number;
  total_assigned: number;
  questions: Question[];
}
interface MarksRevision {
  revision_number: number;
  marks_snapshot: Record<string, number>;
  changed_by: number;
  created_at: string;
}

export default function AdminQuestionBankViewPage() {
  const params = useParams<{ examId: string }>();
  const router = useRouter();
  const examId = String(params.examId || "");
  const [bank, setBank] = useState<BankData | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  const [marksRevisions, setMarksRevisions] = useState<MarksRevision[]>([]);
  const [marksRevisionsUsed, setMarksRevisionsUsed] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const [profileResponse, bankResponse, marksResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams/${examId}/questions`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams/${examId}/question-marks`, { headers, cache: "no-store" }),
      ]);
      if ([profileResponse, bankResponse, marksResponse].some((response) => response.status === 401)) {
        router.replace("/login");
        return;
      }
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await bankResponse.json().catch(() => ({}));
      const marksData = await marksResponse.json().catch(() => ({}));
      if (!profileResponse.ok || !bankResponse.ok || !marksResponse.ok) {
        throw new Error(data.detail || "Unable to load examination question bank.");
      }
      setIsOwner(Number(profile.id) === Number(data.created_by));
      setBank(data);
      setMarksRevisions(Array.isArray(marksData.revisions) ? marksData.revisions : []);
      setMarksRevisionsUsed(Number(marksData.revisions_used || 0));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load question bank.");
    } finally {
      setLoading(false);
    }
  }, [examId, router]);

  useEffect(() => { void load(); }, [load]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link href="/admin/exams" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Administrator / Read-only question bank</p>
          </div>
          <Link href="/admin/exams" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← All Examinations</Link>
        </div>
      </header>
      <div className="mx-auto max-w-6xl space-y-6 px-5 py-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold">Examination Question Bank</h1>
            <p className="mt-2 text-sm text-slate-400">Admin inspection view. Other creators' question banks are read-only.</p>
          </div>
          {isOwner && (
            <Link href={`/examiner/exams/${examId}/question-bank`} className="rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold hover:bg-cyan-500">
              Manage My Question Bank
            </Link>
          )}
        </div>
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        {loading ? <p className="py-10 text-center text-slate-400">Loading question bank...</p> : (
          <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
            <h2 className="text-lg font-semibold">{bank?.total_assigned ?? 0} assigned question(s)</h2>
            {!bank?.questions?.length ? <p className="py-8 text-slate-400">No questions are assigned to this examination.</p> : (
              <div className="mt-4 space-y-3">
                {bank.questions.map((question) => (
                  <article key={question.question_id} className="rounded-xl border border-white/10 bg-slate-800/60 p-4">
                    <p className="text-xs text-cyan-300">Question {question.question_order} · {question.question_type} · {question.difficulty} · {question.marks} marks</p>
                    <p className="mt-2 whitespace-pre-wrap">{question.question_text}</p>
                    {question.tags && question.tags.length > 0 && <p className="mt-2 text-xs text-slate-400">Tags: {question.tags.join(", ")}</p>}
                    <p className="mt-2 text-xs text-slate-400">Question timer: {question.question_time_limit_seconds ? `${question.question_time_limit_seconds} seconds` : "Not configured"}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
        <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Question Paper Marks History</h2>
            <span className="text-xs text-slate-400">{marksRevisionsUsed}/3 revisions used</span>
          </div>
          {marksRevisions.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">No question paper marks revisions have been made.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {marksRevisions.map((revision) => (
                <div key={revision.revision_number} className="rounded-lg bg-slate-800/60 p-3 text-xs text-slate-300">
                  <p className="font-semibold">Revision {revision.revision_number}</p>
                  <p className="mt-1 text-slate-500">{new Date(revision.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST · Staff account #{revision.changed_by}</p>
                  <p className="mt-2 text-slate-400">{Object.entries(revision.marks_snapshot).map(([key, value]) => `${key.replace("|", " · ")}: ${value} marks`).join(" | ")}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

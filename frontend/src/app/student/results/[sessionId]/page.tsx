"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QuestionResult {
  question_id: number;
  question_text?: string | null;
  question_type?: string;
  maximum_marks: number;
  awarded_marks: number;
  outcome: "correct" | "incorrect" | "partial" | "unanswered";
  examiner_feedback?: string | null;
  image_annotations?: Array<{
    annotation_type: string;
    x: number;
    y: number;
    width: number;
    height: number;
    text: string;
  }> | null;
}

interface ResultDetails {
  exam_title: string;
  total_marks: number;
  obtained_marks: number;
  percentage: number;
  percentile: number;
  published_at?: string | null;
  question_results: QuestionResult[];
}

export default function StudentResultDetailPage() {
  const router = useRouter();
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;

  const [result, setResult] = useState<ResultDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadResult = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/results/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to load result details.");
      }
      setResult(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load result.");
    } finally {
      setLoading(false);
    }
  }, [router, sessionId]);

  useEffect(() => {
    if (sessionId) loadResult();
  }, [loadResult, sessionId]);

  const percentage = Math.max(0, Math.min(100, Number(result?.percentage || 0)));

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/student/results" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Published Result Details</p>
          </div>
          <Link href="/student/results" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← My Results
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-10">
        {loading ? (
          <p className="py-16 text-center text-slate-400">Loading result...</p>
        ) : error ? (
          <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-red-300">
            {error}
          </div>
        ) : result ? (
          <>
            <h1 className="text-3xl font-bold">{result.exam_title}</h1>
            <section className="mt-8 grid gap-5 sm:grid-cols-3">
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Overall score</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">
                  {result.obtained_marks} / {result.total_marks}
                </p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Percentage</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">{percentage.toFixed(2)}%</p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-700">
                  <div className="h-full rounded-full bg-blue-500" style={{ width: `${percentage}%` }} />
                </div>
              </article>
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Cohort percentile</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">{Number(result.percentile).toFixed(1)}</p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-700" aria-label="Cohort percentile">
                  <div
                    className="h-full rounded-full bg-purple-500"
                    style={{ width: `${Math.max(0, Math.min(100, Number(result.percentile || 0)))}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-slate-500">Compared with published results for this exam.</p>
              </article>
            </section>

            <section className="mt-10 space-y-4">
              <h2 className="text-xl font-bold">Question-wise evaluation</h2>
              {result.question_results.map((item) => (
                <article key={item.question_id} className="rounded-xl border border-white/10 bg-slate-900 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Question {item.question_id} · {item.question_type}</p>
                      <p className="mt-2 whitespace-pre-wrap font-medium">{item.question_text || "Question text unavailable"}</p>
                    </div>
                    <span className="rounded-full bg-slate-800 px-3 py-1 text-xs capitalize text-slate-300">
                      {item.outcome}
                    </span>
                  </div>
                  <p className="mt-4 text-sm text-slate-300">
                    Marks: {item.awarded_marks} / {item.maximum_marks}
                  </p>
                  {item.examiner_feedback && (
                    <div className="mt-4 rounded-lg border border-blue-400/20 bg-blue-500/5 p-4">
                      <p className="text-sm font-semibold text-blue-300">Examiner feedback</p>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{item.examiner_feedback}</p>
                    </div>
                  )}
                  {item.image_annotations && item.image_annotations.length > 0 && (
                    <div className="mt-4">
                      <p className="text-sm font-semibold text-slate-300">Examiner image annotations</p>
                      <ul className="mt-2 space-y-2">
                        {item.image_annotations.map((annotation, index) => (
                          <li key={index} className="rounded-lg bg-slate-800 p-3 text-sm text-slate-300">
                            <span className="font-semibold capitalize">{annotation.annotation_type}</span>
                            {" · "}position {annotation.x.toFixed(1)}%, {annotation.y.toFixed(1)}%
                            <p className="mt-1">{annotation.text}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              ))}
            </section>
          </>
        ) : null}
      </div>
    </main>
  );
}

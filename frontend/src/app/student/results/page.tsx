"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PublishedResult {
  result_id: number;
  session_id: number;
  exam_id: number;
  exam_title: string;
  subject?: string | null;
  submitted_at?: string | null;
  published_at?: string | null;
  total_marks: number;
  obtained_marks: number;
  percentage: number;
  percentile: number;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

export default function StudentResultsPage() {
  const router = useRouter();
  const [results, setResults] = useState<PublishedResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadResults = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/results/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error("Unable to load published results.");
      }

      const data = await response.json();
      setResults(Array.isArray(data.results) ? data.results : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load results.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/student/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Student / My Results</p>
          </div>
          <Link
            href="/student/dashboard"
            className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">My Examination Results</h1>
            <p className="mt-2 text-slate-400">
              Only results published by an examiner are displayed here.
            </p>
          </div>
          <button
            type="button"
            onClick={loadResults}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && (
          <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">
            {error}
          </div>
        )}

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          {loading ? (
            <p className="py-12 text-center text-slate-400">Loading results...</p>
          ) : results.length === 0 ? (
            <p className="py-12 text-center text-slate-400">
              No results have been published for your account yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Examination</th>
                    <th className="px-4 py-3">Score</th>
                    <th className="px-4 py-3">Percentage</th>
                    <th className="px-4 py-3">Cohort percentile</th>
                    <th className="px-4 py-3">Published</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result) => (
                    <tr key={result.result_id} className="border-b border-white/5 last:border-0">
                      <td className="px-4 py-4">
                        <p className="font-semibold">{result.exam_title}</p>
                        <p className="mt-1 text-xs text-slate-400">{result.subject || "—"}</p>
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {result.obtained_marks} / {result.total_marks}
                      </td>
                      <td className="px-4 py-4 tabular-nums">{Number(result.percentage).toFixed(2)}%</td>
                      <td className="px-4 py-4 tabular-nums">{Number(result.percentile).toFixed(1)}</td>
                      <td className="px-4 py-4 text-slate-400">{formatDate(result.published_at)}</td>
                      <td className="px-4 py-4">
                        <Link
                          href={`/student/results/${result.session_id}`}
                          className="font-semibold text-blue-400 hover:text-blue-300"
                        >
                          View result →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

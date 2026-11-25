"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QuestionOption {
  id: number;
  option_text: string;
  is_correct: boolean;
}

interface Question {
  id: number;
  question_text: string;
  question_type: string;
  subject?: string | null;
  difficulty?: string | null;
  marks?: number | null;
  negative_marks?: number | null;
  created_by?: number | null;
  created_by_name?: string | null;
  question_image_available?: boolean;
  options?: QuestionOption[];
}

export default function AdminQuestionsPage() {
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return null;
    }
    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, [router]);

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const headers = getHeaders();
      if (!headers) return;

      const profileResponse = await fetch(`${API_URL}/users/me`, { headers, cache: "no-store" });
      if (profileResponse.status === 401 || profileResponse.status === 403) {
        router.replace("/login");
        return;
      }
      if (!profileResponse.ok) throw new Error("Unable to verify your account.");
      const profile = await profileResponse.json();
      if (profile.role !== "admin") {
        router.replace("/login");
        return;
      }

      const response = await fetch(`${API_URL}/questions/`, { headers, cache: "no-store" });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) throw new Error("Unable to load the question inventory.");
      const data = await response.json();
      const list = Array.isArray(data) ? data : data.questions;
      if (!Array.isArray(list)) throw new Error("Unexpected question data returned by the server.");
      setQuestions(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load questions.");
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  const visibleQuestions = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return questions;
    return questions.filter((question) =>
      [
        question.question_text,
        question.subject,
        question.question_type,
        question.difficulty,
        question.created_by_name,
        question.id,
      ].some((value) => String(value ?? "").toLowerCase().includes(term))
    );
  }, [questions, search]);

  async function deleteQuestion(question: Question) {
    const confirmed = window.confirm(
      `Delete question #${question.id}? Questions used by an examination, student answer, reusable question, or question collection cannot be removed until those dependencies are safely resolved. This action cannot be undone.`
    );
    if (!confirmed || deletingId !== null) return;

    const headers = getHeaders();
    if (!headers) return;
    setDeletingId(question.id);
    setMessage("");
    setError("");
    try {
      const response = await fetch(`${API_URL}/questions/${question.id}`, {
        method: "DELETE",
        headers,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to delete this question.");
      setQuestions((current) => current.filter((item) => item.id !== question.id));
      setMessage(data.message || `Question #${question.id} deleted.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete this question.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/admin/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Administrator / All Questions</p>
          </div>
          <Link href="/admin/dashboard" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">All Questions</h1>
            <p className="mt-2 text-slate-400">
              View every question currently stored in the platform, regardless of its creator.
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {visibleQuestions.length} of {questions.length} question(s)
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search question, subject, creator, or ID"
              aria-label="Search all questions"
              className="min-w-[260px] rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
            />
            <button
              type="button"
              onClick={loadQuestions}
              disabled={loading}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}
        {message && <div role="status" className="mt-6 rounded-xl border border-white/10 bg-slate-900 px-5 py-4 text-sm text-slate-200">{message}</div>}

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          {loading ? (
            <p className="py-12 text-center text-slate-400">Loading questions...</p>
          ) : visibleQuestions.length === 0 ? (
            <p className="py-12 text-center text-slate-400">
              {questions.length === 0 ? "No questions are currently stored." : "No questions match your search."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1050px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Question</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Difficulty</th>
                    <th className="px-4 py-3">Marks</th>
                    <th className="px-4 py-3">Created By</th>
                    <th className="px-4 py-3">Image</th>
                    <th className="px-4 py-3">Admin Action</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleQuestions.map((question) => (
                    <tr key={question.id} className="border-b border-white/5 last:border-0 align-top">
                      <td className="px-4 py-4">
                        <p className="max-w-xl font-medium text-white">{question.question_text}</p>
                        <p className="mt-1 text-xs text-slate-500">Question ID: {question.id}</p>
                      </td>
                      <td className="px-4 py-4 text-slate-300">{question.subject || "—"}</td>
                      <td className="px-4 py-4 text-slate-300">{question.question_type}</td>
                      <td className="px-4 py-4 capitalize text-slate-300">{question.difficulty || "—"}</td>
                      <td className="px-4 py-4 text-slate-300">
                        {question.marks ?? "—"}
                        {question.negative_marks ? <span className="block text-xs text-slate-500">Negative: {question.negative_marks}</span> : null}
                      </td>
                      <td className="px-4 py-4 text-slate-300">{question.created_by_name || (question.created_by ? `User #${question.created_by}` : "Unknown")}</td>
                      <td className="px-4 py-4 text-slate-300">{question.question_image_available ? "Available" : "—"}</td>
                      <td className="px-4 py-4">
                        <button
                          type="button"
                          onClick={() => deleteQuestion(question)}
                          disabled={deletingId !== null}
                          className="rounded-lg border border-red-500/40 px-3 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {deletingId === question.id ? "Deleting..." : "Delete"}
                        </button>
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

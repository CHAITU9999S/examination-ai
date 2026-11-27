"use client";
import { formatISTDateTime } from "@/lib/utils";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AdminSectionNavigation from "../../admin/components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Bank = {
  id: number;
  name: string;
  subject?: string | null;
  description?: string | null;
  question_count: number;
  question_types: Record<string, number>;
  difficulty_counts: Record<string, number>;
  question_type_difficulty_counts: Record<string, Record<string, number>>;
  maximum_marks: number;
  created_by_name: string;
  created_by_role: string;
  created_at?: string | null;
};

const typeLabels: Record<string, string> = {
  MCQ: "MCQ",
  multi_select: "Multi-select",
  short_answer: "Short answer",
  long_answer: "Long answer",
  image_upload: "Image upload",
};

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  return formatISTDateTime(value);
}

export default function QuestionBanksPage() {
  const router = useRouter();
  const [banks, setBanks] = useState<Bank[]>([]);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dashboardHref, setDashboardHref] = useState("/examiner/dashboard");

  const loadBanks = useCallback(async () => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    setLoading(true);
    setError("");
    try {
      const headers = { Authorization: "Bearer " + token };
      const [profileResponse, response] = await Promise.all([
        fetch(API_URL + "/users/me", { headers, cache: "no-store" }),
        fetch(API_URL + "/question-banks/browse", { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await response.json().catch(() => ({}));
      if (profileResponse.status === 401 || profileResponse.status === 403 || response.status === 401 || response.status === 403) {
        router.replace("/login"); return;
      }
      if (!profileResponse.ok || !response.ok) throw new Error(data.detail || "Unable to load question banks.");
      if (profile.role !== "admin" && profile.role !== "examiner") { router.replace("/login"); return; }
      setDashboardHref(profile.role === "admin" ? "/admin/dashboard" : "/examiner/dashboard");
      setBanks(Array.isArray(data) ? data : []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load question banks.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { void loadBanks(); }, [loadBanks]);

  const visibleBanks = useMemo(() => [...banks]
    .filter((bank) => [
      bank.name, bank.subject, bank.created_by_name, bank.created_by_role,
    ].some((value) => String(value || "").toLowerCase().includes(search.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "questions-low") return a.question_count - b.question_count;
      if (sortBy === "questions-high") return b.question_count - a.question_count;
      if (sortBy === "marks-high") return b.maximum_marks - a.maximum_marks;
      if (sortBy === "oldest") return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime() || b.id - a.id;
    }), [banks, search, sortBy]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div>
            <Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="text-sm text-slate-400">All Question Banks</p>
          </div>
          <AdminSectionNavigation previousHref="/admin/sections/question-banks" previousLabel="Question Bank" dashboardHref={dashboardHref} />
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-6 px-6 py-10">
        <div>
          <h1 className="text-3xl font-bold">All Question Banks</h1>
          <p className="mt-2 text-slate-400">Read-only view of question banks created by every Admin and Examiner, including your own banks.</p>
        </div>
        {error && <p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}
        <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleBanks.length} of {banks.length} question bank(s)</p>
            <div className="flex flex-wrap gap-2">
              <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search bank, subject, or creator" aria-label="Search all question banks" className="min-w-[240px] rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort question banks" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm">
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="name">Name A to Z</option>
                <option value="questions-low">Fewest questions</option>
                <option value="questions-high">Most questions</option>
                <option value="marks-high">Maximum marks: high to low</option>
              </select>
              <button type="button" onClick={loadBanks} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm disabled:opacity-50">{loading ? "Refreshing..." : "Refresh"}</button>
            </div>
          </div>

          {loading ? <p className="py-12 text-center text-slate-400">Loading question banks...</p> :
            visibleBanks.length === 0 ? <p className="py-12 text-center text-slate-400">No question banks match your search.</p> : (
              <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {visibleBanks.map((bank) => (
                  <article key={bank.id} className="flex h-full flex-col rounded-xl border border-white/10 bg-slate-800/70 p-5">
                    <div className="flex-1">
                      <h2 className="text-lg font-semibold">{bank.name}</h2>
                      <p className="mt-1 text-sm text-cyan-300">{bank.subject || "Subject not specified"}</p>
                      {bank.description && <p className="mt-2 text-sm text-slate-400">{bank.description}</p>}
                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <div className="rounded-lg bg-slate-900 p-3"><p className="text-xs text-slate-400">Questions</p><p className="mt-1 font-semibold">{bank.question_count}</p></div>
                        <div className="rounded-lg bg-slate-900 p-3"><p className="text-xs text-slate-400">Maximum marks</p><p className="mt-1 font-semibold">{Number(bank.maximum_marks || 0).toLocaleString()}</p></div>
                      </div>
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Questions by type and difficulty</p>
                        <div className="mt-2 overflow-x-auto rounded-lg border border-white/10">
                          <table className="w-full min-w-[390px] text-left text-xs">
                            <thead className="bg-slate-900 text-slate-400"><tr><th className="p-2">Question type</th><th className="p-2 text-right">Easy</th><th className="p-2 text-right">Medium</th><th className="p-2 text-right">Hard</th><th className="p-2 text-right">Total</th></tr></thead>
                            <tbody>
                              {Object.entries(typeLabels).map(([type, label]) => {
                                const counts = bank.question_type_difficulty_counts?.[type] || {};
                                const easy = counts.easy || 0, medium = counts.medium || 0, hard = counts.hard || 0;
                                return <tr key={type} className="border-t border-white/5 text-slate-300"><th className="p-2 font-medium">{label}</th><td className="p-2 text-right tabular-nums">{easy}</td><td className="p-2 text-right tabular-nums">{medium}</td><td className="p-2 text-right tabular-nums">{hard}</td><td className="p-2 text-right font-semibold tabular-nums">{bank.question_types?.[type] ?? easy + medium + hard}</td></tr>;
                              })}
                              <tr className="border-t border-white/10 bg-slate-900 font-semibold text-white"><th className="p-2">Total</th><td className="p-2 text-right tabular-nums">{bank.difficulty_counts?.easy || 0}</td><td className="p-2 text-right tabular-nums">{bank.difficulty_counts?.medium || 0}</td><td className="p-2 text-right tabular-nums">{bank.difficulty_counts?.hard || 0}</td><td className="p-2 text-right tabular-nums">{bank.question_count}</td></tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div className="mt-4 border-t border-white/10 pt-3 text-sm">
                        <p className="text-slate-300">Created by: <span className="font-medium text-white">{bank.created_by_name}</span> <span className="capitalize text-slate-400">({bank.created_by_role})</span></p>
                        <p className="mt-1 text-xs text-slate-400">Created: {formatDate(bank.created_at)}</p>
                      </div>
                    </div>
                    <Link href={"/staff/question-banks/" + bank.id} className="mt-5 inline-flex justify-center rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-500">View Question Bank</Link>
                  </article>
                ))}
              </div>
            )}
        </section>
      </div>
    </main>
  );
}

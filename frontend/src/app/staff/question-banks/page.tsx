"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AdminSectionNavigation from "../../admin/components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Bank = {
  id: number; name: string; subject?: string | null; description?: string | null;
  question_count: number; question_types: Record<string, number>;
  created_by_name: string; created_by_role: string;
};

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
      const data = await response.json().catch(() => []);
      if (profileResponse.status === 401 || profileResponse.status === 403 || response.status === 401 || response.status === 403) { router.replace("/login"); return; }
      if (!profileResponse.ok || !response.ok) throw new Error(data.detail || "Unable to load question banks.");
      if (profile.role !== "admin" && profile.role !== "examiner") { router.replace("/login"); return; }
      setDashboardHref(profile.role === "admin" ? "/admin/dashboard" : "/examiner/dashboard");
      setBanks(Array.isArray(data) ? data : []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load question banks.");
    } finally { setLoading(false); }
  }, [router]);

  useEffect(() => { void loadBanks(); }, [loadBanks]);

  const visibleBanks = useMemo(() => [...banks]
    .filter((bank) => [bank.name, bank.subject, bank.created_by_name, bank.created_by_role]
      .some((value) => String(value || "").toLowerCase().includes(search.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "questions-low") return a.question_count - b.question_count;
      if (sortBy === "questions-high") return b.question_count - a.question_count;
      return b.id - a.id;
    }), [banks, search, sortBy]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div><Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="text-sm text-slate-400">Question Banks</p></div>
          <AdminSectionNavigation previousHref="/admin/sections/question-banks" previousLabel="Question Bank" dashboardHref={dashboardHref} />
        </div>
      </header>
      <div className="mx-auto max-w-7xl space-y-6 px-6 py-10">
        <div><h1 className="text-3xl font-bold">Question Banks</h1><p className="mt-2 text-slate-400">Browse question banks created by all Admins and Examiners. This page is for viewing only.</p></div>
        {error && <p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}
        <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleBanks.length} question bank(s)</p>
            <div className="flex flex-wrap gap-2">
              <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by bank or owner" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm">
                <option value="newest">Newest first</option><option value="name">Name A to Z</option><option value="questions-low">Fewest questions</option><option value="questions-high">Most questions</option>
              </select>
              <button type="button" onClick={loadBanks} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm disabled:opacity-50">Refresh</button>
            </div>
          </div>
          {loading ? <p className="py-12 text-center text-slate-400">Loading question banks...</p> : visibleBanks.length === 0 ? <p className="py-12 text-center text-slate-400">No question banks match your search.</p> : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400"><th className="px-4 py-3">Bank Name</th><th className="px-4 py-3">Questions</th><th className="px-4 py-3">Question Types</th><th className="px-4 py-3">Owner</th><th className="px-4 py-3">Action</th></tr></thead>
                <tbody>{visibleBanks.map((bank) => (
                  <tr key={bank.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-4"><p className="font-semibold">{bank.name}</p><p className="text-xs text-slate-400">{bank.subject || "No subject"}</p></td>
                    <td className="px-4 py-4">{bank.question_count}</td>
                    <td className="px-4 py-4 text-slate-300">{Object.entries(bank.question_types || {}).map(([type, count]) => type + " (" + count + ")").join(", ") || "—"}</td>
                    <td className="px-4 py-4"><p>{bank.created_by_name}</p><p className="text-xs capitalize text-slate-400">{bank.created_by_role}</p></td>
                    <td className="px-4 py-4"><Link href={"/staff/question-banks/" + bank.id} className="rounded-lg bg-cyan-600/20 px-3 py-2 text-xs font-semibold text-cyan-300">View Questions</Link></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

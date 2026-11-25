"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PerformanceRow {
  result_id: number;
  student_id: number;
  student_name: string;
  exam_id: number;
  exam_title: string;
  obtained_marks: number;
  total_marks: number;
  percentage: number;
  grade: string;
  published_at?: string | null;
}

export default function AdminPerformancePage() {
  const router = useRouter();
  const [rows, setRows] = useState<PerformanceRow[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("published-desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    fetch(`${API_URL}/admin/performance`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to load historical performance.");
      setRows(Array.isArray(data.performance) ? data.performance : []);
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load performance."))
      .finally(() => setLoading(false));
  }, [router]);

  const visibleRows = [...rows]
    .filter((row) => !searchTerm.trim() || [row.student_name, row.exam_title, row.grade].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "student") return a.student_name.localeCompare(b.student_name);
      if (sortBy === "exam") return a.exam_title.localeCompare(b.exam_title);
      if (sortBy === "percentage-high") return b.percentage - a.percentage;
      if (sortBy === "percentage-low") return a.percentage - b.percentage;
      return String(b.published_at || "").localeCompare(String(a.published_at || ""));
    });

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Historical performance</p></div>
          <AdminSectionNavigation previousHref="/admin/sections/students" previousLabel="Students" />
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-5 py-8">
        <h1 className="text-3xl font-bold">Student Performance History</h1>
        <p className="mt-2 text-sm text-slate-400">Published examination results across the platform.</p>
        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-400">{visibleRows.length} published result(s)</p><div className="flex flex-wrap gap-3"><input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search student, exam, or grade" aria-label="Search performance" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"/><select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort performance" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"><option value="published-desc">Latest published</option><option value="student">Student</option><option value="exam">Examination</option><option value="percentage-high">Highest percentage</option><option value="percentage-low">Lowest percentage</option></select></div></div>
          {loading ? <p className="py-10 text-center text-slate-400">Loading performance...</p> : visibleRows.length === 0 ? <p className="py-10 text-center text-slate-400">No published results yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Student</th><th className="p-3">Examination</th><th className="p-3">Marks</th><th className="p-3">Percentage</th><th className="p-3">Grade</th><th className="p-3">Published</th></tr></thead>
                <tbody>{visibleRows.map((row) => <tr key={row.result_id} className="border-b border-white/5"><td className="p-3">{row.student_name}<span className="block text-xs text-slate-500">ID {row.student_id}</span></td><td className="p-3">{row.exam_title}</td><td className="p-3 tabular-nums">{row.obtained_marks} / {row.total_marks}</td><td className="p-3 tabular-nums">{Number(row.percentage).toFixed(2)}%</td><td className="p-3 font-semibold text-cyan-300">{row.grade || "—"}</td><td className="p-3 text-slate-400">{row.published_at ? new Date(row.published_at).toLocaleString("en-IN") : "—"}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

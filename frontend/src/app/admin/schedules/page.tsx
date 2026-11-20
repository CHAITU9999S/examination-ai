"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Schedule {
  exam_id: number;
  exam_title: string;
  creator_name?: string | null;
  student_id: number;
  student_name: string;
  student_email: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  assigned_at: string;
}

export default function AdminSchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    fetch(`${API_URL}/admin/schedules`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 || response.status === 403) { router.replace("/login"); return; }
      if (!response.ok) throw new Error(data.detail || "Unable to load examination schedules.");
      setSchedules(Array.isArray(data.schedules) ? data.schedules : []);
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load schedules."))
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student schedules</p></div>
          <Link href="/admin/dashboard" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Dashboard</Link>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-5 py-8">
        <h1 className="text-3xl font-bold">Examination Schedules</h1>
        <p className="mt-2 text-sm text-slate-400">Active student assignments across Admin-created and Examiner-created examinations.</p>
        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <p className="mb-4 text-sm text-slate-400">{schedules.length} active assignment(s)</p>
          {loading ? <p className="py-10 text-center text-slate-400">Loading schedules...</p> : schedules.length === 0 ? <p className="py-10 text-center text-slate-400">No active student assignments yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Examination</th><th className="p-3">Creator</th><th className="p-3">Student</th><th className="p-3">Opens (IST)</th><th className="p-3">Closes (IST)</th><th className="p-3">Duration</th></tr></thead>
                <tbody>{schedules.map((item) => <tr key={`${item.exam_id}-${item.student_id}`} className="border-b border-white/5"><td className="p-3 font-medium">{item.exam_title}</td><td className="p-3">{item.creator_name || "—"}</td><td className="p-3">{item.student_name}<span className="block text-xs text-slate-500">{item.student_email}</span></td><td className="p-3 text-slate-300">{new Date(item.start_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</td><td className="p-3 text-slate-300">{new Date(item.end_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</td><td className="p-3">{item.duration_minutes} min</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

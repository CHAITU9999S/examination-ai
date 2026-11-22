"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Exam {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  max_marks?: number | null;
  created_by?: number | null;
}

export default function ManageExamsPage() {
  const router = useRouter();
  const [exams, setExams] = useState<Exam[]>([]);
  const [userName, setUserName] = useState("");
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("newest");

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return null;
    }
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  }, [router]);

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const [profileResponse, examsResponse] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exams`, { headers, cache: "no-store" }),
      ]);
      if (profileResponse.status === 401 || examsResponse.status === 401) {
        router.replace("/login");
        return;
      }
      const profile = await profileResponse.json().catch(() => ({}));
      const data = await examsResponse.json().catch(() => []);
      if (!profileResponse.ok || !examsResponse.ok) {
        throw new Error(data.detail || "Unable to load your examinations.");
      }
      if (profile.role !== "admin" && profile.role !== "examiner") {
        router.replace("/login");
        return;
      }
      setUserName(profile.full_name || "");
      const allExams = Array.isArray(data) ? data : Array.isArray(data.exams) ? data.exams : [];
      setExams(allExams.filter((exam: Exam) => Number(exam.created_by) === Number(profile.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load your examinations.");
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    void loadExams();
  }, [loadExams]);

  const visibleExams = useMemo(() => {
    return [...exams]
      .filter((exam) => {
        const search = searchTerm.trim().toLowerCase();
        return !search || [exam.title, exam.subject].some((value) => String(value || "").toLowerCase().includes(search));
      })
      .sort((first, second) => {
        if (sortBy === "title-asc") return first.title.localeCompare(second.title);
        if (sortBy === "title-desc") return second.title.localeCompare(first.title);
        if (sortBy === "duration-short") return first.duration_minutes - second.duration_minutes;
        if (sortBy === "duration-long") return second.duration_minutes - first.duration_minutes;
        if (sortBy === "oldest") return first.id - second.id;
        return second.id - first.id;
      });
  }, [exams, searchTerm, sortBy]);

  async function deleteExam(exam: Exam) {
    const confirmed = window.confirm(
      `Delete "${exam.title}" and its related examination records? This cannot be undone.`
    );
    if (!confirmed) return;
    setWorkingId(exam.id);
    setError("");
    setMessage("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(`${API_URL}/exams/${exam.id}`, { method: "DELETE", headers });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to delete this examination.");
      setMessage(`"${exam.title}" and its related records were deleted.`);
      await loadExams();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete this examination.");
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Manage Examination</p>
          </div>
          <Link href="/staff/examinations" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">View Examinations</Link>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="text-3xl font-bold">Manage My Examinations</h1>
        <p className="mt-2 text-slate-400">Only examinations created by your account are shown here{userName ? `, ${userName}` : ""}.</p>
        {message && <div role="status" className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-300">{message}</div>}
        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}
        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-slate-400">{visibleExams.length} examination(s)</p>
            <div className="flex flex-wrap gap-3">
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search my examinations" aria-label="Search my examinations" className="min-w-[220px] rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort my examinations" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white">
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="title-asc">Name A to Z</option>
                <option value="title-desc">Name Z to A</option>
                <option value="duration-short">Shortest time</option>
                <option value="duration-long">Longest time</option>
              </select>
              <button type="button" onClick={loadExams} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">Refresh</button>
            </div>
          </div>
          {loading ? <p className="py-12 text-center text-slate-400">Loading your examinations...</p> : visibleExams.length === 0 ? (
            <p className="py-12 text-center text-slate-400">{exams.length ? "No examinations match your search." : "You have not created any examinations yet."}</p>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400">
                  <th className="px-4 py-3">Examination</th><th className="px-4 py-3">Subject</th><th className="px-4 py-3">Maximum Time</th><th className="px-4 py-3">Questions</th><th className="px-4 py-3">Maximum Marks</th><th className="px-4 py-3">Actions</th>
                </tr></thead>
                <tbody>{visibleExams.map((exam) => (
                  <tr key={exam.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-4 font-semibold">{exam.title}</td>
                    <td className="px-4 py-4 text-slate-300">{exam.subject || "—"}</td>
                    <td className="px-4 py-4 text-slate-300">{exam.duration_minutes} minutes</td>
                    <td className="px-4 py-4 text-slate-300">{exam.total_questions}</td>
                    <td className="px-4 py-4 text-slate-300">{exam.max_marks === null || exam.max_marks === undefined ? "Not available yet" : exam.max_marks}</td>
                    <td className="px-4 py-4"><div className="flex flex-wrap gap-2">
                      <Link href={`/examiner/exams/${exam.id}/question-bank`} className="rounded-lg bg-cyan-600/20 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-600/30">Manage Examination</Link>
                      <button type="button" onClick={() => deleteExam(exam)} disabled={workingId === exam.id} className="rounded-lg border border-red-500/40 px-3 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-50">{workingId === exam.id ? "Deleting..." : "Delete"}</button>
                    </div></td>
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

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface HistoricalResult {
  result_id: number;
  session_id: number;
  exam_title: string;
  student_name: string;
  obtained_marks: number;
  total_marks: number;
  percentage: number;
  grade: string;
  published: boolean;
  submitted_at?: string | null;
}
interface ReviewSession {
  session_id: number;
  exam_id: number;
  exam_title: string;
  student_id: number;
  student_name: string;
  session_status: string;
  can_manage: boolean;
  submitted_at?: string | null;
  face_photo_url?: string | null;
  result_ready: boolean;
  is_published: boolean;
  obtained_marks?: number | null;
  total_marks?: number | null;
  percentage?: number | null;
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

export default function ExaminerResultsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<ReviewSession[]>([]);
  const [history, setHistory] = useState<HistoricalResult[]>([]);
  const [staffRole, setStaffRole] = useState<"admin" | "examiner">("examiner");
  const [loading, setLoading] = useState(true);
  const [publishingId, setPublishingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [facePhotoUrls, setFacePhotoUrls] = useState<Record<number, string>>({});

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [sessionsResponse, historyResponse, profileResponse] = await Promise.all([
        fetch(`${API_URL}/grading/sessions`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/results/staff/history`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
      ]);
      if ([sessionsResponse, historyResponse, profileResponse].some((response) => response.status === 401 || response.status === 403)) {
        router.replace("/login");
        return;
      }
      const [sessionData, historyData, profile] = await Promise.all([
        sessionsResponse.json().catch(() => ({})),
        historyResponse.json().catch(() => ({})),
        profileResponse.json().catch(() => ({})),
      ]);
      if (!sessionsResponse.ok || !historyResponse.ok || !profileResponse.ok) {
        throw new Error("Unable to load examination result history.");
      }
      setStaffRole(profile.role === "admin" ? "admin" : "examiner");
      setSessions(Array.isArray(sessionData.sessions) ? sessionData.sessions : []);
      setHistory(Array.isArray(historyData.results) ? historyData.results : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sessions.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    let cancelled = false;
    const createdUrls: string[] = [];
    const token = localStorage.getItem("examguard_access_token");
    if (!token || sessions.length === 0) { setFacePhotoUrls({}); return; }
    Promise.all(sessions.filter((session) => session.face_photo_url).map(async (session) => {
      try {
        const response = await fetch(API_URL + session.face_photo_url, {
          headers: { Authorization: "Bearer " + token }, cache: "no-store",
        });
        if (!response.ok) return null;
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        createdUrls.push(url);
        return [session.session_id, url] as const;
      } catch { return null; }
    })).then((items) => {
      if (cancelled) return;
      const next: Record<number, string> = {};
      for (const item of items) if (item) next[item[0]] = item[1];
      setFacePhotoUrls(next);
    });
    return () => { cancelled = true; createdUrls.forEach((url) => URL.revokeObjectURL(url)); };
  }, [sessions]);

  async function publishResult(sessionId: number) {
    if (!window.confirm("Publish this result so the student can view it?")) {
      return;
    }
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    setPublishingId(sessionId);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        `${API_URL}/grading/sessions/${sessionId}/publish`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to publish this result.");
      }
      setMessage(`Result for session #${sessionId} published successfully.`);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish result.");
    } finally {
      setPublishingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href={staffRole === "admin" ? "/admin/dashboard" : "/examiner/dashboard"} className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">{staffRole === "admin" ? "Admin / Result Publication" : "Examiner / Result Publication"}</p>
          </div>
          <Link href={staffRole === "admin" ? "/admin/dashboard" : "/examiner/dashboard"} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Result Review & Publication</h1>
            <p className="mt-2 text-slate-400">
              Review and publish results for examinations you created. Grade all subjective answers before publishing.
            </p>
          </div>
          <button
            type="button"
            onClick={loadSessions}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}
        {message && <div role="status" className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-300">{message}</div>}

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          {loading ? (
            <p className="py-12 text-center text-slate-400">Loading submitted sessions...</p>
          ) : sessions.length === 0 ? (
            <p className="py-12 text-center text-slate-400">No submitted sessions are available for review.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Examination</th>
                    <th className="px-4 py-3">Student</th>
                    <th className="px-4 py-3">Candidate photo</th>
                    <th className="px-4 py-3">Progress</th>
                    <th className="px-4 py-3">Submitted</th>
                    <th className="px-4 py-3">Score</th>
                    <th className="px-4 py-3">Publication</th>
                    <th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.session_id} className="border-b border-white/5 last:border-0">
                      <td className="px-4 py-4 font-semibold">{session.exam_title}</td>
                      <td className="px-4 py-4">{session.student_name}</td>
                      <td className="px-4 py-4">{facePhotoUrls[session.session_id] ? <img src={facePhotoUrls[session.session_id]} alt="Candidate face captured before the examination" className="h-14 w-14 rounded-lg object-cover" /> : "—"}</td>
                      <td className="px-4 py-4">{session.session_status === "in_progress" ? "In progress" : session.session_status === "not_started" ? "Pre-start" : session.session_status === "auto_submitted" ? "Auto-submitted" : "Submitted"}</td>
                      <td className="px-4 py-4 text-slate-400">{formatDate(session.submitted_at)}</td>
                      <td className="px-4 py-4 tabular-nums">
                        {session.result_ready
                          ? `${session.obtained_marks} / ${session.total_marks}`
                          : "Awaiting grading"}
                      </td>
                      <td className="px-4 py-4">
                        {session.is_published ? "Published" : "Not published"}
                      </td>
                      <td className="px-4 py-4">
                        {session.is_published ? (
                          <span className="text-green-300">Student can view</span>
                        ) : !session.can_manage ? (
                          <span className="text-slate-400">View only</span>
                        ) : session.session_status === "submitted" || session.session_status === "auto_submitted" ? (
                          <button
                            type="button"
                            onClick={() => publishResult(session.session_id)}
                            disabled={publishingId === session.session_id || !session.result_ready}
                            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold hover:bg-blue-500 disabled:opacity-50"
                          >
                            {publishingId === session.session_id ? "Publishing..." : session.result_ready ? "Publish result" : "Awaiting grading"}
                          </button>
                        ) : (
                          <span className="text-slate-400">Awaiting submission</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold">Historical Results</h2>
              <p className="mt-1 text-sm text-slate-400">Previously calculated results for examinations you created.</p>
            </div>
            <span className="text-sm text-slate-400">{history.length} result(s)</span>
          </div>
          {history.length === 0 ? (
            <p className="py-8 text-center text-slate-400">No historical results are available.</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Examination</th><th className="p-3">Student</th><th className="p-3">Score</th><th className="p-3">Percentage</th><th className="p-3">Grade</th><th className="p-3">Status</th></tr></thead>
                <tbody>{history.map((item) => <tr key={item.result_id} className="border-b border-white/5"><td className="p-3">{item.exam_title}</td><td className="p-3">{item.student_name}</td><td className="p-3 tabular-nums">{item.obtained_marks} / {item.total_marks}</td><td className="p-3 tabular-nums">{Number(item.percentage).toFixed(2)}%</td><td className="p-3 font-semibold text-cyan-300">{item.grade || "—"}</td><td className="p-3">{item.published ? "Published" : "Awaiting publication"}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

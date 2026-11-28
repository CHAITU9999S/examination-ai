"use client";

import Image from "next/image";
import { formatISTDateTime } from "@/lib/utils";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../../admin/components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProctorEvent {
  event_id: number;
  event_type: string;
  description?: string | null;
  suspicion_points?: number | null;
  cumulative_suspicion_score?: number | null;
  created_at?: string | null;
  snapshot_data?: string | null;
}

interface CohortAnalytics {
  exam_id: number;
  exam_title: string;
  cohort_size: number;
  metrics: Record<string, number | null>;
  score_distribution: Array<{ label: string; count: number }>;
  metric_note: string;
}

interface FlaggedSession {
  session_id: number;
  exam_id: number;
  exam_title: string;
  creator_name?: string | null;
  creator_role?: string | null;
  assigned_by_name?: string | null;
  assigned_by_role?: string | null;
  student_id: number;
  student_name: string;
  session_status: string;
  started_at?: string | null;
  submitted_at?: string | null;
  suspicion_score: number;
  auto_flagged: boolean;
  tab_switch_count: number;
  tab_switch_threshold?: number | null;
  event_counts: Record<string, number>;
  events: ProctorEvent[];
  webcam_snapshots_available?: boolean;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return formatISTDateTime(value, "—");
}

export default function StaffProctoringReviewPage() {
  const router = useRouter();
  const [requestedSessionId, setRequestedSessionId] = useState<string | null>(null);
  const [requestedReturnTo, setRequestedReturnTo] = useState<string | null>(null);
  const [sessions, setSessions] = useState<FlaggedSession[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [selected, setSelected] = useState<FlaggedSession | null>(null);
  const [analytics, setAnalytics] = useState<CohortAnalytics | null>(null);
  const [analyticsError, setAnalyticsError] = useState("");
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dashboardHref, setDashboardHref] = useState("/examiner/dashboard");

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    setRequestedSessionId(query.get("session_id"));
    setRequestedReturnTo(query.get("return_to"));
  }, []);

  const loadFlaggedSessions = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [profileResponse, response] = await Promise.all([
        fetch(`${API_URL}/users/me`, { headers, cache: "no-store" }),
        fetch(`${API_URL}/exam-sessions/proctoring/flagged`, { headers, cache: "no-store" }),
      ]);
      const profile = await profileResponse.json().catch(() => ({}));
      if (!profileResponse.ok || (profile.role !== "admin" && profile.role !== "examiner")) {
        router.replace("/login");
        return;
      }
      setDashboardHref(profile.role === "admin" ? "/admin/dashboard" : "/examiner/dashboard");
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error("Unable to load flagged examination sessions.");
      }
      const data = await response.json();
      const list = Array.isArray(data.sessions) ? data.sessions : [];
      setSessions(list);
      if (requestedSessionId && /^\d+$/.test(requestedSessionId)) {
        const historyResponse = await fetch(`${API_URL}/exam-sessions/${requestedSessionId}/proctoring/history`, { headers, cache: "no-store" });
        const historyData = await historyResponse.json().catch(() => ({}));
        if (!historyResponse.ok) throw new Error(historyData.detail || "Unable to load this student's proctoring details.");
        setSelected(historyData as FlaggedSession);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load proctoring review.");
    } finally {
      setLoading(false);
    }
  }, [router, requestedSessionId]);

  useEffect(() => {
    loadFlaggedSessions();
  }, [loadFlaggedSessions]);

  useEffect(() => {
    if (!selected?.exam_id) {
      setAnalytics(null);
      setAnalyticsError("");
      return;
    }
    let cancelled = false;
    const token = localStorage.getItem("examguard_access_token");
    if (!token) return;
    setAnalyticsLoading(true);
    setAnalyticsError("");
    fetch(`${API_URL}/exam-sessions/proctoring/analytics?exam_id=${selected.exam_id}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to load cohort proctoring analytics.");
        return data as CohortAnalytics;
      })
      .then((data) => { if (!cancelled) setAnalytics(data); })
      .catch((err) => { if (!cancelled) setAnalyticsError(err instanceof Error ? err.message : "Unable to load cohort analytics."); })
      .finally(() => { if (!cancelled) setAnalyticsLoading(false); });
    return () => { cancelled = true; };
  }, [selected?.exam_id]);

  const visibleSessions = [...sessions]
    .filter((session) => !searchTerm.trim() || [session.exam_title, session.student_name, session.session_id].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "student") return a.student_name.localeCompare(b.student_name);
      if (sortBy === "score-high") return b.suspicion_score - a.suspicion_score;
      if (sortBy === "score-low") return a.suspicion_score - b.suspicion_score;
      if (sortBy === "oldest") return String(a.started_at || "").localeCompare(String(b.started_at || ""));
      return String(b.started_at || "").localeCompare(String(a.started_at || ""));
    });

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href={dashboardHref} className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Staff / Proctoring Review</p>
          </div>
          <AdminSectionNavigation
            previousHref={requestedReturnTo && (requestedReturnTo.startsWith("/admin/exams/") || requestedReturnTo.startsWith("/staff/manage-exams/")) ? requestedReturnTo : dashboardHref === "/admin/dashboard" ? "/admin/sections/examinations" : "/examiner/dashboard"}
            previousLabel="Previous Section"
            dashboardHref={dashboardHref}
          />
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Flagged Examination Sessions</h1>
            <p className="mt-2 text-slate-400">
              Review server-recorded events, suspicion scores, and limited event-triggered evidence snapshots where available.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
          <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search student or examination" aria-label="Search flagged sessions" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort flagged sessions" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="student">Student name</option><option value="score-high">Highest suspicion score</option><option value="score-low">Lowest suspicion score</option></select>
          <button
            type="button"
            onClick={loadFlaggedSessions}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          </div>
        </div>

        {error && <div role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">{error}</div>}

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <section className="space-y-3">
            {loading ? (
              <p className="py-10 text-center text-slate-400">Loading flagged sessions...</p>
            ) : visibleSessions.length === 0 ? (
              <p className="rounded-xl border border-white/10 bg-slate-900 p-8 text-center text-slate-400">No flagged sessions found.</p>
            ) : visibleSessions.map((session) => (
              <button
                type="button"
                key={session.session_id}
                onClick={() => setSelected(session)}
                className={`w-full rounded-xl border p-5 text-left transition ${selected?.session_id === session.session_id ? "border-blue-400 bg-slate-800" : "border-white/10 bg-slate-900 hover:border-white/30"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{session.exam_title}</p>
                    <p className="mt-1 text-sm text-slate-400">{session.student_name}</p>
                    <p className="mt-1 text-xs text-slate-400">Created by: {session.creator_name || "Unknown"} · Assigned by: {session.assigned_by_name || "Unknown"}</p>
                    <p className="mt-1 text-xs text-slate-500">Session #{session.session_id} · {session.session_status}</p>
                  </div>
                  <span className="rounded-full bg-red-500/10 px-3 py-1 text-xs font-semibold text-red-300">
                    {session.suspicion_score.toFixed(0)} / 100
                  </span>
                </div>
              </button>
            ))}
          </section>

          <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
            {!selected ? (
              <p className="py-10 text-center text-slate-400">Select a flagged session to review its events.</p>
            ) : (
              <>
                <h2 className="text-xl font-bold">{selected.exam_title}</h2>
                <div className="mt-5 rounded-xl border border-white/10 bg-slate-800/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-semibold">Proctoring signal breakdown — this examination</h3>
                    <span className="text-xs text-slate-400">{analytics?.cohort_size ?? 0} finished session(s)</span>
                  </div>
                  {analyticsLoading && <p className="mt-3 text-sm text-slate-400">Loading cohort analytics...</p>}
                  {analyticsError && <p role="alert" className="mt-3 text-sm text-red-300">{analyticsError}</p>}
                  {analytics && (
                    <>
                      <div className="mt-4 space-y-3">
                        {[
                          ["No face-loss events", analytics.metrics.no_face_loss_events],
                          ["No gaze-away events", analytics.metrics.no_gaze_away_events],
                          ["No tab switches", analytics.metrics.no_tab_switches],
                          ["No multiple-face events", analytics.metrics.no_multiple_face_events],
                          ["High suspicion (>60)", analytics.metrics.high_suspicion_over_60],
                          ["Face present (estimated)", analytics.metrics.face_present_rate],
                          ["Gaze on screen (estimated)", analytics.metrics.gaze_on_screen_rate],
                          ["Monitoring coverage (estimated)", analytics.metrics.monitoring_coverage_rate],
                        ].map(([label, value]) => (
                          <div key={String(label)}>
                            <div className="mb-1 flex justify-between gap-3 text-sm"><span>{label}</span><span className="tabular-nums">{value == null ? "Not available" : `${value}%`}</span></div>
                            <div className="h-2 overflow-hidden rounded-full bg-slate-950"><div className={`h-full rounded-full ${label === "High suspicion (>60)" ? "bg-red-500" : "bg-emerald-500"}`} style={{ width: `${value ?? 0}%` }} /></div>
                          </div>
                        ))}
                      </div>
                      <h4 className="mt-5 text-sm font-semibold">Suspicion score distribution</h4>
                      <div className="mt-3 grid grid-cols-5 items-end gap-2">
                        {analytics.score_distribution.map((band) => {
                          const max = Math.max(1, ...analytics.score_distribution.map((item) => item.count));
                          return <div key={band.label} className="text-center"><div className="flex h-28 items-end justify-center"><div className="w-full rounded-t bg-blue-500" style={{ height: `${Math.max(4, band.count / max * 100)}%` }} title={`${band.count} session(s)`} /></div><p className="mt-2 text-[10px] text-slate-400">{band.label}</p><p className="text-xs">{band.count}</p></div>;
                        })}
                      </div>
                      <p className="mt-4 text-xs text-slate-500">{analytics.metric_note}</p>
                    </>
                  )}
                </div>
                <p className="mt-1 text-sm text-slate-400">{selected.student_name} · Session #{selected.session_id}</p>
                <p className="mt-1 text-xs text-slate-400">Created by: {selected.creator_name || "Unknown"} · Assigned by: {selected.assigned_by_name || "Unknown"}</p>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg bg-slate-800 p-4">
                    <p className="text-xs text-slate-400">Suspicion score</p>
                    <p className="mt-1 text-2xl font-bold">{selected.suspicion_score.toFixed(0)} / 100</p>
                  </div>
                  <div className="rounded-lg bg-slate-800 p-4">
                    <p className="text-xs text-slate-400">Tab switches</p>
                    <p className="mt-1 text-2xl font-bold">{selected.tab_switch_count} / {selected.tab_switch_threshold ?? "—"}</p>
                  </div>
                </div>
                <div className="mt-5 space-y-2 text-sm text-slate-300">
                  <p>Started: {formatDate(selected.started_at)}</p>
                  <p>Submitted: {formatDate(selected.submitted_at)}</p>
                  <p>Automatic tab-switch flag: {selected.auto_flagged ? "Yes" : "No"}</p>
                </div>
                <h3 className="mt-7 font-semibold">Recorded proctoring events</h3>
                {selected.events.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-400">No individual events were returned.</p>
                ) : (
                  <div className="mt-3 space-y-3">
                    {selected.events.map((event) => (
                      <article key={event.event_id} className="rounded-lg bg-slate-800 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-semibold capitalize">{event.event_type.replaceAll("_", " ")}</p>
                          <p className="text-xs text-slate-500">{formatDate(event.created_at)}</p>
                        </div>
                        <p className="mt-2 text-sm text-slate-300">{event.description || "No additional description."}</p>
                        <p className="mt-2 text-xs text-slate-500">
                          Points: {event.suspicion_points ?? 0} · Cumulative: {event.cumulative_suspicion_score ?? 0}
                        </p>
                        {event.snapshot_data && (
                          <div className="mt-3">
                            <p className="mb-2 text-xs font-semibold text-amber-200">Event-triggered evidence snapshot</p>
                            <Image src={event.snapshot_data} alt={`Evidence snapshot for ${event.event_type.replaceAll("_", " ")}`} width={320} height={240} unoptimized className="max-h-60 w-auto rounded-lg border border-white/10 object-contain" />
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                )}
                <p className="mt-6 rounded-lg border border-blue-400/20 bg-blue-500/5 p-4 text-xs text-slate-400">
                  Privacy: continuous video is never uploaded. Up to eight low-resolution snapshots may be stored per session for multiple-face or gaze-away events and are visible only to the Admin and examination creator.
                </p>
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

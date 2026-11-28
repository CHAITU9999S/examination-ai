import Image from "next/image";
"use client";

import { useEffect, useState } from "react";
import { formatISTDateTime } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ProctorEvent = {
  event_id: number;
  event_type: string;
  description?: string | null;
  suspicion_points?: number | null;
  cumulative_suspicion_score?: number | null;
  created_at?: string | null;
  snapshot_data?: string | null;
};

type ProctoringHistory = {
  session_id: number;
  exam_title?: string;
  student_name?: string;
  session_status?: string;
  suspicion_score?: number;
  last_heartbeat_at?: string | null;
  last_heartbeat_signals?: {
    event_counts?: Record<string, number>;
    total_event_count?: number;
    tab_switch_count?: number;
    auto_flagged?: boolean;
    client_reported_monitoring_metrics?: {
      monitoring_seconds?: number;
      face_present_seconds?: number;
      multiple_face_seconds?: number;
      face_missing_seconds?: number;
      gaze_measured_seconds?: number;
      gaze_on_screen_seconds?: number;
      gaze_away_seconds?: number;
    };
  } | null;
  tab_switch_count?: number;
  tab_switch_threshold?: number | null;
  auto_flagged?: boolean;
  total_events?: number;
  event_counts?: Record<string, number>;
  events?: ProctorEvent[];
  webcam_snapshots_available?: boolean;
  integrity_decision?: { decision: "pass" | "disqualify"; reason?: string | null; decided_by_name?: string; decided_at?: string } | null;
  integrity_decision_history?: Array<{ decision: "pass" | "disqualify"; reason?: string | null; decided_by_name?: string; decided_at?: string }>;
};

function dateText(value?: string | null) {
  return formatISTDateTime(value, "Not available");
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <div className="rounded-xl bg-slate-800 p-4">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
    </div>
  );
}

export default function ProctoringReportPanel({ sessionId }: { sessionId: number | null | undefined }) {
  const [history, setHistory] = useState<ProctoringHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionMessage, setDecisionMessage] = useState("");

  useEffect(() => {
    if (!sessionId || !Number.isInteger(sessionId) || sessionId <= 0) {
      setHistory(null);
      return;
    }
    let cancelled = false;
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      setError("Staff sign-in is required to view proctoring details.");
      return;
    }
    setLoading(true);
    setError("");
    fetch(`${API_URL}/exam-sessions/${sessionId}/proctoring/history`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to load proctoring details.");
        return data as ProctoringHistory;
      })
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load proctoring details.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (!sessionId) {
    return (
      <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
        <h2 className="text-lg font-bold">AI Proctoring Report</h2>
        <p className="mt-2 text-sm text-slate-400">No examination session was created, so there are no individual proctoring records.</p>
      </section>
    );
  }

  const submitIntegrityDecision = async (decision: "pass" | "disqualify") => {
    if (!sessionId || decisionBusy) return;
    if (decision === "disqualify" && !decisionReason.trim()) {
      setError("Enter a reason before disqualifying this session.");
      return;
    }
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      setError("Staff sign-in is required to record an integrity decision.");
      return;
    }
    setDecisionBusy(true);
    setError("");
    setDecisionMessage("");
    try {
      const response = await fetch(`${API_URL}/exam-sessions/${sessionId}/proctoring/integrity-decision`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason: decisionReason.trim() || null }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to record the integrity decision.");
      setHistory((current) => current ? {
        ...current,
        integrity_decision: data.integrity_decision,
        integrity_decision_history: data.integrity_decision_history,
      } : current);
      setDecisionReason("");
      setDecisionMessage("Integrity decision recorded. Marks and result publication remain unchanged.");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to record the integrity decision.");
    } finally {
      setDecisionBusy(false);
    }
  };

  const counts = history?.event_counts || history?.last_heartbeat_signals?.event_counts || {};
  const events = history?.events || [];
  const suspicion = Number(history?.suspicion_score || 0);
  const sampled = history?.last_heartbeat_signals?.client_reported_monitoring_metrics;
  const percent = (part?: number, whole?: number) =>
    whole && whole > 0 && typeof part === "number" ? `${Math.round(part / whole * 1000) / 10}%` : "Not available";
  const metrics = [
    { label: "Face present", value: percent(sampled?.face_present_seconds, sampled?.monitoring_seconds) },
    { label: "Gaze on screen", value: percent(sampled?.gaze_on_screen_seconds, sampled?.gaze_measured_seconds) },
    { label: "Monitoring sampled", value: sampled?.monitoring_seconds ? `${sampled.monitoring_seconds}s` : "Not available" },
    { label: "Tab switches", value: counts.tab_switch ?? history?.tab_switch_count ?? 0 },
    { label: "Face not detected", value: counts.face_not_detected ?? 0 },
    { label: "Multiple faces", value: counts.multiple_faces ?? 0 },
    { label: "Gaze away", value: counts.gaze_away ?? 0 },
    { label: "Window lost focus", value: counts.window_blur ?? 0 },
    { label: "Webcam errors", value: counts.webcam_error ?? 0 },
  ];

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">AI Proctoring Report</h2>
          <p className="mt-1 text-sm text-slate-400">Session #{sessionId} · Server-recorded signals and event history</p>
        </div>
        {history && (
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${suspicion > 60 ? "bg-red-500/15 text-red-300" : suspicion >= 50 ? "bg-amber-500/15 text-amber-300" : "bg-emerald-500/15 text-emerald-300"}`}>
            {suspicion.toFixed(0)} / 100 suspicion
          </span>
        )}
      </div>

      {loading && <p className="mt-4 text-sm text-slate-400">Loading proctoring report...</p>}
      {error && <p role="alert" className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}

      {history && (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Metric label="Suspicion score" value={`${suspicion.toFixed(0)} / 100`} detail={suspicion > 60 ? "High suspicion (>60)" : "Score recorded by the server"} />
            <Metric label="Total recorded events" value={history.total_events ?? events.length} />
            <Metric label="Tab-switch threshold" value={history.tab_switch_threshold ?? "Not configured"} detail={history.auto_flagged ? "Automatic tab-switch flag triggered" : "No automatic tab-switch flag"} />
            {metrics.map((metric) => <Metric key={metric.label} label={metric.label} value={metric.value} />)}
          </div>

          <div className="mt-4 rounded-xl bg-slate-800/70 p-4 text-sm text-slate-300">
            <p>Last heartbeat: {dateText(history.last_heartbeat_at)}</p>
            <p className="mt-1">Session status: {(history.session_status || "unknown").replaceAll("_", " ")}</p>
            <p className="mt-1">Automatic flag: {history.auto_flagged ? "Yes" : "No"}</p>
            <p className="mt-1">Event-triggered snapshots: {history.webcam_snapshots_available ? "Available for review" : "None recorded"}</p>
          </div>

          <section className="mt-6 rounded-xl border border-white/10 bg-slate-800/70 p-4">
            <h3 className="font-semibold">Examiner integrity decision</h3>
            {history.integrity_decision ? (
              <div className="mt-2 rounded-lg bg-slate-900 p-3 text-sm">
                <p className={history.integrity_decision.decision === "disqualify" ? "font-semibold text-red-300" : "font-semibold text-emerald-300"}>
                  {history.integrity_decision.decision === "disqualify" ? "Session disqualified" : "Integrity passed"}
                </p>
                {history.integrity_decision.reason && <p className="mt-1 text-slate-300">Reason: {history.integrity_decision.reason}</p>}
                <p className="mt-1 text-xs text-slate-500">Recorded by {history.integrity_decision.decided_by_name || "staff"} · {dateText(history.integrity_decision.decided_at)}</p>
              </div>
            ) : <p className="mt-2 text-sm text-slate-400">No integrity decision has been recorded.</p>}
            {history.session_status !== "in_progress" && (
              <>
                <label className="mt-3 block text-xs text-slate-400" htmlFor={`integrity-reason-${sessionId}`}>Decision reason (required for disqualification)</label>
                <textarea id={`integrity-reason-${sessionId}`} value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} maxLength={2000} rows={2} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 p-3 text-sm text-white" placeholder="Enter the reason or review notes..." />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" disabled={decisionBusy} onClick={() => void submitIntegrityDecision("pass")} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold disabled:opacity-50">Mark integrity passed</button>
                  <button type="button" disabled={decisionBusy || !decisionReason.trim()} onClick={() => void submitIntegrityDecision("disqualify")} className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold disabled:opacity-50">Disqualify session</button>
                </div>
                <p className="mt-2 text-xs text-slate-500">This records an auditable review decision only. It does not alter awarded marks or automatically publish/reject a result; existing examiner result approval remains in control.</p>
              </>
            )}
            {decisionMessage && <p role="status" className="mt-2 text-sm text-emerald-300">{decisionMessage}</p>}
          </section>

          <h3 className="mt-6 font-semibold">Recorded proctoring events</h3>
          {events.length === 0 ? (
            <p className="mt-2 text-sm text-slate-400">No individual violation events were recorded for this session.</p>
          ) : (
            <div className="mt-3 max-h-96 space-y-2 overflow-y-auto">
              {events.map((event) => (
                <article key={event.event_id} className="rounded-lg border border-white/5 bg-slate-800 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold capitalize">{event.event_type.replaceAll("_", " ")}</p>
                    <time className="text-xs text-slate-500">{dateText(event.created_at)}</time>
                  </div>
                  <p className="mt-1 text-sm text-slate-300">{event.description || "No additional description."}</p>
                  <p className="mt-1 text-xs text-slate-500">Points: {event.suspicion_points ?? 0} · Cumulative score: {event.cumulative_suspicion_score ?? 0}</p>
                  {event.snapshot_data && (
                    <div className="mt-3">
                      <p className="mb-2 text-xs font-semibold text-amber-200">Event-triggered evidence snapshot</p>
                      <Image src={event.snapshot_data} alt={`Webcam evidence for ${event.event_type.replaceAll("_", " ")} event`} width={320} height={240} unoptimized className="max-h-60 w-auto rounded-lg border border-white/10 object-contain" />
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}

          <p className="mt-4 rounded-lg border border-blue-400/20 bg-blue-500/5 p-3 text-xs text-slate-400">
            Only low-resolution snapshots captured when multiple faces or gaze-away events are detected are stored (maximum eight per session). Continuous video and routine camera frames are never uploaded. Face/gaze percentages are browser-side detector estimates from one-second samples; they are indicative and not tamper-proof proof of candidate conduct.
          </p>
        </>
      )}
    </section>
  );
}

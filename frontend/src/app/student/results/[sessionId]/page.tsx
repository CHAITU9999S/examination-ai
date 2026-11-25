"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QuestionResult {
  question_id: number;
  question_text?: string | null;
  question_type?: string;
  maximum_marks: number;
  awarded_marks: number;
  outcome: "correct" | "incorrect" | "partial" | "unanswered";
  examiner_feedback?: string | null;
  rubric_scores?: Array<{
    criterion: string;
    description?: string | null;
    max_marks: number;
    awarded_marks: number;
  }> | null;
  image_annotations?: Array<{
    annotation_type: string;
    x: number;
    y: number;
    width: number;
    height: number;
    text: string;
  }> | null;
}

interface CohortDistribution {
  cohort_size: number;
  current_student_percentage: number | null;
  score_bands: Array<{
    label: string;
    count: number;
    share_percentage: number;
  }>;
}

interface ResultDetails {
  exam_title: string;
  creator_name?: string | null;
  creator_role?: string | null;
  assigned_by_name?: string | null;
  assigned_by_role?: string | null;
  total_marks: number;
  obtained_marks: number;
  percentage: number;
  grade: string;
  percentile: number;
  cohort_distribution?: CohortDistribution;
  published_at?: string | null;
  face_photo_url?: string | null;
  question_results: QuestionResult[];
}

interface ResultStatus {
  exam_title: string;
  subject?: string | null;
  creator_name?: string | null;
  creator_role?: string | null;
  assigned_by_name?: string | null;
  assigned_by_role?: string | null;
  session_status: string | null;
  submitted_at?: string | null;
  result_published: boolean;
}

export default function StudentResultDetailPage() {
  const router = useRouter();
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;

  const [result, setResult] = useState<ResultDetails | null>(null);
  const [notDeclared, setNotDeclared] = useState<ResultStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [facePhotoUrl, setFacePhotoUrl] = useState("");

  const loadResult = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const statusResponse = await fetch(`${API_URL}/results/session-status/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (statusResponse.status === 401 || statusResponse.status === 403) {
        router.replace("/login");
        return;
      }
      if (!statusResponse.ok) {
        const data = await statusResponse.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to load examination status.");
      }
      const statusData: ResultStatus = await statusResponse.json();
      if (!statusData.result_published) {
        setNotDeclared(statusData);
        setResult(null);
        return;
      }
      setNotDeclared(null);
      const response = await fetch(`${API_URL}/results/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to load result details.");
      }
      setResult(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load result.");
    } finally {
      setLoading(false);
    }
  }, [router, sessionId]);

  useEffect(() => {
    if (sessionId) loadResult();
  }, [loadResult, sessionId]);

  useEffect(() => {
    if (!result?.face_photo_url) { setFacePhotoUrl(""); return; }
    let cancelled = false;
    let objectUrl: string | null = null;
    const token = localStorage.getItem("examguard_access_token");
    if (!token) return;
    fetch(API_URL + result.face_photo_url, { headers: { Authorization: "Bearer " + token }, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load the examination face photo.");
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setFacePhotoUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(() => { if (!cancelled) setFacePhotoUrl(""); });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [result?.face_photo_url]);

  const percentage = Math.max(0, Math.min(100, Number(result?.percentage || 0)));

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/student/results" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Examination Performance</p>
          </div>
          <Link href="/student/results" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← My Results
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-10">
        {loading ? (
          <p className="py-16 text-center text-slate-400">Loading result...</p>
        ) : error ? (
          <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-red-300">
            {error}
          </div>
        ) : notDeclared ? (
          <section className="rounded-2xl border border-amber-500/20 bg-slate-900 p-8">
            <h1 className="text-2xl font-bold">{notDeclared.exam_title}</h1>
            <p className="mt-2 text-sm text-slate-400">{notDeclared.subject || "Examination performance"}</p>
            <p className="mt-2 text-xs text-slate-400">Created by: {notDeclared.creator_name || "Unknown"} · Assigned by: {notDeclared.assigned_by_name || "Unknown"}</p>
            <div className="mt-6 rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
              <p className="font-semibold text-amber-300">Result Not Declared</p>
              <p className="mt-2 text-sm text-slate-300">Your examination has been submitted or expired, but the result has not yet been published. Marks and question-wise evaluation will appear here after publication.</p>
              <p className="mt-3 text-xs capitalize text-slate-400">Session status: {(notDeclared.session_status || "not available").replaceAll("_", " ")}</p>
            </div>
          </section>
        ) : result ? (
          <>
            <h1 className="text-3xl font-bold">{result.exam_title}</h1>
            <p className="mt-2 text-xs text-slate-400">Created by: {result.creator_name || "Unknown"} · Assigned by: {result.assigned_by_name || "Unknown"}</p>
            {result.face_photo_url && (
              <section className="mt-6 flex justify-end">
                <figure className="w-32 rounded-xl border border-white/10 bg-slate-900 p-3 text-center">
                  {facePhotoUrl ? <img src={facePhotoUrl} alt="Your face photo captured before the examination" className="h-28 w-full rounded-lg object-cover" /> : <div className="flex h-28 items-center justify-center text-xs text-slate-400">Loading photo...</div>}
                  <figcaption className="mt-2 text-xs text-slate-400">Your examination photo</figcaption>
                </figure>
              </section>
            )}
            <section className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Overall score</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">
                  {result.obtained_marks} / {result.total_marks}
                </p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Percentage</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">{percentage.toFixed(2)}%</p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-700">
                  <div className="h-full rounded-full bg-blue-500" style={{ width: `${percentage}%` }} />
                </div>
              </article>
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Grade</p>
                <p className="mt-3 text-3xl font-bold text-cyan-300">{result.grade || "—"}</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <p className="text-sm text-slate-400">Cohort percentile</p>
                <p className="mt-3 text-3xl font-bold tabular-nums">{Number(result.percentile).toFixed(1)}</p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-700" aria-label="Cohort percentile">
                  <div
                    className="h-full rounded-full bg-purple-500"
                    style={{ width: `${Math.max(0, Math.min(100, Number(result.percentile || 0)))}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-slate-500">Compared with published results for this exam.</p>
              </article>
            </section>

            {result.cohort_distribution && (
              <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold">Cohort score distribution</h2>
                    <p className="mt-1 text-sm text-slate-400">
                      Anonymized published scores for this examination
                    </p>
                  </div>
                  <p className="text-sm text-slate-400">
                    {result.cohort_distribution.cohort_size} published results
                  </p>
                </div>
                <div
                  className="mt-6 grid grid-cols-5 items-end gap-2 sm:grid-cols-10"
                  role="img"
                  aria-label="Distribution of published student scores grouped into ten-percent bands"
                >
                  {result.cohort_distribution.score_bands.map((band) => {
                    const maxShare = Math.max(
                      1,
                      ...result.cohort_distribution!.score_bands.map((item) => item.share_percentage)
                    );
                    const currentPercentage =
                      result.cohort_distribution!.current_student_percentage;
                    const bandStart = Number(band.label.split("-")[0]);
                    const isCurrentBand =
                      currentPercentage !== null &&
                      Math.min(9, Math.floor(currentPercentage / 10)) ===
                        Math.floor(bandStart / 10);
                    return (
                      <div key={band.label} className="flex min-w-0 flex-col items-center gap-2">
                        <span className="text-[10px] tabular-nums text-slate-400">{band.count}</span>
                        <div className="flex h-32 w-full items-end rounded-t bg-slate-800">
                          <div
                            className={`w-full rounded-t ${isCurrentBand ? "bg-purple-400" : "bg-blue-500"}`}
                            style={{ height: `${Math.max(3, (band.share_percentage / maxShare) * 100)}%` }}
                            title={`${band.label}: ${band.count} students`}
                          />
                        </div>
                        <span className="text-[9px] text-slate-400 sm:text-[10px]">{band.label}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-4 text-xs text-slate-500">
                  Purple marks the score band containing your result. Individual student scores are not disclosed.
                </p>
              </section>
            )}

            <section className="mt-10 space-y-4">
              <h2 className="text-xl font-bold">Question-wise evaluation</h2>
              {result.question_results.map((item) => (
                <article key={item.question_id} className="rounded-xl border border-white/10 bg-slate-900 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Question {item.question_id} · {item.question_type}</p>
                      <p className="mt-2 whitespace-pre-wrap font-medium">{item.question_text || "Question text unavailable"}</p>
                    </div>
                    <span className="rounded-full bg-slate-800 px-3 py-1 text-xs capitalize text-slate-300">
                      {item.outcome}
                    </span>
                  </div>
                  <p className="mt-4 text-sm text-slate-300">
                    Marks: {item.awarded_marks} / {item.maximum_marks}
                  </p>
                  {item.rubric_scores && item.rubric_scores.length > 0 && (
                    <div className="mt-4 rounded-lg border border-white/10 bg-slate-800 p-4">
                      <p className="text-sm font-semibold text-slate-200">Rubric breakdown</p>
                      <div className="mt-3 space-y-2">
                        {item.rubric_scores.map((rubric, index) => (
                          <div key={index} className="flex flex-wrap justify-between gap-3 text-sm">
                            <div>
                              <p className="font-medium">{rubric.criterion}</p>
                              {rubric.description && <p className="text-xs text-slate-400">{rubric.description}</p>}
                            </div>
                            <p className="tabular-nums">{rubric.awarded_marks} / {rubric.max_marks}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {item.examiner_feedback && (
                    <div className="mt-4 rounded-lg border border-blue-400/20 bg-blue-500/5 p-4">
                      <p className="text-sm font-semibold text-blue-300">Examiner feedback</p>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{item.examiner_feedback}</p>
                    </div>
                  )}
                  {item.image_annotations && item.image_annotations.length > 0 && (
                    <div className="mt-4">
                      <p className="text-sm font-semibold text-slate-300">Examiner image annotations</p>
                      <ul className="mt-2 space-y-2">
                        {item.image_annotations.map((annotation, index) => (
                          <li key={index} className="rounded-lg bg-slate-800 p-3 text-sm text-slate-300">
                            <span className="font-semibold capitalize">{annotation.annotation_type}</span>
                            {" · "}position {annotation.x.toFixed(1)}%, {annotation.y.toFixed(1)}%
                            <p className="mt-1">{annotation.text}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              ))}
            </section>
          </>
        ) : null}
      </div>
    </main>
  );
}


"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PendingAnswer {
  answer_id: number;
  session_id: number;
  question_id: number;
  student_id: number;
  student_name?: string;
  exam_id: number;
  exam_title?: string;
  question_text: string;
  question_type: string;
  answer_text?: string | null;
  image_path?: string | null;
  marks: number;
  awarded_marks?: number | null;
  ai_suggested_marks?: number | null;
  ai_justification?: string | null;
  ai_matched_points?: string[] | null;
  ai_missed_points?: string[] | null;
  ai_model?: string | null;
  examiner_feedback?: string | null;
  image_annotations?: ImageAnnotation[] | null;
}

interface ImageAnnotation {
  annotation_type: "highlight" | "comment";
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
}

interface GradingSuggestion {
  suggested_marks: number;
  justification: string;
  matched_points: string[];
  missed_points: string[];
}

export default function ExaminerGradingPage() {
  const router = useRouter();

  const [answers, setAnswers] = useState<PendingAnswer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [selectedAnswer, setSelectedAnswer] =
    useState<PendingAnswer | null>(null);

  const [suggestion, setSuggestion] =
    useState<GradingSuggestion | null>(null);

  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [awardedMarks, setAwardedMarks] = useState("");
  const [imagePreviewUrl, setImagePreviewUrl] = useState("");
  const [examinerFeedback, setExaminerFeedback] = useState("");
  const [imageAnnotations, setImageAnnotations] = useState<ImageAnnotation[]>([]);
  const [selectedForBulk, setSelectedForBulk] = useState<number[]>([]);
  const [bulkMarks, setBulkMarks] = useState<Record<number, string>>({});
  const [annotationType, setAnnotationType] = useState<"highlight" | "comment">("comment");
  const [annotationX, setAnnotationX] = useState("50");
  const [annotationY, setAnnotationY] = useState("50");
  const [annotationWidth, setAnnotationWidth] = useState("15");
  const [annotationHeight, setAnnotationHeight] = useState("10");
  const [annotationText, setAnnotationText] = useState("");

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

  const loadPendingAnswers = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(
        `${API_URL}/grading/pending`,
        {
          method: "GET",
          headers,
        }
      );

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load answers awaiting grading.");
      }

      const data = await response.json();

      const list = Array.isArray(data)
        ? data
        : Array.isArray(data.answers)
          ? data.answers
          : null;

      if (!list) {
        throw new Error("Unexpected grading data returned by the server.");
      }

      setAnswers(list);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load answers."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadPendingAnswers();
  }, [loadPendingAnswers]);

  useEffect(() => {
    if (!selectedAnswer?.image_path) {
      setImagePreviewUrl("");
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    const token = localStorage.getItem("examguard_access_token");

    if (!token) return;

    fetch(`${API_URL}/grading/answers/${selectedAnswer.answer_id}/image`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Unable to load the uploaded answer image.");
        }
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setImagePreviewUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch((imageError) => {
        if (!cancelled) {
          setImagePreviewUrl("");
          setError(imageError instanceof Error ? imageError.message : "Unable to load answer image.");
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selectedAnswer?.answer_id, selectedAnswer?.image_path]);

  function openAnswer(answer: PendingAnswer) {
    setSelectedAnswer(answer);

    const hasSavedAISuggestion =
      answer.ai_suggested_marks !== null &&
      answer.ai_suggested_marks !== undefined;

    setSuggestion(
      hasSavedAISuggestion
        ? {
            suggested_marks: answer.ai_suggested_marks as number,
            justification: answer.ai_justification || "No justification was saved.",
            matched_points: answer.ai_matched_points || [],
            missed_points: answer.ai_missed_points || [],
          }
        : null
    );

    setAwardedMarks(
      answer.awarded_marks !== null && answer.awarded_marks !== undefined
        ? String(answer.awarded_marks)
        : hasSavedAISuggestion
          ? String(answer.ai_suggested_marks)
          : ""
    );
    setExaminerFeedback(answer.examiner_feedback || "");
    setImageAnnotations(answer.image_annotations || []);
    setAnnotationText("");
    setError("");
    setMessage("");
  }

  function toggleBulkSelection(answer: PendingAnswer, checked: boolean) {
    if (checked) {
      const selected = answers.filter((item) => selectedForBulk.includes(item.answer_id));
      if (selected.length > 0 && selected[0].session_id !== answer.session_id) {
        setError("Bulk grading can include answers from one examination session only.");
        return;
      }
      setSelectedForBulk((current) =>
        current.includes(answer.answer_id) ? current : [...current, answer.answer_id]
      );
      setBulkMarks((current) => ({
        ...current,
        [answer.answer_id]: current[answer.answer_id] ?? "",
      }));
      setError("");
    } else {
      setSelectedForBulk((current) => current.filter((id) => id !== answer.answer_id));
      setBulkMarks((current) => {
        const next = { ...current };
        delete next[answer.answer_id];
        return next;
      });
    }
  }

  async function submitBulkGrades() {
    const selected = answers.filter((answer) =>
      selectedForBulk.includes(answer.answer_id)
    );
    if (selected.length === 0) {
      setError("Select at least one answer for bulk grading.");
      return;
    }
    const sessionId = selected[0].session_id;
    if (selected.some((answer) => answer.session_id !== sessionId)) {
      setError("Bulk grading can include answers from one examination session only.");
      return;
    }

    const grades = [];
    for (const answer of selected) {
      const raw = bulkMarks[answer.answer_id] ?? "";
      const marks = Number(raw);
      if (
        raw.trim() === "" ||
        !Number.isFinite(marks) ||
        marks < 0 ||
        marks > answer.marks
      ) {
        setError(`Enter valid marks between 0 and ${answer.marks} for answer #${answer.answer_id}.`);
        return;
      }
      grades.push({
        answer_id: answer.answer_id,
        awarded_marks: marks,
      });
    }

    setSaving(true);
    setError("");
    setMessage("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(
        `${API_URL}/grading/sessions/${sessionId}/bulk-grade`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ grades }),
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to save bulk grading.");
      }
      setMessage(`${data.graded_answer_count} answers were graded successfully.`);
      setSelectedForBulk([]);
      setBulkMarks({});
      await loadPendingAnswers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save bulk grading.");
    } finally {
      setSaving(false);
    }
  }

  async function requestAISuggestion() {
    if (!selectedAnswer) return;

    setError("");
    setMessage("");
    setSuggestion(null);
    setSuggestionLoading(true);

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(
        `${API_URL}/grading/answers/${selectedAnswer.answer_id}/ai-suggestion`,
        {
          method: "POST",
          headers,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to generate AI grading suggestion."
        );
      }

      setSuggestion(data);
      setAwardedMarks(String(data.suggested_marks));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "AI grading suggestion failed."
      );
    } finally {
      setSuggestionLoading(false);
    }
  }

  async function saveFinalMarks() {
    if (!selectedAnswer) return;

    const marks = Number(awardedMarks);

    if (
      awardedMarks.trim() === "" ||
      !Number.isFinite(marks) ||
      marks < 0 ||
      marks > selectedAnswer.marks
    ) {
      setError(
        `Enter marks between 0 and ${selectedAnswer.marks}.`
      );
      return;
    }

    setSaving(true);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(
        `${API_URL}/grading/answers/${selectedAnswer.answer_id}/grade`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            awarded_marks: marks,
            examiner_feedback: examinerFeedback.trim() || null,
            image_annotations: imageAnnotations,
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to save final marks."
        );
      }

      setMessage("Final marks saved successfully.");
      setSelectedAnswer(null);
      setSuggestion(null);
      setAwardedMarks("");
      setExaminerFeedback("");
      setImageAnnotations([]);

      await loadPendingAnswers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to save final marks."
      );
    } finally {
      setSaving(false);
    }
  }

  const questionGroups = answers.reduce<Record<string, PendingAnswer[]>>(
    (groups, answer) => {
      const key = `${answer.exam_id}-${answer.question_id}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(answer);
      return groups;
    },
    {}
  );

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link
              href="/examiner/dashboard"
              className="text-2xl font-bold"
            >
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>

            <p className="mt-1 text-sm text-slate-400">
              Examiner / Answer Grading
            </p>
          </div>

          <Link
            href="/examiner/dashboard"
            className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="text-3xl font-bold">
          Answer Grading
        </h1>

        <p className="mt-2 text-slate-400">
          Review subjective answers and approve their final marks.
          AI suggestions are optional and must be reviewed by an examiner.
        </p>

        {error && (
          <div
            role="alert"
            className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300"
          >
            {error}
          </div>
        )}

        {message && (
          <div
            role="status"
            className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-300"
          >
            {message}
          </div>
        )}

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">
                Answers Awaiting Grading
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                {answers.length} answer(s) pending
              </p>
            </div>

            {selectedForBulk.length > 0 && (
              <button
                type="button"
                onClick={submitBulkGrades}
                disabled={saving}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold hover:bg-green-500 disabled:opacity-50"
              >
                {saving ? "Saving..." : `Submit ${selectedForBulk.length} selected grades`}
              </button>
            )}
            <button
              type="button"
              onClick={loadPendingAnswers}
              disabled={loading}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="py-10 text-center text-slate-400">
              Loading answers...
            </p>
          ) : answers.length === 0 ? (
            <p className="py-10 text-center text-slate-400">
              No answers are currently awaiting grading.
            </p>
          ) : (
            <div className="mt-6 space-y-4">
              {Object.entries(questionGroups).map(([groupKey, group]) => (
                <div key={groupKey} className="rounded-xl border border-white/10 bg-slate-900/50 p-4">
                  <h3 className="mb-3 font-semibold text-blue-300">
                    {group[0].question_text}
                  </h3>
                  <div className="space-y-4">
                  {group.map((answer) => (
                <article
                  key={answer.answer_id}
                  className="rounded-xl border border-white/10 bg-slate-800/60 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <label className="flex items-center gap-2 text-xs text-slate-400">
                      <input
                        type="checkbox"
                        checked={selectedForBulk.includes(answer.answer_id)}
                        onChange={(event) => toggleBulkSelection(answer, event.target.checked)}
                        aria-label={`Select answer ${answer.answer_id} for bulk grading`}
                      />
                      Bulk select
                    </label>
                    {selectedForBulk.includes(answer.answer_id) && (
                      <label className="text-xs text-slate-400">
                        Marks
                        <input
                          type="number"
                          min="0"
                          max={answer.marks}
                          step="0.01"
                          value={bulkMarks[answer.answer_id] ?? ""}
                          onChange={(event) => setBulkMarks((current) => ({
                            ...current,
                            [answer.answer_id]: event.target.value,
                          }))}
                          className="ml-2 w-24 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-white"
                        />
                      </label>
                    )}
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold">
                        {answer.exam_title || `Examination #${answer.exam_id}`}
                      </h3>

                      <p className="mt-1 text-sm text-slate-400">
                        Student:{" "}
                        {answer.student_name ||
                          `Student #${answer.student_id}`}
                      </p>

                      <p className="mt-1 text-sm text-slate-400">
                        Question #{answer.question_id} ·{" "}
                        {answer.question_type} ·{" "}
                        {answer.marks} marks
                      </p>

                      <p className="mt-3 line-clamp-3 text-sm text-slate-300">
                        {answer.question_text}
                      </p>

                      <p className="mt-2 text-xs text-slate-500">
                        {answer.awarded_marks === null ||
                        answer.awarded_marks === undefined
                          ? "Not graded"
                          : `Current marks: ${answer.awarded_marks}`}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => openAnswer(answer)}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold transition hover:bg-blue-500"
                    >
                      Review Answer
                    </button>
                  </div>
                </article>
                  ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {selectedAnswer && (
          <section className="mt-8 rounded-2xl border border-blue-500/30 bg-slate-900 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-xl font-bold">
                Review Student Answer
              </h2>

              <button
                type="button"
                onClick={() => {
                  setSelectedAnswer(null);
                  setSuggestion(null);
                  setAwardedMarks("");
                  setExaminerFeedback("");
                  setImageAnnotations([]);
                }}
                className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10"
              >
                Close
              </button>
            </div>

            <div className="mt-6 space-y-5">
              <div>
                <p className="text-sm font-semibold text-slate-400">
                  Examination
                </p>
                <p className="mt-1">
                  {selectedAnswer.exam_title ||
                    `Examination #${selectedAnswer.exam_id}`}
                </p>
              </div>

              <div>
                <p className="text-sm font-semibold text-slate-400">
                  Question
                </p>
                <p className="mt-1 whitespace-pre-wrap">
                  {selectedAnswer.question_text}
                </p>
              </div>

              <div>
                <p className="text-sm font-semibold text-slate-400">
                  Student Answer
                </p>

                {selectedAnswer.answer_text && (
                  <div className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-800 p-4 text-slate-200">
                    {selectedAnswer.answer_text}
                  </div>
                )}
                {selectedAnswer.image_path && (
                  <div className="mt-3 rounded-lg bg-slate-800 p-4">
                    {imagePreviewUrl ? (
                      <div className="relative inline-block max-w-full">
                        <img
                          src={imagePreviewUrl}
                          alt="Uploaded handwritten examination answer"
                          className="max-h-[32rem] w-full rounded-lg object-contain"
                        />
                        {imageAnnotations.map((annotation, index) => (
                          <div
                            key={index}
                            title={annotation.text}
                            className={annotation.annotation_type === "highlight"
                              ? "pointer-events-none absolute border-2 border-amber-400 bg-amber-300/10"
                              : "pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-red-400 bg-red-500/30 px-2 py-1 text-[10px] text-white"}
                            style={{
                              left: `${annotation.x}%`,
                              top: `${annotation.y}%`,
                              width: annotation.annotation_type === "highlight" ? `${annotation.width}%` : "auto",
                              height: annotation.annotation_type === "highlight" ? `${annotation.height}%` : "auto",
                            }}
                          >
                            {annotation.annotation_type === "comment" ? index + 1 : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-400">Loading uploaded answer image...</p>
                    )}
                  </div>
                )}
                {!selectedAnswer.answer_text && !selectedAnswer.image_path && (
                  <p className="mt-2 text-slate-400">
                    No text or image answer was submitted.
                  </p>
                )}
              </div>

              <div className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
                <p className="text-sm text-slate-400">
                  Maximum marks
                </p>

                <p className="mt-1 text-2xl font-bold">
                  {selectedAnswer.marks}
                </p>
              </div>

              {selectedAnswer.question_type === "short_answer" ||
              selectedAnswer.question_type === "long_answer" ? (
                <div>
                  <button
                    type="button"
                    onClick={requestAISuggestion}
                    disabled={suggestionLoading}
                    className="rounded-lg border border-purple-400/40 bg-purple-500/10 px-5 py-3 font-semibold text-purple-300 transition hover:bg-purple-500/20 disabled:opacity-50"
                  >
                    {suggestionLoading
                      ? "Generating AI Suggestion..."
                      : suggestion
                        ? "Regenerate AI Grading Suggestion"
                        : "Get AI Grading Suggestion"}
                  </button>

                  <p className="mt-2 text-xs text-slate-500">
                    AI suggestions are advisory. The examiner must decide
                    and save the final marks.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-slate-400">
                  Handwritten image answers are reviewed manually by an examiner.
                </p>
              )}

              {suggestion && (
                <div className="space-y-4 rounded-xl border border-purple-400/30 bg-purple-500/5 p-5">
                  <h3 className="font-semibold text-purple-300">
                    AI Grading Suggestion
                  </h3>

                  <div>
                    <p className="text-sm text-slate-400">
                      Suggested marks
                    </p>
                    <p className="mt-1 text-2xl font-bold">
                      {suggestion.suggested_marks} / {selectedAnswer.marks}
                    </p>
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-slate-300">
                      Justification
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">
                      {suggestion.justification}
                    </p>
                  </div>

                  <div>
                    <p className="font-semibold text-green-300">
                      Matched points
                    </p>

                    {suggestion.matched_points.length ? (
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                        {suggestion.matched_points.map((point, index) => (
                          <li key={index}>{point}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-sm text-slate-400">
                        No matched points identified.
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="font-semibold text-amber-300">
                      Missed points
                    </p>

                    {suggestion.missed_points.length ? (
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                        {suggestion.missed_points.map((point, index) => (
                          <li key={index}>{point}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-sm text-slate-400">
                        No missed points identified.
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div>
                <label
                  htmlFor="awardedMarks"
                  className="mb-2 block text-sm font-semibold"
                >
                  Final marks awarded by examiner
                </label>

                <input
                  id="awardedMarks"
                  type="number"
                  min="0"
                  max={selectedAnswer.marks}
                  step="0.01"
                  value={awardedMarks}
                  onChange={(event) =>
                    setAwardedMarks(event.target.value)
                  }
                  placeholder="Enter final marks"
                  className="w-full max-w-sm rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />

                <p className="mt-2 text-xs text-slate-500">
                  You can accept, modify, or ignore the AI suggestion.
                </p>
              </div>

              <div>
                <label
                  htmlFor="examinerFeedback"
                  className="mb-2 block text-sm font-semibold"
                >
                  Examiner feedback for the student
                </label>
                <textarea
                  id="examinerFeedback"
                  rows={4}
                  maxLength={5000}
                  value={examinerFeedback}
                  onChange={(event) => setExaminerFeedback(event.target.value)}
                  placeholder="Write feedback explaining the awarded marks..."
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm outline-none focus:border-blue-500"
                />
              </div>

              {selectedAnswer.question_type === "image_upload" && (
                <div className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
                  <h3 className="font-semibold">Image answer annotations</h3>
                  <p className="mt-1 text-xs text-slate-400">
                    Add a comment or highlight marker using percentage coordinates on the submitted answer image.
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <label className="text-sm">
                      Annotation type
                      <select
                        value={annotationType}
                        onChange={(event) => setAnnotationType(event.target.value as "highlight" | "comment")}
                        className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2"
                      >
                        <option value="comment">Text comment</option>
                        <option value="highlight">Highlight area</option>
                      </select>
                    </label>
                    <label className="text-sm">
                      X position (%)
                      <input type="number" min="0" max="100" value={annotationX} onChange={(event) => setAnnotationX(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2" />
                    </label>
                    <label className="text-sm">
                      Y position (%)
                      <input type="number" min="0" max="100" value={annotationY} onChange={(event) => setAnnotationY(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2" />
                    </label>
                    {annotationType === "highlight" && (
                      <>
                        <label className="text-sm">
                          Width (%)
                          <input type="number" min="0" max="100" value={annotationWidth} onChange={(event) => setAnnotationWidth(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2" />
                        </label>
                        <label className="text-sm">
                          Height (%)
                          <input type="number" min="0" max="100" value={annotationHeight} onChange={(event) => setAnnotationHeight(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2" />
                        </label>
                      </>
                    )}
                  </div>
                  <label className="mt-3 block text-sm">
                    Annotation text
                    <input
                      type="text"
                      maxLength={500}
                      value={annotationText}
                      onChange={(event) => setAnnotationText(event.target.value)}
                      placeholder="Explain this highlight or comment"
                      className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      const x = Number(annotationX);
                      const y = Number(annotationY);
                      const width = annotationType === "highlight" ? Number(annotationWidth) : 0;
                      const height = annotationType === "highlight" ? Number(annotationHeight) : 0;
                      if (
                        !annotationText.trim() ||
                        !Number.isFinite(x) || !Number.isFinite(y) ||
                        x < 0 || x > 100 || y < 0 || y > 100 ||
                        width < 0 || width > 100 || height < 0 || height > 100
                      ) {
                        setError("Enter valid annotation text and coordinates from 0 to 100.");
                        return;
                      }
                      setImageAnnotations((current) => [
                        ...current,
                        {
                          annotation_type: annotationType,
                          x,
                          y,
                          width,
                          height,
                          text: annotationText.trim(),
                        },
                      ]);
                      setAnnotationText("");
                      setError("");
                    }}
                    className="mt-4 rounded-lg border border-blue-400/30 px-4 py-2 text-sm font-semibold text-blue-300 hover:bg-blue-500/10"
                  >
                    Add annotation
                  </button>
                  {imageAnnotations.length > 0 && (
                    <ul className="mt-4 space-y-2">
                      {imageAnnotations.map((annotation, index) => (
                        <li key={index} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-900 p-3 text-sm">
                          <span className="text-slate-300">
                            <strong className="capitalize">{annotation.annotation_type}</strong>
                            {" · "}({annotation.x}%, {annotation.y}%): {annotation.text}
                          </span>
                          <button
                            type="button"
                            onClick={() => setImageAnnotations((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                            className="text-xs text-red-300 hover:text-red-200"
                          >
                            Remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <button
                type="button"
                onClick={saveFinalMarks}
                disabled={saving}
                className="rounded-lg bg-green-600 px-6 py-3 font-semibold transition hover:bg-green-500 disabled:opacity-50"
              >
                {saving ? "Saving Marks..." : "Save Final Marks"}
              </button>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

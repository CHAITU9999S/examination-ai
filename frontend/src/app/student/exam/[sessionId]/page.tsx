
"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import WebcamPreview from "@/components/WebcamPreview";
import FaceProctoring from "@/components/FaceProctoring";
import ImageUpload from "@/components/ImageUpload";
import { useProctoring } from "@/hooks/useProctoring";
import { useWebSocket } from "@/hooks/useWebSocket";
import proctoringService from "@/services/proctoringService";
import { useParams, useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ExamOption {
  id: number;
  option_text: string;
}

interface ExamQuestion {
  id: number;
  question_text: string;
  question_type: string;
  marks: number;
  options?: ExamOption[];
}

interface ExamPaper {
  session_id: number;
  exam_id?: number;
  exam_title?: string;
  duration_minutes?: number;
  questions: ExamQuestion[];
  proctoring_enabled?: boolean;
  gaze_tracking_sensitivity?: number | null;
  max_tab_switch_warnings?: number | null;
}

interface SavedAnswer {
  answer_text: string;
}

export default function StudentExamPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();

  const sessionId = String(params.sessionId || "");

  const [paper, setPaper] = useState<ExamPaper | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showSubmitConfirmation, setShowSubmitConfirmation] =
    useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [uploadedImageQuestionIds, setUploadedImageQuestionIds] = useState<number[]>([]);
  const [pendingImageFiles, setPendingImageFiles] = useState<Record<number, File>>({});
  const [imageUploading, setImageUploading] = useState(false);
  const [websocketStatus, setWebsocketStatus] = useState("disconnected");

  const answersRef = useRef<Record<number, string>>({});
  const submittedRef = useRef(false);
  const saveTimeoutsRef = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  const examTokenKey = `examguard_exam_token_${sessionId}`;
  const examIdKey = `examguard_exam_id_${sessionId}`;

  const getExamToken = useCallback(() => {
    return sessionStorage.getItem(examTokenKey);
  }, [examTokenKey]);

  const getHeaders = useCallback(() => {
    const token = getExamToken();

    if (!token) {
      router.replace("/student/exams");
      return null;
    }

    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, [getExamToken, router]);

  const handleProctoringEvent = useCallback((event: {
    event_type: "tab_switch" | "window_blur" | "window_focus" | "face_not_detected" | "multiple_faces" | "gaze_away" | "webcam_error";
    description: string;
    gaze_data?: Record<string, unknown> | null;
  }) => {
    if (!Number.isInteger(Number(sessionId)) || Number(sessionId) <= 0) return;
    void proctoringService.submitEvent(Number(sessionId), event).catch((requestError) => {
      setError(requestError instanceof Error ? requestError.message : "Unable to record a proctoring event.");
    });
  }, [sessionId]);

  const proctoring = useProctoring({
    enabled: Boolean(paper?.proctoring_enabled),
    onEvent: handleProctoringEvent,
    maxTabWarnings: paper?.max_tab_switch_warnings ?? 3,
    duplicateEventCooldownMs: 4000,
  });

  const handleCameraStream = useCallback((stream: MediaStream | null) => {
    setCameraStream(stream);
  }, []);

  const handleCameraStatus = useCallback((status: "active" | "denied" | "unavailable" | "error") => {
    if (status !== "active") {
      proctoring.reportWebcamError(`Camera status: ${status}.`);
    }
  }, [proctoring.reportWebcamError]);

  const handleImageUpload = useCallback(async (questionId: number, file: File) => {
    const token = getExamToken();
    if (!token) return;
    const formData = new FormData();
    formData.append("question_id", String(questionId));
    formData.append("file", file);
    setImageUploading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/answers/${sessionId}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to upload answer image.");
      setUploadedImageQuestionIds((current) =>
        current.includes(questionId) ? current : [...current, questionId]
      );
      setPendingImageFiles((current) => {
        const next = { ...current };
        delete next[questionId];
        return next;
      });
      setMessage(data.ocr_completed
        ? "Image uploaded and text extracted for examiner review."
        : "Image uploaded. OCR is unavailable; examiner review is required.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Unable to upload answer image.");
    } finally {
      setImageUploading(false);
    }
  }, [getExamToken, sessionId]);

  const loadPaper = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const examId = sessionStorage.getItem(examIdKey);
      if (!examId || !/^\\d+$/.test(examId)) {
        throw new Error("Exam details are missing for this session. Please return to the exam list and start again.");
      }

      const response = await fetch(
        `${API_URL}/exam-sessions/paper/${examId}`,
        {
          method: "GET",
          headers,
          cache: "no-store",
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to load examination paper."
        );
      }

      const questions = Array.isArray(data)
        ? data
        : data.questions;

      if (!Array.isArray(questions)) {
        throw new Error("Invalid examination paper received.");
      }

      const normalizedPaper: ExamPaper = {
        ...data,
        session_id: Number(data.session_id || sessionId),
        questions,
      };

      setPaper(normalizedPaper);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load examination paper."
      );
    } finally {
      setLoading(false);
    }
  }, [examIdKey, getHeaders, sessionId]);

  const loadRemainingTime = useCallback(async () => {
    const headers = getHeaders();
    if (!headers) return;

    try {
      const response = await fetch(
        `${API_URL}/exam-sessions/time/${sessionId}`,
        {
          method: "GET",
          headers,
          cache: "no-store",
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to retrieve examination time."
        );
      }

      const seconds = Number(
        data.remaining_seconds ??
        data.remaining_time_seconds ??
        data.remaining_time
      );

      if (!Number.isFinite(seconds) || seconds < 0) {
        throw new Error("Invalid remaining-time response.");
      }

      setRemainingSeconds(Math.floor(seconds));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to retrieve remaining time."
      );
    }
  }, [getHeaders, sessionId]);

  const saveAnswer = useCallback(async (
    questionId: number,
    answerText: string
  ) => {
    const headers = getHeaders();
    if (!headers) return false;

    setSaving(true);

    try {
      const clearingAnswer = answerText.trim().length === 0;
      const response = await fetch(
        clearingAnswer
          ? `${API_URL}/answers/${sessionId}/${questionId}`
          : `${API_URL}/answers/${sessionId}`,
        {
          method: clearingAnswer ? "DELETE" : "POST",
          headers,
          ...(clearingAnswer ? {} : {
            body: JSON.stringify({
              question_id: questionId,
              answer_text: answerText,
            }),
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Unable to save answer.");
      }

      setMessage("Answer saved.");
      setError("");
      return true;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to save answer."
      );
      throw err;
    } finally {
      setSaving(false);
    }
  }, [getHeaders, sessionId]);


  const submitExam = useCallback(async (automatic = false) => {
    if (submittedRef.current || submitting) return;

    submittedRef.current = true;
    setSubmitting(true);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();

      if (!headers) {
        submittedRef.current = false;
        return;
      }

      Object.values(saveTimeoutsRef.current).forEach(clearTimeout);
      saveTimeoutsRef.current = {};

      // Flush every written answer before submission. If the server has
      // already expired the session, automatic submission must still proceed;
      // the backend expiry workflow remains authoritative in that case.
      const pendingSaves = Object.entries(answersRef.current)
        .filter(([questionId]) =>
          paper?.questions.find((question) => question.id === Number(questionId))?.question_type !== "image_upload"
        )
        .map(([questionId, answerText]) =>
          saveAnswer(Number(questionId), answerText)
        );

      const saveResults = await Promise.allSettled(pendingSaves);
      const saveFailed = saveResults.some(
        (result) =>
          result.status === "rejected" ||
          (result.status === "fulfilled" && result.value === false)
      );
      if (saveFailed && !automatic) {
        throw new Error("One or more answers could not be saved. Please retry before submitting.");
      }

      const response = await fetch(
        `${API_URL}/exam-sessions/submit/${sessionId}`,
        {
          method: "POST",
          headers,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to submit examination."
        );
      }

      sessionStorage.removeItem(examTokenKey);
      sessionStorage.removeItem(examIdKey);
      sessionStorage.removeItem("examguard_active_exam_session");

      setMessage(
        automatic
          ? "Your examination time has ended. The examination was submitted."
          : "Your examination was submitted successfully."
      );

      router.replace("/student/dashboard");
    } catch (err) {
      submittedRef.current = false;

      setError(
        err instanceof Error
          ? err.message
          : "Unable to submit examination."
      );
    } finally {
      setSubmitting(false);
    }
  }, [
    examTokenKey,
    examIdKey,
    getHeaders,
    router,
    sessionId,
    submitting,
    saveAnswer,
    paper,
    remainingSeconds,
  ]);

  function updateAnswer(questionId: number, answerText: string) {
    const updated = {
      ...answersRef.current,
      [questionId]: answerText,
    };

    answersRef.current = updated;
    setAnswers(updated);
    setMessage("");

    const existingTimeout = saveTimeoutsRef.current[questionId];
    if (existingTimeout) {
      clearTimeout(existingTimeout);
    }

    saveTimeoutsRef.current[questionId] = setTimeout(() => {
      delete saveTimeoutsRef.current[questionId];
      void saveAnswer(questionId, answerText).catch(() => {
        // The visible error state is set by saveAnswer.
      });
    }, 700);
  }

  useEffect(() => {
    if (!sessionId || !/^\d+$/.test(sessionId)) {
      router.replace("/student/exams");
      return;
    }

    loadPaper();
    loadRemainingTime();

    const token = sessionStorage.getItem(examTokenKey);
    if (token) {
      fetch(`${API_URL}/answers/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      })
        .then(async (response) => {
          if (!response.ok) return;
          const data = await response.json();
          const saved = Array.isArray(data.answers) ? data.answers : [];
          const restored: Record<number, string> = {};
          const restoredImages: number[] = [];
          for (const answer of saved) {
            if (!answer || !Number.isInteger(answer.question_id)) continue;
            if (typeof answer.answer_text === "string" && answer.answer_text.length > 0) {
              restored[answer.question_id] = answer.answer_text;
            }
            if (typeof answer.image_path === "string" && answer.image_path.length > 0) {
              restoredImages.push(answer.question_id);
            }
          }
          setUploadedImageQuestionIds(restoredImages);
          answersRef.current = restored;
          setAnswers(restored);
        })
        .catch(() => setError("Some previously saved answers could not be restored."));
    }

    const timeInterval = setInterval(() => {
      loadRemainingTime();
    }, 15000);

    return () => {
      clearInterval(timeInterval);

      Object.values(saveTimeoutsRef.current).forEach(clearTimeout);
      saveTimeoutsRef.current = {};
    };
  }, [examTokenKey, loadPaper, loadRemainingTime, router, sessionId]);

  useEffect(() => {
    if (remainingSeconds === null || remainingSeconds <= 0) {
      return;
    }

    const timer = setInterval(() => {
      setRemainingSeconds((previous) => {
        if (previous === null) return null;

        return Math.max(0, previous - 1);
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [remainingSeconds === null || remainingSeconds <= 0]);

  useEffect(() => {
    if (remainingSeconds === 0 && !submittedRef.current) {
      submitExam(true);
    }
  }, [remainingSeconds, submitExam]);

  const heartbeatToken = typeof window !== "undefined"
    ? sessionStorage.getItem(examTokenKey)
    : null;
  const heartbeatUrl = paper?.proctoring_enabled && heartbeatToken
    ? `${API_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:")}/exam-sessions/${sessionId}/proctoring/heartbeat?token=${encodeURIComponent(heartbeatToken)}`
    : null;

  const heartbeat = useWebSocket({
    url: heartbeatUrl,
    enabled: Boolean(heartbeatUrl && paper?.proctoring_enabled),
    heartbeatIntervalMs: 10000,
    reconnectIntervalMs: 3000,
    maxReconnectAttempts: 10,
    onMessage: (message) => {
      if (
        typeof message === "object" &&
        message !== null &&
        "type" in message &&
        message.type === "session_expired"
      ) {
        setRemainingSeconds(0);
        setError("The examination session has expired. Submitting your saved answers.");
      }
    },
  });

  useEffect(() => {
    setWebsocketStatus(heartbeat.status);
  }, [heartbeat.status]);

  function formatTime(seconds: number | null) {
    if (seconds === null) return "--:--";

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remaining = seconds % 60;

    if (hours > 0) {
      return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
    }

    return `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
  }

  function renderAnswerInput(question: ExamQuestion) {
    const currentAnswer = answers[question.id] || "";

    if (question.question_type === "MCQ") {
      return (
        <div className="mt-5 space-y-3">
          {(question.options || []).map((option) => (
            <label
              key={option.id}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-white/10 bg-slate-800 p-4 transition hover:border-blue-500"
            >
              <input
                type="radio"
                name={`question-${question.id}`}
                checked={currentAnswer === String(option.id)}
                onChange={() =>
                  updateAnswer(question.id, String(option.id))
                }
                className="h-4 w-4"
              />

              <span className="text-sm text-slate-200">
                {option.option_text}
              </span>
            </label>
          ))}
        </div>
      );
    }

    if (question.question_type === "multi_select") {
      let selectedIds: number[] = [];
      try {
        const parsed = currentAnswer ? JSON.parse(currentAnswer) : [];
        selectedIds = Array.isArray(parsed) ? parsed.filter((id): id is number => Number.isInteger(id)) : [];
      } catch {
        selectedIds = [];
      }

      return (
        <div className="mt-5 space-y-3">
          {(question.options || []).map((option) => (
            <label
              key={option.id}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-white/10 bg-slate-800 p-4 transition hover:border-blue-500"
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(option.id)}
                onChange={(event) => {
                  const updated = event.target.checked
                    ? [...selectedIds, option.id]
                    : selectedIds.filter((id) => id !== option.id);

                  updateAnswer(
                    question.id,
                    JSON.stringify(updated)
                  );
                }}
                className="h-4 w-4"
              />

              <span className="text-sm text-slate-200">
                {option.option_text}
              </span>
            </label>
          ))}
        </div>
      );
    }

    if (
      question.question_type === "short_answer" ||
      question.question_type === "long_answer"
    ) {
      const wordCount = currentAnswer.trim()
        ? currentAnswer.trim().split(/\s+/).length
        : 0;
      const wordLimit = question.question_type === "short_answer" ? 1000 : 10000;

      return (
        <div className="mt-5">
          <textarea
            value={currentAnswer}
            onChange={(event) =>
              updateAnswer(question.id, event.target.value)
            }
            rows={question.question_type === "short_answer" ? 4 : 9}
            maxLength={50000}
            placeholder="Type your answer here..."
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm outline-none focus:border-blue-500"
          />
          <p className={`mt-2 text-right text-xs ${wordCount > wordLimit ? "text-red-400" : "text-slate-400"}`} aria-live="polite">
            {wordCount} / {wordLimit} words
          </p>
        </div>
      );
    }

    if (question.question_type === "image_upload") {
      return (
        <div className="mt-5 space-y-3">
          {uploadedImageQuestionIds.includes(question.id) ? (
            <p role="status" className="rounded-lg border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-300">
              Answer image uploaded and saved for examiner review.
            </p>
          ) : (
            <ImageUpload
              onFileSelect={(file) => {
                setPendingImageFiles((current) => {
                  const next = { ...current };
                  if (file) next[question.id] = file;
                  else delete next[question.id];
                  return next;
                });
              }}
              disabled={imageUploading || submitting}
            />
          )}
          {pendingImageFiles[question.id] && (
            <button
              type="button"
              onClick={() => void handleImageUpload(question.id, pendingImageFiles[question.id])}
              disabled={imageUploading || submitting}
              className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold disabled:opacity-50"
            >
              Upload Answer Image
            </button>
          )}
          {imageUploading && (
            <p role="status" className="text-sm text-blue-300">Uploading image and processing OCR...</p>
          )}
        </div>
      );
    }

    return (
      <p className="mt-4 text-sm text-red-300">
        Unsupported question type.
      </p>
    );
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <p className="text-slate-400">Loading examination...</p>
      </main>
    );
  }

  if (!paper) {
    return (
      <main className="min-h-screen bg-slate-950 px-6 py-16 text-white">
        <div className="mx-auto max-w-xl rounded-xl border border-red-500/30 bg-slate-900 p-6">
          <h1 className="text-xl font-bold">
            Unable to open examination
          </h1>

          <p className="mt-3 text-sm text-red-300">
            {error || "Examination paper could not be loaded."}
          </p>

          <button
            type="button"
            onClick={loadPaper}
            className="mt-5 rounded-lg bg-blue-600 px-5 py-3 font-semibold"
          >
            Try Again
          </button>
        </div>
      </main>
    );
  }

  const currentQuestion = paper.questions[currentIndex];

  const answeredCount = paper.questions.filter((question) => {
    return Boolean(answers[question.id]?.trim()) ||
      uploadedImageQuestionIds.includes(question.id);
  }).length;

  return (
    <main
      className="min-h-screen bg-slate-950 text-white"
      onContextMenu={(event) => event.preventDefault()}
      onCopy={(event) => event.preventDefault()}
      onCut={(event) => event.preventDefault()}
      onPaste={(event) => event.preventDefault()}
    >
      <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <h1 className="text-lg font-bold">
              {paper.exam_title || "Online Examination"}
            </h1>

            <p className="text-xs text-slate-400">
              Session #{sessionId}
            </p>
          </div>

          <div className="text-right">
            <p className="text-xs text-slate-400">
              Time Remaining
            </p>

            <p
              className={`text-xl font-bold tabular-nums ${
                remainingSeconds !== null && remainingSeconds <= 60
                  ? "text-red-400"
                  : remainingSeconds !== null && remainingSeconds <= 300
                    ? "text-amber-400"
                    : "text-green-400"
              }`}
            >
              {formatTime(remainingSeconds)}
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[1fr_280px]">
        <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          {error && (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300"
            >
              {error}
            </div>
          )}

          {message && (
            <p
              role="status"
              className="mb-5 text-xs text-green-400"
            >
              {message}
            </p>
          )}

          {currentQuestion ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-slate-400">
                  Question {currentIndex + 1} of {paper.questions.length}
                </p>

                <p className="text-sm text-slate-400">
                  {currentQuestion.marks} marks
                </p>
              </div>

              <div className="mt-6">
                <h2 className="whitespace-pre-wrap text-lg font-semibold leading-8">
                  {currentQuestion.question_text}
                </h2>

                {renderAnswerInput(currentQuestion)}
              </div>

              <div className="mt-8 flex flex-wrap justify-between gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setCurrentIndex((index) => Math.max(0, index - 1))
                  }
                  disabled={currentIndex === 0}
                  className="rounded-lg border border-white/20 px-5 py-3 text-sm disabled:opacity-40"
                >
                  Previous
                </button>

                {currentIndex < paper.questions.length - 1 ? (
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentIndex((index) =>
                        Math.min(paper.questions.length - 1, index + 1)
                      )
                    }
                    className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold hover:bg-blue-500"
                  >
                    Next Question
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowSubmitConfirmation(true)}
                    disabled={submitting}
                    className="rounded-lg bg-green-600 px-5 py-3 text-sm font-semibold hover:bg-green-500 disabled:opacity-50"
                  >
                    Submit Examination
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className="py-10 text-center text-slate-400">
              No questions are available in this examination.
            </p>
          )}
        </section>

        <aside className="h-fit rounded-2xl border border-white/10 bg-slate-900 p-5">
          <h2 className="font-bold">Question Navigation</h2>

          <p className="mt-2 text-sm text-slate-400">
            Answered: {answeredCount} / {paper.questions.length}
          </p>

          <div className="mt-5 grid grid-cols-5 gap-2">
            {paper.questions.map((question, index) => {
              const answered = Boolean(
                answers[question.id]?.trim()
              ) || uploadedImageQuestionIds.includes(question.id);

              return (
                <button
                  key={question.id}
                  type="button"
                  onClick={() => setCurrentIndex(index)}
                  aria-label={`Go to question ${index + 1}`}
                  className={`rounded-lg py-3 text-sm font-semibold ${
                    currentIndex === index
                      ? "bg-blue-600 text-white"
                      : answered
                        ? "bg-green-500/20 text-green-300"
                        : "bg-slate-800 text-slate-300"
                  }`}
                >
                  {index + 1}
                </button>
              );
            })}
          </div>

          <div className="mt-6 space-y-2 text-xs text-slate-400">
            <p>
              <span className="mr-2 inline-block h-3 w-3 rounded bg-blue-600" />
              Current question
            </p>

            <p>
              <span className="mr-2 inline-block h-3 w-3 rounded bg-green-500/60" />
              Answered
            </p>

            <p>
              <span className="mr-2 inline-block h-3 w-3 rounded bg-slate-700" />
              Not answered
            </p>
          </div>

          {paper.proctoring_enabled && (
            <div className="mt-6 space-y-3 border-t border-white/10 pt-5">
              <h3 className="font-semibold">Automated Proctoring</h3>
              <WebcamPreview
                enabled
                onStreamReady={handleCameraStream}
                onCameraStatusChange={handleCameraStatus}
              />
              <FaceProctoring
                stream={cameraStream}
                enabled
                sensitivity={paper.gaze_tracking_sensitivity ?? 0.5}
                onFaceMissing={proctoring.reportFaceNotDetected}
                onMultipleFaces={proctoring.reportMultipleFaces}
                onGazeAway={proctoring.reportGazeAway}
                onDetectorError={proctoring.reportWebcamError}
              />
              <p className="text-xs text-slate-400">
                Monitoring: {proctoring.isMonitoring ? "Active" : "Starting"} ·
                Heartbeat: {websocketStatus}
              </p>
              {proctoring.isAutoFlagged && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200"
                >
                  The configured tab-switch warning limit has been reached.
                  This session has been flagged for examiner review.
                </div>
              )}
              <p className="text-xs text-amber-300">
                Proctoring checks are automated indicators for examiner review, not proof of misconduct.
              </p>
            </div>
          )}

          <div className="mt-6 border-t border-white/10 pt-5">
            <p className="text-sm text-slate-400">
              Answer saving
            </p>

            <p className="mt-1 text-sm">
              {saving ? "Saving..." : "Automatic saving enabled"}
            </p>

            <button
              type="button"
              onClick={() => setShowSubmitConfirmation(true)}
              disabled={submitting}
              className="mt-5 w-full rounded-lg bg-green-600 px-4 py-3 text-sm font-semibold hover:bg-green-500 disabled:opacity-50"
            >
              Submit Examination
            </button>
          </div>
        </aside>
      </div>

      {showSubmitConfirmation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900 p-6">
            <h2 className="text-xl font-bold">
              Submit Examination?
            </h2>

            <p className="mt-3 text-sm text-slate-400">
              You have answered {answeredCount} out of{" "}
              {paper.questions.length} questions. Unanswered questions
              will remain unanswered. You cannot continue after submission.
            </p>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowSubmitConfirmation(false)}
                disabled={submitting}
                className="rounded-lg border border-white/20 px-4 py-2 text-sm"
              >
                Continue Exam
              </button>

              <button
                type="button"
                onClick={() => submitExam(false)}
                disabled={submitting}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Confirm Submit"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

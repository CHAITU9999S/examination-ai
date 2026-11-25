
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
  question_image_available?: boolean;
  question_time_limit_seconds?: number | null;
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
  is_paused?: boolean;
  current_question_index?: number;
  status?: string;
  prestart_stage?: string;
  face_captured?: boolean;
  exam_summary?: {
    exam_title: string; subject?: string | null; creator_name: string; student_name: string;
    student_email?: string | null; student_department?: string | null; total_questions: number;
    question_type_breakdown: Record<string, number>;
    marking_scheme: Array<{ question_type: string; difficulty: string; count: number; positive_marks_per_question: number; negative_marks_per_question: number }>;
    duration_minutes: number; maximum_marks: number;
    negative_marking_enabled: boolean; total_possible_negative_marks: number;
    proctoring_enabled: boolean; randomize_questions: boolean; instructions?: string[] | string;
  };
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
  const [questionRemainingSeconds, setQuestionRemainingSeconds] = useState<number | null>(null);
  const [questionTimerLocked, setQuestionTimerLocked] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [pauseBusy, setPauseBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setErrorState] = useState("");

  // A second device login invalidates this exam token. Clear this browser's
  // credentials and return to login as soon as the server reports replacement.
  const setError = useCallback((message: string) => {
    const normalizedMessage = message.toLowerCase();
    if (
      normalizedMessage.includes(
        "signed out because your account was used to sign in on another device"
      ) ||
      normalizedMessage.includes(
        "exam refresh token is invalid or has already been rotated"
      )
    ) {
      localStorage.removeItem("examguard_access_token");
      localStorage.removeItem("examguard_user");
      for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
        const key = sessionStorage.key(index);
        if (
          key &&
          (
            key.startsWith("examguard_exam_token_") ||
            key.startsWith("examguard_exam_refresh_") ||
            key.startsWith("examguard_exam_id_")
          )
        ) {
          sessionStorage.removeItem(key);
        }
      }
      router.replace("/login?reason=session_replaced");
      return;
    }
    setErrorState(message);
  }, [router]);
  const [message, setMessage] = useState("");
  const [showSubmitConfirmation, setShowSubmitConfirmation] =
    useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [examAccessToken, setExamAccessToken] = useState<string | null>(null);
  const [faceVerified, setFaceVerified] = useState(false);
  const [uploadedImageQuestionIds, setUploadedImageQuestionIds] = useState<number[]>([]);
  const [questionImageUrls, setQuestionImageUrls] = useState<Record<number, string>>({});
  const [pendingImageFiles, setPendingImageFiles] = useState<Record<number, File>>({});
  const [imageUploading, setImageUploading] = useState(false);
  const [websocketStatus, setWebsocketStatus] = useState("disconnected");
  const [prestartStage, setPrestartStage] = useState("face_capture");
  const [faceCaptured, setFaceCaptured] = useState(false);
  const [faceCaptureBusy, setFaceCaptureBusy] = useState(false);
  const [summarySecondsUntilContinue, setSummarySecondsUntilContinue] = useState(60);
  const [summarySecondsUntilAutoContinue, setSummarySecondsUntilAutoContinue] = useState(120);
  const [startWindowSecondsRemaining, setStartWindowSecondsRemaining] = useState<number | null>(null);
  const [showCameraPreview, setShowCameraPreview] = useState(true);
  const captureVideoRef = useRef<HTMLVideoElement | null>(null);

  const answersRef = useRef<Record<number, string>>({});
  const submittedRef = useRef(false);
  const saveTimeoutsRef = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  const refreshInFlightRef = useRef(false);
  const activePaperLoadedRef = useRef(false);

  const examTokenKey = `examguard_exam_token_${sessionId}`;
  const examRefreshTokenKey = `examguard_exam_refresh_${sessionId}`;
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

  const refreshExamAccessToken = useCallback(async () => {
    if (refreshInFlightRef.current) return;

    const refreshToken = sessionStorage.getItem(examRefreshTokenKey);
    if (!refreshToken) return;

    refreshInFlightRef.current = true;
    try {
      const response = await fetch(
        `${API_URL}/exam-sessions/refresh/${sessionId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
          cache: "no-store",
        }
      );
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Unable to renew the examination session token.");
      }
      if (
        typeof data.access_token !== "string" ||
        typeof data.refresh_token !== "string"
      ) {
        throw new Error("The server returned an invalid token refresh response.");
      }

      sessionStorage.setItem(examTokenKey, data.access_token);
      sessionStorage.setItem(examRefreshTokenKey, data.refresh_token);
      setExamAccessToken(data.access_token);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Unable to renew the examination session token."
      );
    } finally {
      refreshInFlightRef.current = false;
    }
  }, [examRefreshTokenKey, examTokenKey, sessionId, setError]);

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
    enabled: Boolean(paper?.proctoring_enabled && paper.status === "in_progress"),
    onEvent: handleProctoringEvent,
    maxTabWarnings: paper?.max_tab_switch_warnings ?? 3,
    duplicateEventCooldownMs: 4000,
  });

  const handleCameraStream = useCallback((stream: MediaStream | null) => {
    setCameraStream(stream);
    if (!stream) setFaceVerified(false);
  }, []);
  useEffect(() => {
    if (captureVideoRef.current && cameraStream) {
      captureVideoRef.current.srcObject = cameraStream;
      void captureVideoRef.current.play().catch(() => undefined);
    } else if (captureVideoRef.current) {
      captureVideoRef.current.srcObject = null;
    }
  }, [cameraStream]);


  const uploadFaceCapture = useCallback(async (photo: Blob) => {
    if (faceCaptured) return;
    const token = getExamToken();
    if (!token) return;
    setFaceCaptureBusy(true);
    setError("");
    try {
      const response = await fetch(API_URL + "/exam-sessions/face-capture/" + sessionId, {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "image/jpeg" },
        body: photo,
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to save the face capture.");
      setFaceCaptured(true);
      setPrestartStage("summary");
      setSummarySecondsUntilContinue(60);
      setSummarySecondsUntilAutoContinue(120);
      setPaper((current) => current ? { ...current, status: "not_started", prestart_stage: "summary", face_captured: true } : current);
      setMessage("Face capture saved. Your examination summary has started.");
    } catch (captureError) {
      setError(captureError instanceof Error ? captureError.message : "Unable to save the face capture. Please retry.");
    } finally {
      setFaceCaptureBusy(false);
    }
  }, [faceCaptured, getExamToken, sessionId, setError]);

  const handleFaceVerified = useCallback((photo: Blob) => {
    setFaceVerified(true);
    void uploadFaceCapture(photo);
  }, [uploadFaceCapture]);

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

      const response = await fetch(
        `${API_URL}/exam-sessions/paper/session/${sessionId}`,
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

      if (normalizedPaper.exam_id) sessionStorage.setItem(examIdKey, String(normalizedPaper.exam_id));
      setPaper(normalizedPaper);
      setPrestartStage(normalizedPaper.prestart_stage || "face_capture");
      setFaceCaptured(Boolean(normalizedPaper.face_captured));
      setFaceVerified(Boolean(normalizedPaper.face_captured));
      if (normalizedPaper.status === "in_progress") activePaperLoadedRef.current = true;
      setRemainingSeconds(normalizedPaper.remaining_seconds === null || normalizedPaper.remaining_seconds === undefined ? null : Math.max(0, Number(normalizedPaper.remaining_seconds)));

      const imageQuestions = questions.filter(
        (question: ExamQuestion) => String(question.question_type).toLowerCase() === "image_upload"
      );
      const savedImageQuestionIds = await Promise.all(
        imageQuestions.map(async (question: ExamQuestion) => {
          try {
            const answerResponse = await fetch(
              `${API_URL}/answers/${sessionId}/${question.id}`,
              { method: "GET", headers, cache: "no-store" }
            );
            if (!answerResponse.ok) return null;
            const savedAnswer = await answerResponse.json().catch(() => null);
            return savedAnswer?.image_path ? question.id : null;
          } catch {
            return null;
          }
        })
      );
      setUploadedImageQuestionIds(
        savedImageQuestionIds.filter((id): id is number => id !== null)
      );

      setCurrentIndex(Math.max(0, Math.min(
        Number(normalizedPaper.current_question_index || 0),
        Math.max(0, questions.length - 1)
      )));
      setIsPaused(Boolean(normalizedPaper.is_paused));
    } catch (err) {
      activePaperLoadedRef.current = false;
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load examination paper."
      );
    } finally {
      setLoading(false);
    }
  }, [examIdKey, getHeaders, sessionId]);

  useEffect(() => {
    if (!paper) return;

    let cancelled = false;
    const createdUrls: string[] = [];
    const token = getExamToken();

    if (!token) return;

    const imageQuestions = paper.questions.filter(
      (question) => question.question_image_available
    );

    Promise.all(
      imageQuestions.map(async (question) => {
        const response = await fetch(
          `${API_URL}/answers/${sessionId}/questions/${question.id}/image`,
          {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }
        );

        if (!response.ok) return null;

        const imageBlob = await response.blob();
        const imageUrl = URL.createObjectURL(imageBlob);
        createdUrls.push(imageUrl);
        return [question.id, imageUrl] as const;
      })
    )
      .then((results) => {
        if (cancelled) return;
        const nextUrls: Record<number, string> = {};
        for (const result of results) {
          if (result) nextUrls[result[0]] = result[1];
        }
        setQuestionImageUrls(nextUrls);
      })
      .catch(() => {
        if (!cancelled) setQuestionImageUrls({});
      });

    return () => {
      cancelled = true;
      createdUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [paper, getExamToken, sessionId]);

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

      if (data.status === "not_started") {
        setRemainingSeconds(null);
        setIsPaused(false);
        setPrestartStage(data.prestart_stage || prestartStage);
        return;
      }
      const seconds = Number(data.remaining_seconds ?? data.remaining_time_seconds ?? data.remaining_time);
      if (!Number.isFinite(seconds) || seconds < 0) {
        throw new Error("Invalid remaining-time response.");
      }

      setRemainingSeconds(Math.floor(seconds));
      setIsPaused(Boolean(data.is_paused));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to retrieve remaining time."
      );
    }
  }, [getHeaders, sessionId, prestartStage]);

  const loadPrestartStatus = useCallback(async () => {
    const headers = getHeaders();
    if (!headers) return null;
    try {
      const response = await fetch(API_URL + "/exam-sessions/prestart/" + sessionId, { headers, cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to check examination entry status.");
      setPrestartStage(data.stage || "in_progress");
      setFaceCaptured(Boolean(data.face_captured));
      if (data.face_captured) setFaceVerified(true);
      setSummarySecondsUntilContinue(Math.max(0, Number(data.summary_seconds_until_continue ?? 0)));
      setSummarySecondsUntilAutoContinue(Math.max(0, Number(data.summary_seconds_until_auto_continue ?? 0)));
      setStartWindowSecondsRemaining(data.start_window_seconds_remaining === null || data.start_window_seconds_remaining === undefined ? null : Math.max(0, Number(data.start_window_seconds_remaining)));
      if (data.status === "in_progress") {
        setRemainingSeconds(Math.max(0, Number(data.remaining_seconds ?? 0)));
        setPaper((current) => current ? { ...current, status: "in_progress" } : current);
        if (!activePaperLoadedRef.current) {
          activePaperLoadedRef.current = true;
          void loadPaper();
        }
      }
      return data.status || null;
    } catch (statusError) {
      setError(statusError instanceof Error ? statusError.message : "Unable to check examination entry status.");
      return null;
    }
  }, [getHeaders, loadPaper, sessionId, setError]);

  const continueAfterSummary = useCallback(async () => {
    const headers = getHeaders();
    if (!headers) return;
    try {
      const response = await fetch(API_URL + "/exam-sessions/summary/continue/" + sessionId, { method: "POST", headers, cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to continue from the examination summary.");
      setPrestartStage(data.stage || "start_window");
      setStartWindowSecondsRemaining(Math.max(0, Number(data.start_window_seconds_remaining ?? 0)));
      await loadPrestartStatus();
    } catch (continueError) {
      setError(continueError instanceof Error ? continueError.message : "Unable to continue.");
    }
  }, [getHeaders, loadPrestartStatus, sessionId, setError]);

  const confirmExamStart = useCallback(async () => {
    const headers = getHeaders();
    if (!headers) return;
    try {
      const response = await fetch(API_URL + "/exam-sessions/confirm-start/" + sessionId, { method: "POST", headers, cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to start the examination.");
      setPrestartStage("in_progress");
      setRemainingSeconds(Math.max(0, Number(data.remaining_seconds ?? 0)));
      await loadPaper();
      await loadRemainingTime();
      setMessage("The examination has started. Your timer is now running.");
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Unable to start the examination.");
    }
  }, [getHeaders, loadPaper, loadRemainingTime, sessionId, setError]);

  const retryFaceCapture = useCallback(async () => {
    const video = captureVideoRef.current;
    if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      setError("The webcam frame is not ready. Keep the camera connected and try again.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) { setError("Unable to capture a webcam photo on this device."); return; }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((photo) => {
      if (photo) void uploadFaceCapture(photo);
      else setError("Unable to create the webcam photo. Please retry.");
    }, "image/jpeg", 0.82);
  }, [setError, uploadFaceCapture]);

  const loadQuestionTimer = useCallback(async (questionId: number) => {
    const headers = getHeaders();
    if (!headers) return;
    try {
      const response = await fetch(
        `${API_URL}/exam-sessions/${sessionId}/question-timer/${questionId}`,
        { method: "GET", headers, cache: "no-store" }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to load question timer.");
      setQuestionRemainingSeconds(
        data.remaining_seconds === null || data.remaining_seconds === undefined
          ? null
          : Math.max(0, Number(data.remaining_seconds))
      );
      setQuestionTimerLocked(Boolean(data.is_locked));
    } catch (timerError) {
      setError(timerError instanceof Error ? timerError.message : "Unable to load question timer.");
    }
  }, [getHeaders, sessionId]);

  const togglePause = useCallback(async () => {
    if (pauseBusy) return;
    const headers = getHeaders();
    if (!headers) return;
    setPauseBusy(true);
    setError("");
    try {
      const action = isPaused ? "resume" : "pause";
      const response = await fetch(
        `${API_URL}/exam-sessions/${action}/${sessionId}`,
        { method: "POST", headers }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to change exam pause state.");
      setIsPaused(Boolean(data.is_paused));
      setRemainingSeconds(Number(data.remaining_seconds));
      setMessage(data.message || (data.is_paused ? "Exam paused." : "Exam resumed."));
    } catch (pauseError) {
      setError(pauseError instanceof Error ? pauseError.message : "Unable to change exam pause state.");
    } finally {
      setPauseBusy(false);
    }
  }, [getHeaders, isPaused, pauseBusy, sessionId]);

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
      const pendingSaves = (isPaused ? [] : Object.entries(answersRef.current))
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
      sessionStorage.removeItem(examRefreshTokenKey);
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
    examRefreshTokenKey,
    examIdKey,
    getHeaders,
    router,
    sessionId,
    submitting,
    saveAnswer,
    paper,
    remainingSeconds,
    isPaused,
  ]);

  function updateAnswer(questionId: number, answerText: string) {
    if (isPaused || questionTimerLocked) return;
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
    }, 300);
  }

  useEffect(() => {
    if (!sessionId || !/^\d+$/.test(sessionId)) {
      router.replace("/student/exams");
      return;
    }

    let cancelled = false;
    const initializeExam = async () => {
      const initialToken = sessionStorage.getItem(examTokenKey);
      if (!initialToken) {
        router.replace("/student/exams");
        return;
      }

      setExamAccessToken(initialToken);
      await refreshExamAccessToken();
      if (cancelled) return;

      const token = sessionStorage.getItem(examTokenKey);
      if (!token) {
        router.replace("/login?reason=session_replaced");
        return;
      }
      setExamAccessToken(token);

      await loadPaper();
      if (cancelled) return;
      const entryStatus = await loadPrestartStatus();
      if (cancelled || entryStatus !== "in_progress") return;
      if (!activePaperLoadedRef.current) await loadPaper();
      if (cancelled) return;
      await loadRemainingTime();
      if (cancelled) return;

      try {
        const response = await fetch(`${API_URL}/answers/${sessionId}`, {
          headers: { Authorization: `Bearer ${sessionStorage.getItem(examTokenKey) || token}` },
          cache: "no-store",
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Unable to restore saved answers.");
        }
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
        if (!cancelled) {
          setUploadedImageQuestionIds(restoredImages);
          answersRef.current = restored;
          setAnswers(restored);
        }
      } catch (restoreError) {
        if (!cancelled) {
          setError(restoreError instanceof Error ? restoreError.message : "Some previously saved answers could not be restored.");
        }
      }
    };

    void initializeExam();

    const timeInterval = setInterval(() => { loadRemainingTime(); }, 15000);
    const prestartInterval = setInterval(() => {
      if (!activePaperLoadedRef.current) void loadPrestartStatus();
    }, 1000);
    const tokenRefreshInterval = setInterval(() => {
      void refreshExamAccessToken();
    }, 4 * 60 * 1000);
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") void refreshExamAccessToken();
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      cancelled = true;
      clearInterval(timeInterval);
      clearInterval(prestartInterval);
      clearInterval(tokenRefreshInterval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      Object.values(saveTimeoutsRef.current).forEach(clearTimeout);
      saveTimeoutsRef.current = {};
    };
  }, [examTokenKey, loadPaper, loadPrestartStatus, loadRemainingTime, refreshExamAccessToken, router, sessionId]);

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

  const currentQuestionId = paper?.questions[currentIndex]?.id ?? null;

  useEffect(() => {
    if (!paper || !examAccessToken || isPaused) return;
    const headers = getHeaders();
    if (!headers) return;
    fetch(`${API_URL}/exam-sessions/progress/${sessionId}`, {
      method: "PUT",
      headers,
      body: JSON.stringify({ current_question_index: currentIndex }),
      cache: "no-store",
    }).catch(() => {
      setError("The current question position could not be saved. Your answers remain saved separately.");
    });
  }, [currentIndex, paper, examAccessToken, isPaused, getHeaders, sessionId]);

  useEffect(() => {
    if (!currentQuestionId || !examAccessToken || isPaused) return;
    setQuestionRemainingSeconds(null);
    setQuestionTimerLocked(false);
    void loadQuestionTimer(currentQuestionId);
  }, [currentQuestionId, examAccessToken, isPaused, loadQuestionTimer]);

  useEffect(() => {
    if (questionRemainingSeconds === null || questionRemainingSeconds <= 0) return;
    const timer = setInterval(() => {
      setQuestionRemainingSeconds((previous) =>
        previous === null ? null : Math.max(0, previous - 1)
      );
    }, 1000);
    return () => clearInterval(timer);
  }, [questionRemainingSeconds === null || questionRemainingSeconds <= 0]);

  useEffect(() => {
    if (questionRemainingSeconds !== 0 || questionTimerLocked || !currentQuestionId || isPaused) return;
    setQuestionTimerLocked(true);
    void loadQuestionTimer(currentQuestionId);
  }, [questionRemainingSeconds, questionTimerLocked, currentQuestionId, isPaused, loadQuestionTimer]);

  useEffect(() => {
    if (!questionTimerLocked || isPaused || !paper) return;
    if (currentIndex < paper.questions.length - 1) {
      setCurrentIndex((index) => Math.min(paper.questions.length - 1, index + 1));
    }
  }, [questionTimerLocked, isPaused, paper, currentIndex]);

  const heartbeatToken = examAccessToken;
  const heartbeatUrl = paper?.proctoring_enabled && paper.status === "in_progress" && heartbeatToken
    ? `${API_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:")}/exam-sessions/${sessionId}/proctoring/heartbeat?token=${encodeURIComponent(heartbeatToken)}`
    : null;

  const heartbeat = useWebSocket({
    url: heartbeatUrl,
    enabled: Boolean(heartbeatUrl && paper?.proctoring_enabled && paper.status === "in_progress"),
    heartbeatIntervalMs: 10000,
    heartbeatPayload: () => ({
      event_counts: proctoring.events.reduce<Record<string, number>>((counts, event) => {
        counts[event.event_type] = (counts[event.event_type] || 0) + 1;
        return counts;
      }, {}),
      total_event_count: proctoring.events.length,
      tab_switch_count: proctoring.tabSwitchCount,
      auto_flagged: proctoring.isAutoFlagged,
    }),
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
      } else if (
        typeof message === "object" &&
        message !== null &&
        "type" in message &&
        message.type === "token_expired"
      ) {
        void refreshExamAccessToken();
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
      // The API stores MCQ selections as a one-item JSON array. Normalize
      // that persisted value so the selected radio option remains checked
      // after refresh, while keeping the in-memory value as a plain ID.
      let selectedMcqOption = currentAnswer;
      try {
        const parsed = JSON.parse(currentAnswer);
        if (Array.isArray(parsed) && parsed.length === 1) {
          selectedMcqOption = String(parsed[0]);
        }
      } catch {
        // Fresh answers are stored as a plain option ID in component state.
      }
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
                checked={selectedMcqOption === String(option.id)}
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
            className="w-full select-text rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm outline-none focus:border-blue-500"
          />
          <p className={`mt-2 text-right text-xs ${wordCount > wordLimit ? "text-red-400" : "text-slate-400"}`} aria-live="polite">
            {wordCount} / {wordLimit} words
          </p>
        </div>
      );
    }

    if (String(question.question_type).toLowerCase() === "image_upload") {
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


  if (paper.status === "not_started") {
    const summary = paper.exam_summary;
    const instructions = Array.isArray(summary?.instructions) ? summary.instructions : summary?.instructions ? [summary.instructions] : [];
    return (
      <main className="min-h-screen bg-slate-950 px-4 py-8 text-white">
        <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_300px]">
          <section className="rounded-2xl border border-white/10 bg-slate-900 p-6 sm:p-8">
            <p className="text-sm font-semibold uppercase tracking-wide text-blue-300">Examination entry</p>
            <h1 className="mt-2 text-2xl font-bold">{paper.exam_title || "Online Examination"}</h1>
            {prestartStage === "face_capture" && (
              <div className="mt-8 space-y-4">
                <h2 className="text-xl font-semibold">Face capture</h2>
                <p className="text-sm leading-6 text-slate-300">Keep only your face visible and look toward the camera. When one face is continuously detected, the system automatically captures a still photo for this examination session.</p>
                <p className="text-sm text-amber-300">{faceCaptureBusy ? "Saving your face photo..." : faceVerified ? "One face detected. Saving your photo..." : cameraStream ? "Waiting for one clear face..." : "Allow camera access to continue."}</p>
                {faceVerified && !faceCaptured && !faceCaptureBusy && <button type="button" onClick={retryFaceCapture} className="rounded-lg border border-blue-400 px-4 py-2 text-sm font-semibold text-blue-200">Retry photo capture</button>}
              </div>
            )}
            {prestartStage === "summary" && summary && (
              <div className="mt-8 space-y-5">
                <h2 className="text-xl font-semibold">Examination summary</h2>
                <p className="text-sm leading-6 text-slate-300">Review the details below. This summary must remain on screen for at least 60 seconds. You may continue after the first minute or wait until the full two minutes finish.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    ["Subject", summary.subject || "Not specified"], ["Created by", summary.creator_name],
                    ["Student", summary.student_name], ["Student email", summary.student_email || "—"],
                    ["Department", summary.student_department || "—"], ["Total questions", String(summary.total_questions)],
                    ["Duration", summary.duration_minutes + " minutes"], ["Maximum marks", String(summary.maximum_marks)],
                    ["Negative marking", summary.negative_marking_enabled ? "Enabled" : "Disabled"],
                    ["Possible negative marks", String(summary.total_possible_negative_marks)],
                    ["AI proctoring", summary.proctoring_enabled ? "Enabled" : "Disabled"],
                    ["Question order", summary.randomize_questions ? "Randomized" : "Configured order"],
                  ].map(([label, value]) => <div key={label} className="rounded-lg border border-white/10 bg-slate-800 p-3"><p className="text-xs text-slate-400">{label}</p><p className="mt-1 font-semibold">{value}</p></div>)}
                </div>
                <div className="rounded-lg border border-white/10 bg-slate-800 p-4">
                  <h3 className="font-semibold">Positive and negative marking</h3>
                  <div className="mt-3 space-y-2 text-sm text-slate-300">
                    {(summary.marking_scheme || []).map((item, index) => (
                      <div key={index} className="flex flex-wrap justify-between gap-2 border-b border-white/5 pb-2 last:border-0">
                        <span>{item.question_type} · {item.difficulty} · {item.count} question(s)</span>
                        <span>+{item.positive_marks_per_question} / -{item.negative_marks_per_question}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-slate-800 p-4">
                  <h3 className="font-semibold">Question type breakdown</h3>
                  <div className="mt-2 flex flex-wrap gap-2 text-sm text-slate-300">
                    {Object.entries(summary.question_type_breakdown || {}).map(([type, count]) => <span key={type} className="rounded-full bg-slate-700 px-3 py-1">{type.replaceAll("_", " ")}: {count}</span>)}
                  </div>
                </div>
                {instructions.length > 0 && <div className="rounded-lg border border-amber-400/20 bg-amber-500/5 p-4"><h3 className="font-semibold text-amber-200">Examination instructions</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">{instructions.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
                <p className="text-sm text-amber-300">{summarySecondsUntilContinue > 0 ? "You can continue in " + summarySecondsUntilContinue + " seconds. Automatic continuation in " + summarySecondsUntilAutoContinue + " seconds." : "You may continue now, or wait " + summarySecondsUntilAutoContinue + " more seconds for automatic continuation."}</p>
                <button type="button" onClick={continueAfterSummary} disabled={summarySecondsUntilContinue > 0} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">Continue to start window</button>
              </div>
            )}
            {prestartStage === "start_window" && (
              <div className="mt-8 space-y-4">
                <h2 className="text-xl font-semibold">Ready to begin?</h2>
                <p className="text-sm text-slate-300">You have 17 seconds to start the examination. If you do not select the button, the examination will start automatically when the countdown ends.</p>
                <p className="text-4xl font-bold tabular-nums text-amber-300">{startWindowSecondsRemaining ?? 17}s</p>
                <button type="button" onClick={confirmExamStart} disabled={!startWindowSecondsRemaining} className="rounded-lg bg-green-600 px-6 py-3 font-semibold hover:bg-green-500 disabled:opacity-50">Start Examination</button>
              </div>
            )}
            {error && <p role="alert" className="mt-5 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
            {message && <p role="status" className="mt-5 text-sm text-green-300">{message}</p>}
          </section>
          <aside className="h-fit space-y-3 rounded-2xl border border-white/10 bg-slate-900 p-4">
            <div className="flex items-center justify-between gap-2"><h2 className="font-semibold">Camera</h2><button type="button" onClick={() => setShowCameraPreview((visible) => !visible)} className="text-xs text-blue-300">{showCameraPreview ? "Hide preview" : "Show preview"}</button></div>
            <WebcamPreview enabled={Boolean(paper.proctoring_enabled || !faceCaptured)} showPreview={showCameraPreview} compact onStreamReady={handleCameraStream} onCameraStatusChange={handleCameraStatus} />
            <video ref={captureVideoRef} muted autoPlay playsInline className="hidden" />
            <FaceProctoring stream={cameraStream} enabled={!faceCaptured} sensitivity={paper.gaze_tracking_sensitivity ?? 0.5} onFaceMissing={proctoring.reportFaceNotDetected} onFaceVerified={handleFaceVerified} onMultipleFaces={proctoring.reportMultipleFaces} onGazeAway={proctoring.reportGazeAway} onDetectorError={proctoring.reportWebcamError} />
            <p className="text-xs text-slate-400">Hiding the preview does not stop camera monitoring. Only a still photo is saved.</p>
          </aside>
        </div>
      </main>
    );
  }

  return (
    <main
      className="min-h-screen select-none bg-slate-950 text-white"
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

          <div className="flex flex-wrap items-center justify-end gap-4">
            <div className="text-right">
              <p className="text-xs text-slate-400">Time Remaining</p>
              <p className={`text-xl font-bold tabular-nums ${
                remainingSeconds !== null && remainingSeconds <= 60
                  ? "text-red-400"
                  : remainingSeconds !== null && remainingSeconds <= 300
                    ? "text-amber-400"
                    : "text-green-400"
              }`}>{formatTime(remainingSeconds)}</p>
            </div>
            <button
              type="button"
              onClick={togglePause}
              disabled={pauseBusy || submitting}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm font-semibold hover:bg-white/10 disabled:opacity-50"
            >
              {pauseBusy ? "Please wait..." : isPaused ? "Resume Exam" : "Pause Exam"}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[1fr_280px]">
        <section className="relative rounded-2xl border border-white/10 bg-slate-900 p-6">
          {paper.proctoring_enabled && !faceVerified && (
            <div
              role="status"
              aria-live="polite"
              className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-2xl bg-slate-950/95 p-6 text-center"
            >
              <div className="max-w-md">
                <p className="text-lg font-bold text-white">
                  Complete the face-presence check to begin
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Keep your face clearly visible in the webcam. The examination
                  questions remain locked until one face is detected continuously
                  for a short verification period.
                </p>
                <p className="mt-4 text-sm text-amber-300">
                  {cameraStream
                    ? "Face-presence check is in progress..."
                    : "Allow camera access and keep the webcam connected."}
                </p>
              </div>
            </div>
          )}

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
                <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
                  {currentQuestion.question_time_limit_seconds ? (
                    <span className={`rounded-full px-3 py-1 ${questionRemainingSeconds !== null && questionRemainingSeconds <= 10 ? "bg-red-500/20 text-red-300" : "bg-cyan-500/15 text-cyan-300"}`}>
                      Question time: {formatTime(questionRemainingSeconds)}
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-400">No separate question timer</span>
                  )}
                  {isPaused && <span className="rounded-full bg-amber-500/20 px-3 py-1 text-amber-300">Paused — overall deadline continues</span>}
                  {questionTimerLocked && <span className="rounded-full bg-red-500/20 px-3 py-1 text-red-300">Question time expired — answer locked</span>}
                </div>
                <h2 className="whitespace-pre-wrap text-lg font-semibold leading-8">
                  {currentQuestion.question_text}
                </h2>

                {questionImageUrls[currentQuestion.id] && (
                  <div className="mt-5 rounded-xl border border-slate-700 bg-slate-800 p-3">
                    <p className="mb-2 text-xs font-medium text-slate-400">
                      Question Image
                    </p>
                    <img
                      src={questionImageUrls[currentQuestion.id]}
                      alt="Image attached to the examination question"
                      className="max-h-96 w-full rounded-lg bg-white object-contain"
                    />
                  </div>
                )}

                <fieldset disabled={isPaused || questionTimerLocked} className="min-w-0">
                  {renderAnswerInput(currentQuestion)}
                </fieldset>
              </div>

              <div className="mt-8 flex flex-wrap justify-between gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setCurrentIndex((index) => Math.max(0, index - 1))
                  }
                  disabled={currentIndex === 0 || isPaused}
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
                    disabled={isPaused}
                    className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold hover:bg-blue-500 disabled:opacity-40"
                  >
                    Next Question
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowSubmitConfirmation(true)}
                    disabled={submitting || isPaused}
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
                  disabled={isPaused}
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

          <div className="mt-6 space-y-3 border-t border-white/10 pt-5">
            {paper.proctoring_enabled && <h3 className="font-semibold">Automated Proctoring</h3>}
            <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Camera preview</h3><button type="button" onClick={() => setShowCameraPreview((visible) => !visible)} className="text-xs text-blue-300">{showCameraPreview ? "Hide" : "Show"}</button></div>
            <WebcamPreview enabled showPreview={showCameraPreview} compact onStreamReady={handleCameraStream} onCameraStatusChange={handleCameraStatus} />
            {paper.proctoring_enabled && (
              <>
                <FaceProctoring
                  stream={cameraStream}
                  enabled={paper.status === "in_progress"}
                  sensitivity={paper.gaze_tracking_sensitivity ?? 0.5}
                  onFaceMissing={proctoring.reportFaceNotDetected}
                  onFaceVerified={handleFaceVerified}
                  onMultipleFaces={proctoring.reportMultipleFaces}
                  onGazeAway={proctoring.reportGazeAway}
                  onDetectorError={proctoring.reportWebcamError}
                />
                <p className="text-xs text-slate-400">
                  Face presence: {faceVerified ? "Confirmed" : "Pending"} · Monitoring: {proctoring.isMonitoring ? "Active" : "Starting"} · Heartbeat: {websocketStatus}
                </p>
                <p className="text-xs text-amber-300">Proctoring checks are automated indicators for examiner review, not proof of misconduct.</p>
              </>
            )}
          </div>

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
              disabled={submitting || (paper.proctoring_enabled && !faceVerified)}
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

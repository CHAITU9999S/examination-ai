
import api from "./api";

export type ProctoringEventType =
  | "tab_switch"
  | "window_blur"
  | "window_focus"
  | "face_not_detected"
  | "multiple_faces"
  | "gaze_away"
  | "webcam_error"
  | "heartbeat";

export interface ProctoringEventSubmission {
  event_type: ProctoringEventType;
  description?: string;
  gaze_data?: Record<string, unknown> | null;
  snapshot_data?: string | null;
}

export interface ProctoringEventRecord {
  id: number;
  session_id: number;
  event_type: string;
  description?: string | null;
  suspicion_points?: number;
  created_at?: string;
}

export interface ProctoringSummary {
  session_id: number;
  suspicion_score: number;
  total_events: number;
  tab_switch_count?: number;
  events?: ProctoringEventRecord[];
  event_counts?: Record<string, number>;
}

const EXAM_TOKEN_KEY = "examguard_exam_token";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

function getExamToken(): string {
  if (typeof window === "undefined") {
    throw new Error("Examination session is unavailable.");
  }

  const token = sessionStorage.getItem(EXAM_TOKEN_KEY);

  if (!token) {
    throw new Error("Exam access token is missing.");
  }

  return token;
}

function validateSessionId(sessionId: number): void {
  if (!Number.isInteger(sessionId) || sessionId <= 0) {
    throw new Error("Invalid examination session ID.");
  }
}

function buildWebSocketBaseUrl(): string {
  return API_BASE_URL.replace(/^http:/, "ws:").replace(
    /^https:/,
    "wss:"
  );
}

export const proctoringService = {
  async submitEvent(
    sessionId: number,
    event: ProctoringEventSubmission
  ): Promise<unknown> {
    validateSessionId(sessionId);

    return api.post(
      `/exam-sessions/${sessionId}/proctoring/events`,
      {
        event_type: event.event_type,
        description: event.description ?? "",
        gaze_data: event.gaze_data ?? null,
        snapshot_data: event.snapshot_data ?? null,
      },
      {
        token: getExamToken(),
      }
    );
  },

  async getSummary(
    sessionId: number
  ): Promise<ProctoringSummary> {
    validateSessionId(sessionId);

    return api.get<ProctoringSummary>(
      `/exam-sessions/${sessionId}/proctoring/summary`,
      {
        token: getExamToken(),
      }
    );
  },

  createHeartbeatUrl(sessionId: number): string {
    validateSessionId(sessionId);

    const token = encodeURIComponent(getExamToken());

    return (
      `${buildWebSocketBaseUrl()}` +
      `/exam-sessions/${sessionId}/proctoring/heartbeat` +
      `?token=${token}`
    );
  },

  async reportTabSwitch(sessionId: number) {
    return this.submitEvent(sessionId, {
      event_type: "tab_switch",
      description: "The examination tab became hidden.",
    });
  },

  async reportWindowBlur(sessionId: number) {
    return this.submitEvent(sessionId, {
      event_type: "window_blur",
      description: "The examination window lost focus.",
    });
  },

  async reportWindowFocus(sessionId: number) {
    return this.submitEvent(sessionId, {
      event_type: "window_focus",
      description: "The examination window regained focus.",
    });
  },

  async reportFaceNotDetected(sessionId: number) {
    return this.submitEvent(sessionId, {
      event_type: "face_not_detected",
      description: "The candidate's face was not detected.",
    });
  },

  async reportMultipleFaces(sessionId: number) {
    return this.submitEvent(sessionId, {
      event_type: "multiple_faces",
      description: "Multiple faces were detected.",
    });
  },

  async reportGazeAway(
    sessionId: number,
    gazeData?: Record<string, unknown>
  ) {
    return this.submitEvent(sessionId, {
      event_type: "gaze_away",
      description: "The candidate's gaze was away from the screen.",
      gaze_data: gazeData ?? null,
    });
  },

  async reportWebcamError(
    sessionId: number,
    description?: string
  ) {
    return this.submitEvent(sessionId, {
      event_type: "webcam_error",
      description:
        description || "The examination webcam encountered an error.",
    });
  },
};

export default proctoringService;

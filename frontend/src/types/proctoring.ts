
export type ProctoringEventType =
  | "tab_switch"
  | "window_blur"
  | "window_focus"
  | "face_not_detected"
  | "multiple_faces"
  | "gaze_away"
  | "webcam_error"
  | "heartbeat";

export type WebcamStatus =
  | "idle"
  | "requesting"
  | "active"
  | "denied"
  | "unavailable"
  | "error";

export type WebSocketStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting"
  | "error";

export interface GazeData {
  direction?: "left" | "right" | "center" | "up" | "down";
  confidence?: number;
  timestamp?: string;
  [key: string]: unknown;
}

export interface ProctoringEvent {
  id?: number;
  session_id: number;
  event_type: ProctoringEventType;
  description?: string | null;
  suspicion_points?: number;
  snapshot_data?: string | null;
  gaze_data?: GazeData | null;
  tab_switch_count?: number | null;
  created_at?: string;
}

export interface ProctoringEventRequest {
  event_type: ProctoringEventType;
  description?: string;
  snapshot_data?: string;
  gaze_data?: GazeData;
}

export interface ProctoringSummary {
  session_id: number;
  suspicion_score: number;
  total_events: number;
  tab_switch_count: number;
  event_counts: Record<string, number>;
  events: ProctoringEvent[];
}

export interface ProctoringSettings {
  enabled: boolean;
  webcam_required: boolean;
  gaze_tracking_sensitivity: number;
  max_tab_switch_warnings: number;
}

export interface ProctoringWarning {
  id: string;
  event_type: ProctoringEventType;
  message: string;
  timestamp: string;
  dismissed?: boolean;
}

export interface HeartbeatRequest {
  type: "heartbeat";
}

export interface HeartbeatResponse {
  type?: "heartbeat_ack" | "session_expired" | "error";
  remaining_seconds?: number;
  message?: string;
}

export interface ProctoringState {
  isMonitoring: boolean;
  webcamStatus: WebcamStatus;
  webSocketStatus: WebSocketStatus;
  suspicionScore: number;
  tabSwitchCount: number;
  warnings: ProctoringWarning[];
}

export const PROCTORING_EVENT_LABELS: Record<
  ProctoringEventType,
  string
> = {
  tab_switch: "Tab Switch",
  window_blur: "Window Lost Focus",
  window_focus: "Window Regained Focus",
  face_not_detected: "Face Not Detected",
  multiple_faces: "Multiple Faces Detected",
  gaze_away: "Gaze Away From Screen",
  webcam_error: "Webcam Error",
  heartbeat: "Session Heartbeat",
};

export function isProctoringEventType(
  value: unknown
): value is ProctoringEventType {
  return (
    typeof value === "string" &&
    [
      "tab_switch",
      "window_blur",
      "window_focus",
      "face_not_detected",
      "multiple_faces",
      "gaze_away",
      "webcam_error",
      "heartbeat",
    ].includes(value)
  );
}

export function normalizeSuspicionScore(
  score: number
): number {
  if (!Number.isFinite(score)) {
    return 0;
  }

  return Math.min(100, Math.max(0, score));
}

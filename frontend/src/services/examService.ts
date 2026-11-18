
import api from "./api";

export interface Exam {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  randomize_questions?: boolean;
  start_time?: string | null;
  end_time?: string | null;
  negative_marking?: boolean;
  proctoring_enabled?: boolean;
  created_by?: number | null;
}

export interface ExamCreateData {
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  randomize_questions?: boolean;
  selection_rules?: Record<string, unknown>;
  start_time: string;
  end_time: string;
  negative_marking?: boolean;
  proctoring_enabled?: boolean;
  gaze_tracking_sensitivity?: number;
  max_tab_switch_warnings?: number;
}

export interface ExamStartResponse {
  session_id: number;
  access_token: string;
  exam_id: number;
  expires_at?: string;
  remaining_seconds?: number;
  message?: string;
}

export interface ExamQuestionOption {
  id: number;
  option_text: string;
}

export interface ExamPaperQuestion {
  id: number;
  question_text: string;
  question_type: string;
  subject?: string | null;
  difficulty?: string | null;
  marks: number;
  negative_marks?: number;
  options?: ExamQuestionOption[];
}

export interface ExamPaperResponse {
  session_id?: number;
  exam_id?: number;
  questions: ExamPaperQuestion[];
  remaining_seconds?: number;
}

export interface RemainingTimeResponse {
  remaining_seconds: number;
  status?: string;
  expires_at?: string;
}

export interface ExamSubmissionResponse {
  message?: string;
  status?: string;
  session_id?: number;
  submitted_at?: string;
}

const EXAM_TOKEN_KEY = "examguard_exam_token";
const EXAM_SESSION_KEY = "examguard_session_id";

function saveExamSession(
  sessionId: number,
  examToken: string
): void {
  if (typeof window === "undefined") {
    return;
  }

  sessionStorage.setItem(EXAM_SESSION_KEY, String(sessionId));
  sessionStorage.setItem(EXAM_TOKEN_KEY, examToken);
  sessionStorage.setItem(`examguard_exam_token_${sessionId}`, examToken);
}

function getExamToken(sessionId: number): string {
  if (typeof window === "undefined") {
    throw new Error("Examination session is unavailable.");
  }

  const token = sessionStorage.getItem(`examguard_exam_token_${sessionId}`) || sessionStorage.getItem(EXAM_TOKEN_KEY);

  if (!token) {
    throw new Error("Exam access token is missing. Start the examination again.");
  }

  return token;
}

export const examService = {
  async getExams(): Promise<Exam[]> {
    const response = await api.get<Exam[] | { exams: Exam[] }>(
      "/exams"
    );

    if (Array.isArray(response)) {
      return response;
    }

    return response.exams ?? [];
  },

  async createExam(data: ExamCreateData): Promise<Exam> {
    return api.post<Exam>("/exams", data);
  },

  async startExam(examId: number): Promise<ExamStartResponse> {
    if (!Number.isInteger(examId) || examId <= 0) {
      throw new Error("Invalid examination ID.");
    }

    const response = await api.post<ExamStartResponse>(
      `/exam-sessions/start/${examId}`
    );

    if (
      !response ||
      !Number.isInteger(response.session_id) ||
      response.session_id <= 0 ||
      typeof response.access_token !== "string" ||
      !response.access_token
    ) {
      throw new Error("The server returned an invalid exam session.");
    }

    saveExamSession(response.session_id, response.access_token);
    sessionStorage.setItem(`examguard_exam_id_${response.session_id}`, String(response.exam_id));

    return response;
  },

  async getExamPaper(
    sessionId: number
  ): Promise<ExamPaperResponse> {
    if (!Number.isInteger(sessionId) || sessionId <= 0) {
      throw new Error("Invalid examination session ID.");
    }

    return api.get<ExamPaperResponse>(
      `/exam-sessions/paper/${sessionStorage.getItem(`examguard_exam_id_${sessionId}`) || sessionId}`,
      {
        token: getExamToken(sessionId),
      }
    );
  },

  async getRemainingTime(
    sessionId: number
  ): Promise<RemainingTimeResponse> {
    if (!Number.isInteger(sessionId) || sessionId <= 0) {
      throw new Error("Invalid examination session ID.");
    }

    return api.get<RemainingTimeResponse>(
      `/exam-sessions/time/${sessionId}`,
      {
        token: getExamToken(sessionId),
      }
    );
  },

  async submitExam(
    sessionId: number
  ): Promise<ExamSubmissionResponse> {
    if (!Number.isInteger(sessionId) || sessionId <= 0) {
      throw new Error("Invalid examination session ID.");
    }

    return api.post<ExamSubmissionResponse>(
      `/exam-sessions/submit/${sessionId}`,
      {},
      {
        token: getExamToken(sessionId),
      }
    );
  },

  getStoredExamSessionId(): number | null {
    if (typeof window === "undefined") {
      return null;
    }

    const value = sessionStorage.getItem(EXAM_SESSION_KEY);

    if (!value) {
      return null;
    }

    const sessionId = Number(value);

    return Number.isInteger(sessionId) && sessionId > 0
      ? sessionId
      : null;
  },

  clearExamSession(): void {
    if (typeof window === "undefined") {
      return;
    }

    const sessionId = this.getStoredExamSessionId();
    if (sessionId !== null) {
      sessionStorage.removeItem(`examguard_exam_token_${sessionId}`);
      sessionStorage.removeItem(`examguard_exam_id_${sessionId}`);
    }
    sessionStorage.removeItem(EXAM_TOKEN_KEY);
    sessionStorage.removeItem(EXAM_SESSION_KEY);
  },
};

export default examService;

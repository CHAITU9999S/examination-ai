
export type ExamStatus =
  | "upcoming"
  | "available"
  | "in_progress"
  | "submitted"
  | "expired"
  | "completed";

export interface DifficultyDistribution {
  easy?: number;
  medium?: number;
  hard?: number;
}

export interface QuestionTypeDistribution {
  MCQ?: number;
  multi_select?: number;
  short_answer?: number;
  long_answer?: number;
  image_upload?: number;
}

export interface ExamSelectionRules {
  difficulty_distribution?: DifficultyDistribution;
  question_type_distribution?: QuestionTypeDistribution;
}

export interface Exam {
  id: number;
  title: string;
  subject: string | null;
  duration_minutes: number;
  total_questions: number;
  randomize_questions: boolean;
  selection_rules?: ExamSelectionRules | null;
  start_time: string;
  end_time: string;
  negative_marking: boolean;
  proctoring_enabled: boolean;
  gaze_tracking_sensitivity?: number | null;
  max_tab_switch_warnings?: number | null;
  created_by?: number | null;
}

export interface ExamCreateRequest {
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  randomize_questions: boolean;
  selection_rules?: ExamSelectionRules;
  start_time: string;
  end_time: string;
  negative_marking: boolean;
  proctoring_enabled: boolean;
  gaze_tracking_sensitivity?: number;
  max_tab_switch_warnings?: number;
}

export interface ExamSession {
  id: number;
  exam_id: number;
  student_id: number;
  started_at: string;
  expires_at: string;
  submitted_at?: string | null;
  status: "in_progress" | "submitted" | "expired";
  remaining_seconds?: number;
}

export interface ExamStartRequest {
  exam_id: number;
}

export interface ExamStartResponse {
  session_id: number;
  exam_id: number;
  access_token: string;
  token_type: string;
  started_at: string;
  expires_at: string;
  remaining_seconds: number;
  total_questions?: number;
  status?: string;
}

export interface ExamQuestionOption {
  id: number;
  option_text: string;
}

export interface ExamPaperQuestion {
  id: number;
  question_text: string;
  question_type:
    | "MCQ"
    | "multi_select"
    | "short_answer"
    | "long_answer"
    | "image_upload";
  subject?: string | null;
  difficulty?: "easy" | "medium" | "hard" | null;
  marks: number;
  options?: ExamQuestionOption[];
}

export interface ExamPaper {
  session_id: number;
  exam_id: number;
  title?: string;
  duration_minutes?: number;
  remaining_seconds?: number;
  questions: ExamPaperQuestion[];
}

export interface RemainingTimeResponse {
  session_id: number;
  remaining_seconds: number;
  expires_at?: string;
  status?: string;
}

export interface ExamSubmitResponse {
  message: string;
  session_id?: number;
  status?: string;
  submitted_at?: string;
}

export interface ExamResult {
  id: number;
  session_id: number;
  total_marks: number;
  obtained_marks: number;
  percentage: number;
  evaluated_at?: string | null;
}

export interface ExamListResponse {
  exams: Exam[];
}

export function getExamStatus(
  exam: Pick<Exam, "start_time" | "end_time">,
  currentTime = new Date()
): ExamStatus {
  const start = new Date(exam.start_time).getTime();
  const end = new Date(exam.end_time).getTime();
  const now = currentTime.getTime();

  if (
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    !Number.isFinite(now) ||
    end <= start
  ) {
    return "expired";
  }

  if (now < start) {
    return "upcoming";
  }

  if (now > end) {
    return "expired";
  }

  return "available";
}


import api from "./api";

export type AnswerQuestionType =
  | "MCQ"
  | "multi_select"
  | "short_answer"
  | "long_answer"
  | "image_upload";

export interface AnswerSubmission {
  question_id: number;
  question_type: AnswerQuestionType;
  answer_text?: string | null;
  selected_option_ids?: number[];
}

export interface SavedAnswer {
  id: number;
  session_id: number;
  question_id: number;
  answer_text?: string | null;
  image_path?: string | null;
  awarded_marks?: number | null;
  submitted_at?: string | null;
}

export interface AnswerSubmissionResponse {
  message?: string;
  answer?: SavedAnswer;
  id?: number;
  question_id?: number;
}

export interface ImageUploadResponse {
  message?: string;
  image_path?: string;
  thumbnail_path?: string;
  answer?: SavedAnswer;
}

const EXAM_TOKEN_KEY = "examguard_exam_token";

function getExamToken(sessionId: number): string {
  if (typeof window === "undefined") {
    throw new Error("Examination session is unavailable.");
  }

  const token = sessionStorage.getItem(`examguard_exam_token_${sessionId}`) || sessionStorage.getItem(EXAM_TOKEN_KEY);

  if (!token) {
    throw new Error("Exam access token is missing.");
  }

  return token;
}

function validatePositiveId(value: number, field: string): void {
  if (
    !Number.isInteger(value) ||
    value <= 0
  ) {
    throw new Error(`${field} must be a positive integer.`);
  }
}

function normalizeObjectiveAnswer(
  questionType: AnswerQuestionType,
  selectedOptionIds: number[]
): string {
  if (!Array.isArray(selectedOptionIds)) {
    throw new Error("Selected options must be an array.");
  }

  if (
    selectedOptionIds.some(
      (id) => !Number.isInteger(id) || id <= 0
    )
  ) {
    throw new Error("Invalid selected option ID.");
  }

  const uniqueIds = [...new Set(selectedOptionIds)];

  if (questionType === "MCQ" && uniqueIds.length !== 1) {
    throw new Error("MCQ requires exactly one selected option.");
  }

  if (
    questionType === "multi_select" &&
    uniqueIds.length === 0
  ) {
    throw new Error("Select at least one option.");
  }

  return JSON.stringify(uniqueIds);
}

export const answerService = {
  async saveAnswer(
    sessionId: number,
    submission: AnswerSubmission
  ): Promise<AnswerSubmissionResponse> {
    validatePositiveId(sessionId, "Session ID");
    validatePositiveId(submission.question_id, "Question ID");

    const objective =
      submission.question_type === "MCQ" ||
      submission.question_type === "multi_select";

    let answerText = submission.answer_text ?? "";

    if (objective) {
      answerText = normalizeObjectiveAnswer(
        submission.question_type,
        submission.selected_option_ids ?? []
      );
    } else if (submission.question_type === "image_upload") {
      throw new Error(
        "Use uploadAnswerImage() for handwritten image answers."
      );
    } else if (typeof answerText !== "string") {
      throw new Error("Answer must be text.");
    }

    return api.post<AnswerSubmissionResponse>(
      `/answers/${sessionId}`,
      {
        question_id: submission.question_id,
        answer_text: answerText,
      },
      {
        token: getExamToken(sessionId),
      }
    );
  },

  async uploadAnswerImage(
    sessionId: number,
    questionId: number,
    file: File
  ): Promise<ImageUploadResponse> {
    validatePositiveId(sessionId, "Session ID");
    validatePositiveId(questionId, "Question ID");

    if (!(file instanceof File) || file.size === 0) {
      throw new Error("Please select a valid answer image.");
    }

    const maxSize = 10 * 1024 * 1024;

    if (file.size > maxSize) {
      throw new Error("Image size cannot exceed 10 MB.");
    }

    const allowedTypes = [
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/tiff",
      "image/bmp",
    ];

    if (!allowedTypes.includes(file.type)) {
      throw new Error("Unsupported image format.");
    }

    const formData = new FormData();

    formData.append("question_id", String(questionId));
    formData.append("file", file);

    return api.upload<ImageUploadResponse>(
      `/answers/${sessionId}/upload`,
      formData,
      {
        token: getExamToken(sessionId),
      }
    );
  },

  async getAnswer(
    sessionId: number,
    questionId: number
  ): Promise<SavedAnswer | null> {
    validatePositiveId(sessionId, "Session ID");
    validatePositiveId(questionId, "Question ID");

    return api.get<SavedAnswer | null>(
      `/answers/${sessionId}/${questionId}`,
      {
        token: getExamToken(sessionId),
      }
    );
  },

  async getSessionAnswers(
    sessionId: number
  ): Promise<SavedAnswer[]> {
    validatePositiveId(sessionId, "Session ID");

    const response = await api.get<
      SavedAnswer[] | { answers: SavedAnswer[] }
    >(`/answers/${sessionId}`, {
      token: getExamToken(sessionId),
    });

    return Array.isArray(response)
      ? response
      : response.answers ?? [];
  },
};

export default answerService;

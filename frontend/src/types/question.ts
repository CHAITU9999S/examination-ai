
export type QuestionType =
  | "MCQ"
  | "multi_select"
  | "short_answer"
  | "long_answer"
  | "image_upload";

export type DifficultyLevel = "easy" | "medium" | "hard";

export interface QuestionOption {
  id?: number;
  option_text: string;
  is_correct?: boolean;
}

export interface Question {
  id: number;
  question_text: string;
  question_type: QuestionType;
  subject?: string | null;
  difficulty?: DifficultyLevel | null;
  expected_answer?: string | null;
  model_answer_text?: string | null;
  marks: number;
  negative_marks: number;
  tags?: string[] | null;
  options?: QuestionOption[];
  created_by?: number | null;
}

export interface QuestionCreateRequest {
  question_text: string;
  question_type: QuestionType;
  subject?: string | null;
  difficulty?: DifficultyLevel | null;
  expected_answer?: string | null;
  model_answer_text?: string | null;
  marks: number;
  negative_marks?: number;
  tags?: string[];
  options?: string[];
  correct_option_index?: number | null;
  correct_option_indices?: number[] | null;
}

export interface QuestionUpdateRequest {
  question_text?: string;
  subject?: string | null;
  difficulty?: DifficultyLevel | null;
  expected_answer?: string | null;
  model_answer_text?: string | null;
  marks?: number;
  negative_marks?: number;
  tags?: string[];
}

export interface QuestionListResponse {
  questions: Question[];
}

export interface QuestionValidationResult {
  valid: boolean;
  errors: string[];
}

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  MCQ: "Multiple Choice Question",
  multi_select: "Multiple Select Question",
  short_answer: "Short Answer",
  long_answer: "Long Answer",
  image_upload: "Image Upload",
};

export const DIFFICULTY_LABELS: Record<DifficultyLevel, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

export function isObjectiveQuestion(
  questionType: QuestionType
): boolean {
  return (
    questionType === "MCQ" ||
    questionType === "multi_select"
  );
}

export function isSubjectiveQuestion(
  questionType: QuestionType
): boolean {
  return (
    questionType === "short_answer" ||
    questionType === "long_answer" ||
    questionType === "image_upload"
  );
}

export function validateQuestionInput(
  question: QuestionCreateRequest
): QuestionValidationResult {
  const errors: string[] = [];

  if (!question.question_text?.trim()) {
    errors.push("Question text is required.");
  }

  if (
    !Number.isFinite(question.marks) ||
    question.marks <= 0
  ) {
    errors.push("Marks must be a positive number.");
  }

  const negativeMarks = question.negative_marks ?? 0;

  if (
    !Number.isFinite(negativeMarks) ||
    negativeMarks < 0
  ) {
    errors.push("Negative marks cannot be negative.");
  }

  if (isObjectiveQuestion(question.question_type)) {
    const options = question.options ?? [];

    if (options.length < 2) {
      errors.push("At least two options are required.");
    }

    if (options.some((option) => !option.trim())) {
      errors.push("Options cannot be empty.");
    }

    const normalizedOptions = options.map((option) =>
      option.trim().toLowerCase()
    );

    if (
      new Set(normalizedOptions).size !==
      normalizedOptions.length
    ) {
      errors.push("Duplicate options are not allowed.");
    }

    if (question.question_type === "MCQ") {
      const index = question.correct_option_index;

      if (
        index === undefined ||
        index === null ||
        !Number.isInteger(index) ||
        index < 0 ||
        index >= options.length
      ) {
        errors.push("Select exactly one correct option.");
      }

      if (question.correct_option_indices?.length) {
        errors.push(
          "MCQ must use only one correct option index."
        );
      }
    }

    if (question.question_type === "multi_select") {
      const indexes = question.correct_option_indices ?? [];

      if (indexes.length === 0) {
        errors.push("Select at least one correct option.");
      }

      if (
        indexes.some(
          (index) =>
            !Number.isInteger(index) ||
            index < 0 ||
            index >= options.length
        )
      ) {
        errors.push("A correct option index is invalid.");
      }

      if (new Set(indexes).size !== indexes.length) {
        errors.push("Duplicate correct option indexes are not allowed.");
      }

      if (question.correct_option_index !== undefined &&
          question.correct_option_index !== null) {
        errors.push(
          "Multi-select must use correct option indexes."
        );
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}


"use client";

import { useState, type FormEvent } from "react";

export type QuestionType =
  | "MCQ"
  | "multi_select"
  | "short_answer"
  | "long_answer"
  | "image_upload";

export interface QuestionFormData {
  question_text: string;
  question_type: QuestionType;
  subject: string;
  difficulty: "easy" | "medium" | "hard";
  marks: number;
  negative_marks: number;
  model_answer_text: string;
  tags: string[];
  options?: string[];
  correct_option_index?: number;
  correct_option_indices?: number[];
}

interface QuestionFormProps {
  onSubmit: (data: QuestionFormData) => void | Promise<void>;
  submitting?: boolean;
}

const QUESTION_TYPES: {
  value: QuestionType;
  label: string;
}[] = [
  { value: "MCQ", label: "Multiple Choice (Single Answer)" },
  { value: "multi_select", label: "Multiple Choice (Multiple Answers)" },
  { value: "short_answer", label: "Short Answer" },
  { value: "long_answer", label: "Long Answer" },
  { value: "image_upload", label: "Image Upload Answer" },
];

export default function QuestionForm({
  onSubmit,
  submitting = false,
}: QuestionFormProps) {
  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] =
    useState<QuestionType>("MCQ");

  const [subject, setSubject] = useState("");
  const [difficulty, setDifficulty] =
    useState<"easy" | "medium" | "hard">("medium");

  const [marks, setMarks] = useState("1");
  const [negativeMarks, setNegativeMarks] = useState("0");

  const [modelAnswer, setModelAnswer] = useState("");
  const [tagsText, setTagsText] = useState("");

  const [options, setOptions] = useState([
    "",
    "",
    "",
    "",
  ]);

  const [correctOptionIndex, setCorrectOptionIndex] =
    useState<number>(0);

  const [correctOptionIndices, setCorrectOptionIndices] =
    useState<number[]>([]);

  const [error, setError] = useState("");

  const isObjective =
    questionType === "MCQ" ||
    questionType === "multi_select";

  function updateOption(index: number, value: string) {
    setOptions((previous) =>
      previous.map((option, optionIndex) =>
        optionIndex === index ? value : option
      )
    );
  }

  function addOption() {
    if (options.length >= 10) {
      setError("A maximum of 10 options is allowed.");
      return;
    }

    setOptions((previous) => [...previous, ""]);
    setError("");
  }

  function removeOption(index: number) {
    if (options.length <= 2) {
      setError("At least two options are required.");
      return;
    }

    setOptions((previous) =>
      previous.filter((_, optionIndex) => optionIndex !== index)
    );

    setCorrectOptionIndices((previous) =>
      previous
        .filter((value) => value !== index)
        .map((value) => value > index ? value - 1 : value)
    );

    if (correctOptionIndex === index) {
      setCorrectOptionIndex(0);
    } else if (correctOptionIndex > index) {
      setCorrectOptionIndex((previous) => previous - 1);
    }

    setError("");
  }

  function toggleCorrectOption(index: number) {
    setCorrectOptionIndices((previous) =>
      previous.includes(index)
        ? previous.filter((value) => value !== index)
        : [...previous, index]
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const trimmedQuestion = questionText.trim();
    const parsedMarks = Number(marks);
    const parsedNegativeMarks = Number(negativeMarks);

    if (!trimmedQuestion) {
      setError("Enter the question text.");
      return;
    }

    if (
      !Number.isFinite(parsedMarks) ||
      parsedMarks <= 0
    ) {
      setError("Marks must be a positive number.");
      return;
    }

    if (
      !Number.isFinite(parsedNegativeMarks) ||
      parsedNegativeMarks < 0
    ) {
      setError("Negative marks must be zero or greater.");
      return;
    }

    let cleanedOptions: string[] = [];

    if (isObjective) {
      cleanedOptions = options.map((option) => option.trim());

      if (cleanedOptions.some((option) => !option)) {
        setError("Fill in every option.");
        return;
      }

      const normalizedOptions = cleanedOptions.map((option) =>
        option.toLocaleLowerCase()
      );

      if (
        new Set(normalizedOptions).size !==
        normalizedOptions.length
      ) {
        setError("Duplicate options are not allowed.");
        return;
      }

      if (questionType === "MCQ") {
        if (
          !Number.isInteger(correctOptionIndex) ||
          correctOptionIndex < 0 ||
          correctOptionIndex >= cleanedOptions.length
        ) {
          setError("Select the correct answer.");
          return;
        }
      }

      if (questionType === "multi_select") {
        if (correctOptionIndices.length === 0) {
          setError("Select at least one correct answer.");
          return;
        }
      }
    }

    const tags = tagsText
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);

    const questionData: QuestionFormData = {
      question_text: trimmedQuestion,
      question_type: questionType,
      subject: subject.trim(),
      difficulty,
      marks: parsedMarks,
      negative_marks: parsedNegativeMarks,
      model_answer_text: modelAnswer.trim(),
      tags,
    };

    if (isObjective) {
      questionData.options = cleanedOptions;
    }

    if (questionType === "MCQ") {
      questionData.correct_option_index = correctOptionIndex;
    }

    if (questionType === "multi_select") {
      questionData.correct_option_indices =
        [...correctOptionIndices].sort((a, b) => a - b);
    }

    try {
      await onSubmit(questionData);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to save the question. Please try again."
      );
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div>
        <h2 className="text-xl font-bold text-slate-900">
          Create Question
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Add a question to the examination question bank.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      <div>
        <label
          htmlFor="question_type"
          className="mb-2 block text-sm font-medium text-slate-700"
        >
          Question Type
        </label>

        <select
          id="question_type"
          value={questionType}
          onChange={(event) => {
            setQuestionType(event.target.value as QuestionType);
            setError("");
          }}
          className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm"
          disabled={submitting}
        >
          {QUESTION_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="question_text"
          className="mb-2 block text-sm font-medium text-slate-700"
        >
          Question Text
        </label>

        <textarea
          id="question_text"
          value={questionText}
          onChange={(event) => setQuestionText(event.target.value)}
          placeholder="Enter your question..."
          rows={4}
          required
          disabled={submitting}
          className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm"
        />
      </div>

      {isObjective && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <label className="text-sm font-semibold text-slate-700">
              Answer Options
            </label>

            <button
              type="button"
              onClick={addOption}
              disabled={submitting || options.length >= 10}
              className="rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 disabled:opacity-50"
            >
              + Add Option
            </button>
          </div>

          {options.map((option, index) => (
            <div
              key={index}
              className="flex items-center gap-2"
            >
              {questionType === "MCQ" ? (
                <input
                  type="radio"
                  name="correct_option"
                  checked={correctOptionIndex === index}
                  onChange={() => setCorrectOptionIndex(index)}
                  disabled={submitting}
                  aria-label={`Mark option ${index + 1} as correct`}
                />
              ) : (
                <input
                  type="checkbox"
                  checked={correctOptionIndices.includes(index)}
                  onChange={() => toggleCorrectOption(index)}
                  disabled={submitting}
                  aria-label={`Mark option ${index + 1} as correct`}
                />
              )}

              <input
                type="text"
                value={option}
                onChange={(event) =>
                  updateOption(index, event.target.value)
                }
                placeholder={`Option ${index + 1}`}
                disabled={submitting}
                className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />

              <button
                type="button"
                onClick={() => removeOption(index)}
                disabled={submitting || options.length <= 2}
                className="rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-40"
                aria-label={`Remove option ${index + 1}`}
              >
                Remove
              </button>
            </div>
          ))}

          <p className="text-xs text-slate-500">
            {questionType === "MCQ"
              ? "Select the radio button beside exactly one correct option."
              : "Select every correct option using the checkboxes."}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="subject"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Subject
          </label>

          <input
            id="subject"
            type="text"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="e.g. Computer Science"
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="difficulty"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Difficulty
          </label>

          <select
            id="difficulty"
            value={difficulty}
            onChange={(event) =>
              setDifficulty(
                event.target.value as "easy" | "medium" | "hard"
              )
            }
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="marks"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Marks
          </label>

          <input
            id="marks"
            type="number"
            min="0.01"
            step="any"
            value={marks}
            onChange={(event) => setMarks(event.target.value)}
            required
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="negative_marks"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Negative Marks
          </label>

          <input
            id="negative_marks"
            type="number"
            min="0"
            step="any"
            value={negativeMarks}
            onChange={(event) => setNegativeMarks(event.target.value)}
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label
          htmlFor="model_answer"
          className="mb-2 block text-sm font-medium text-slate-700"
        >
          Model Answer / Expected Answer
        </label>

        <textarea
          id="model_answer"
          value={modelAnswer}
          onChange={(event) => setModelAnswer(event.target.value)}
          rows={3}
          placeholder="Enter the expected answer or reference answer..."
          disabled={submitting}
          className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="tags"
          className="mb-2 block text-sm font-medium text-slate-700"
        >
          Tags
        </label>

        <input
          id="tags"
          type="text"
          value={tagsText}
          onChange={(event) => setTagsText(event.target.value)}
          placeholder="e.g. programming, arrays, basics"
          disabled={submitting}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />

        <p className="mt-1 text-xs text-slate-500">
          Separate multiple tags with commas.
        </p>
      </div>

      {questionType === "image_upload" && (
        <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
          Students will submit an image for this question. The actual
          image upload is handled by the examination answer interface,
          not by this question creation form.
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Saving Question..." : "Create Question"}
      </button>
    </form>
  );
}

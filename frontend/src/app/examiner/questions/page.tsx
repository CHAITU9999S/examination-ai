
"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type QuestionType =
  | "MCQ"
  | "multi_select"
  | "short_answer"
  | "long_answer"
  | "image_upload";

type Difficulty = "easy" | "medium" | "hard";

interface QuestionOption {
  id?: number;
  option_text?: string;
  text?: string;
  is_correct?: boolean;
}

interface Question {
  id: number;
  question_text: string;
  question_type: QuestionType;
  subject?: string | null;
  difficulty?: string | null;
  marks: number;
  negative_marks?: number;
  model_answer_text?: string | null;
  expected_answer?: string | null;
  options?: QuestionOption[];
  question_image_available?: boolean;
}

export default function ExaminerQuestionsPage() {
  const router = useRouter();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingQuestionId, setDeletingQuestionId] = useState<number | null>(null);

  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] =
    useState<QuestionType>("MCQ");
  const [subject, setSubject] = useState("");
  const [difficulty, setDifficulty] =
    useState<Difficulty>("medium");
  const [marks, setMarks] = useState("1");
  const [negativeMarks, setNegativeMarks] = useState("0");
  const [modelAnswer, setModelAnswer] = useState("");
  const [questionImageFile, setQuestionImageFile] = useState<File | null>(null);

  const [options, setOptions] = useState(["", "", "", ""]);
  const [correctOption, setCorrectOption] = useState("0");
  const [correctOptions, setCorrectOptions] = useState<number[]>([0]);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

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

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(`${API_URL}/questions`, {
        method: "GET",
        headers,
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load questions.");
      }

      const data = await response.json();

      const questionList = Array.isArray(data)
        ? data
        : Array.isArray(data.questions)
          ? data.questions
          : null;

      if (!questionList) {
        throw new Error("Unexpected question data returned by the server.");
      }

      setQuestions(questionList);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load questions."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  async function deleteQuestion(questionId: number) {
    if (!window.confirm("Delete this question? Questions already used in an examination or student answer cannot be deleted.")) {
      return;
    }

    setDeletingQuestionId(questionId);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(`${API_URL}/questions/${questionId}`, {
        method: "DELETE",
        headers,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Unable to delete this question.");
      }

      setMessage("Question deleted successfully.");
      await loadQuestions();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete this question."
      );
    } finally {
      setDeletingQuestionId(null);
    }
  }

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  function updateOption(index: number, value: string) {
    setOptions((current) =>
      current.map((option, optionIndex) =>
        optionIndex === index ? value : option
      )
    );
  }

  function toggleCorrectOption(index: number) {
    setCorrectOptions((current) =>
      current.includes(index)
        ? current.filter((item) => item !== index)
        : [...current, index]
    );
  }

  function resetForm() {
    setQuestionText("");
    setQuestionType("MCQ");
    setSubject("");
    setDifficulty("medium");
    setMarks("1");
    setNegativeMarks("0");
    setModelAnswer("");
    setQuestionImageFile(null);
    setOptions(["", "", "", ""]);
    setCorrectOption("0");
    setCorrectOptions([0]);
  }

  async function createQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setMessage("");

    const parsedMarks = Number(marks);
    const parsedNegativeMarks = Number(negativeMarks);

    if (!questionText.trim()) {
      setError("Enter the question text.");
      return;
    }

    if (!subject.trim()) {
      setError("Enter the subject.");
      return;
    }

    if (!Number.isFinite(parsedMarks) || parsedMarks <= 0) {
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

    const objective =
      questionType === "MCQ" || questionType === "multi_select";

    const cleanedOptions = options.map((option) => option.trim());

    if (objective) {
      if (cleanedOptions.filter(Boolean).length < 2) {
        setError("Objective questions require at least two options.");
        return;
      }

      if (cleanedOptions.some((option) => !option)) {
        setError("Please complete or remove all four option fields.");
        return;
      }

      const normalized = cleanedOptions.map((item) =>
        item.toLowerCase()
      );

      if (new Set(normalized).size !== normalized.length) {
        setError("Duplicate options are not allowed.");
        return;
      }

      if (
        questionType === "multi_select" &&
        correctOptions.length === 0
      ) {
        setError("Select at least one correct option.");
        return;
      }
    }

    setCreating(true);

    try {
      const headers = getHeaders();

      if (!headers) return;

      const payload: Record<string, unknown> = {
        question_text: questionText.trim(),
        question_type: questionType,
        subject: subject.trim(),
        difficulty,
        marks: parsedMarks,
        negative_marks: parsedNegativeMarks,
        model_answer_text: modelAnswer.trim() || null,
      };

      if (objective) {
        payload.options = cleanedOptions;
      }

      if (questionType === "MCQ") {
        payload.correct_option_index = Number(correctOption);
      }

      if (questionType === "multi_select") {
        payload.correct_option_indices = correctOptions;
      }

      const response = await fetch(`${API_URL}/questions`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to create question."
        );
      }

      if (questionImageFile) {
        const imageForm = new FormData();
        imageForm.append("file", questionImageFile);
        const imageResponse = await fetch(
          `${API_URL}/questions/${data.question_id}/image`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${localStorage.getItem("examguard_access_token") || ""}`,
            },
            body: imageForm,
          }
        );
        const imageData = await imageResponse.json().catch(() => ({}));
        if (!imageResponse.ok) {
          throw new Error(
            imageData.detail ||
            "The question was created, but its image could not be uploaded. Please retry by creating a new question with the image."
          );
        }
      }

      setMessage(
        questionImageFile
          ? "Question and prompt image created successfully."
          : "Question created successfully."
      );
      resetForm();
      await loadQuestions();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create question."
      );
    } finally {
      setCreating(false);
    }
  }

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
              Examiner / Question Bank
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
        <h1 className="text-3xl font-bold">Question Bank</h1>

        <p className="mt-2 text-slate-400">
          Create and manage questions for your examinations.
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
          <h2 className="text-xl font-bold">Create New Question</h2>

          <form onSubmit={createQuestion} className="mt-6 space-y-5">
            <div>
              <label
                htmlFor="questionText"
                className="mb-2 block text-sm font-medium"
              >
                Question text
              </label>

              <textarea
                id="questionText"
                required
                rows={4}
                value={questionText}
                onChange={(event) =>
                  setQuestionText(event.target.value)
                }
                placeholder="Enter your question..."
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="questionType"
                  className="mb-2 block text-sm font-medium"
                >
                  Question type
                </label>

                <select
                  id="questionType"
                  value={questionType}
                  onChange={(event) =>
                    setQuestionType(event.target.value as QuestionType)
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                >
                  <option value="MCQ">Multiple Choice (MCQ)</option>
                  <option value="multi_select">Multiple Select</option>
                  <option value="short_answer">Short Answer</option>
                  <option value="long_answer">Long Answer</option>
                  <option value="image_upload">Image Upload</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="subject"
                  className="mb-2 block text-sm font-medium"
                >
                  Subject
                </label>

                <input
                  id="subject"
                  required
                  maxLength={100}
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  placeholder="e.g. Computer Science"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label
                  htmlFor="difficulty"
                  className="mb-2 block text-sm font-medium"
                >
                  Difficulty
                </label>

                <select
                  id="difficulty"
                  value={difficulty}
                  onChange={(event) =>
                    setDifficulty(event.target.value as Difficulty)
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="marks"
                  className="mb-2 block text-sm font-medium"
                >
                  Marks
                </label>

                <input
                  id="marks"
                  type="number"
                  min="0.01"
                  step="any"
                  required
                  value={marks}
                  onChange={(event) => setMarks(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label
                  htmlFor="negativeMarks"
                  className="mb-2 block text-sm font-medium"
                >
                  Negative marks
                </label>

                <input
                  id="negativeMarks"
                  type="number"
                  min="0"
                  step="any"
                  value={negativeMarks}
                  onChange={(event) =>
                    setNegativeMarks(event.target.value)
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {questionType === "image_upload" && (
              <div className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
                <label htmlFor="questionImage" className="block font-semibold">
                  Question Image (Optional)
                </label>
                <p className="mt-1 text-sm text-slate-400">
                  Attach a diagram, photograph or scanned image for students to view with this question. Maximum size: 10 MB.
                </p>
                <input
                  id="questionImage"
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp"
                  onChange={(event) => {
                    const file = event.target.files?.[0] || null;
                    if (file && file.size > 10 * 1024 * 1024) {
                      setError("Question image must not exceed 10 MB.");
                      event.target.value = "";
                      setQuestionImageFile(null);
                      return;
                    }
                    setError("");
                    setQuestionImageFile(file);
                  }}
                  className="mt-4 block w-full cursor-pointer rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:font-semibold file:text-white hover:file:bg-blue-500"
                />
                {questionImageFile && (
                  <p className="mt-2 break-all text-sm text-green-300">
                    Selected: {questionImageFile.name}
                  </p>
                )}
              </div>
            )}

            {(questionType === "MCQ" ||
              questionType === "multi_select") && (
              <div className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
                <h3 className="font-semibold">Answer Options</h3>

                <p className="mt-1 text-sm text-slate-400">
                  Enter four options and identify the correct answer.
                </p>

                <div className="mt-5 space-y-3">
                  {options.map((option, index) => (
                    <div
                      key={index}
                      className="flex flex-wrap items-center gap-3"
                    >
                      <span className="w-7 text-sm text-slate-400">
                        {String.fromCharCode(65 + index)}.
                      </span>

                      <input
                        value={option}
                        onChange={(event) =>
                          updateOption(index, event.target.value)
                        }
                        placeholder={`Option ${index + 1}`}
                        className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 outline-none focus:border-blue-500"
                      />

                      {questionType === "MCQ" ? (
                        <label className="flex items-center gap-2 text-sm text-slate-300">
                          <input
                            type="radio"
                            name="correctOption"
                            value={index}
                            checked={correctOption === String(index)}
                            onChange={(event) =>
                              setCorrectOption(event.target.value)
                            }
                          />
                          Correct
                        </label>
                      ) : (
                        <label className="flex items-center gap-2 text-sm text-slate-300">
                          <input
                            type="checkbox"
                            checked={correctOptions.includes(index)}
                            onChange={() => toggleCorrectOption(index)}
                          />
                          Correct
                        </label>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label
                htmlFor="modelAnswer"
                className="mb-2 block text-sm font-medium"
              >
                Model answer / Expected answer
              </label>

              <textarea
                id="modelAnswer"
                rows={4}
                value={modelAnswer}
                onChange={(event) =>
                  setModelAnswer(event.target.value)
                }
                placeholder="Enter the expected answer or reference answer..."
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
              />

              <p className="mt-2 text-xs text-slate-500">
                Add a model answer if you want to use AI suggestions for written or image answers.
              </p>
            </div>

            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-blue-600 px-6 py-3 font-semibold transition hover:bg-blue-500 disabled:opacity-60"
            >
              {creating ? "Creating Question..." : "Save Question"}
            </button>
          </form>
        </section>

        <section className="mt-10 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">Existing Questions</h2>

              <p className="mt-1 text-sm text-slate-400">
                {questions.length} question(s) available
              </p>
            </div>

            <button
              type="button"
              onClick={loadQuestions}
              disabled={loading}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="py-10 text-center text-slate-400">
              Loading questions...
            </p>
          ) : questions.length === 0 ? (
            <p className="py-10 text-center text-slate-400">
              No questions found.
            </p>
          ) : (
            <div className="mt-6 space-y-4">
              {questions.map((question) => (
                <article
                  key={question.id}
                  className="rounded-xl border border-white/10 bg-slate-800/60 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-blue-400">
                        Question #{question.id} ·{" "}
                        {question.question_type}
                      </p>

                      <h3 className="mt-2 font-semibold">
                        {question.question_text}
                      </h3>
                      {question.question_image_available && (
                        <p className="mt-2 text-xs text-green-300">
                          Question image attached
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-300">
                        {question.difficulty || "Unspecified"}
                      </span>
                      <button
                        type="button"
                        onClick={() => void deleteQuestion(question.id)}
                        disabled={deletingQuestionId !== null}
                        className="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs text-red-300 transition hover:bg-red-500/10 disabled:opacity-50"
                      >
                        {deletingQuestionId === question.id ? "Deleting..." : "Delete Question"}
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400">
                    <span>Subject: {question.subject || "—"}</span>
                    <span>Marks: {question.marks}</span>
                    <span>
                      Negative marks: {question.negative_marks ?? 0}
                    </span>
                  </div>

                  {question.options && question.options.length > 0 && (
                    <ul className="mt-4 space-y-2 text-sm text-slate-300">
                      {question.options.map((option, index) => (
                        <li key={option.id ?? index}>
                          {String.fromCharCode(65 + index)}.{" "}
                          {option.option_text ?? option.text ?? ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

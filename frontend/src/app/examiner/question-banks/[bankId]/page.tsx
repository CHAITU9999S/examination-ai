"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type QuestionOption = { id: number; option_text: string; is_correct: boolean };
type Question = {
  id: number;
  question_text: string;
  question_type: string;
  difficulty: string;
  subject: string;
  marks: number;
  negative_marks?: number;
  expected_answer?: string | null;
  model_answer_text?: string | null;
  tags?: string[];
  question_image_available?: boolean;
  expected_answer_image_available?: boolean;
  options: QuestionOption[];
};

function errorMessage(detail: unknown, fallback: string) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || "Invalid question data").join(" ");
  }
  return fallback;
}

export default function QuestionBankDetailPage() {
  const params = useParams<{ bankId: string }>();
  const bankId = params.bankId;
  const router = useRouter();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [editingQuestion, setEditingQuestion] = useState<Question | null>(null);
  const [imagePreviews, setImagePreviews] = useState<Record<number, { prompt?: string; expected?: string }>>({});
  const [bankName, setBankName] = useState("Question Bank");
  const [text, setText] = useState("");
  const [type, setType] = useState("MCQ");
  const [difficulty, setDifficulty] = useState("easy");
  const [subject, setSubject] = useState("");
  const [marks, setMarks] = useState("1");
  const [expected, setExpected] = useState("");
  const [optionTexts, setOptionTexts] = useState(["", "", "", ""]);
  const [correct, setCorrect] = useState<string[]>(["0"]);
  const [questionImage, setQuestionImage] = useState<File | null>(null);
  const [expectedAnswerImage, setExpectedAnswerImage] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const headers = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return null;
    }
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  }, [router]);

  const load = useCallback(async () => {
    const auth = headers();
    if (!auth) return;
    const [banksRes, questionsRes] = await Promise.all([
      fetch(`${API_URL}/question-banks`, { headers: auth }),
      fetch(`${API_URL}/question-banks/${bankId}/questions`, { headers: auth }),
    ]);
    if (!banksRes.ok || !questionsRes.ok) {
      throw new Error("Unable to load this question bank.");
    }
    const banks = await banksRes.json();
    const bank = banks.find((item: { id: number; name: string }) => item.id === Number(bankId));
    if (!bank) throw new Error("You can manage only question banks you created.");
    setBankName(bank.name);
    const loadedQuestions: Question[] = await questionsRes.json();
    setQuestions(loadedQuestions);
    const previews: Record<number, { prompt?: string; expected?: string }> = {};
    await Promise.all(loadedQuestions.map(async (question) => {
      const fetchPreview = async (url: string) => {
        const response = await fetch(url, { headers: auth });
        return response.ok ? URL.createObjectURL(await response.blob()) : undefined;
      };
      const [prompt, expected] = await Promise.all([
        question.question_image_available
          ? fetchPreview(API_URL + "/questions/" + question.id + "/image")
          : Promise.resolve(undefined),
        question.expected_answer_image_available
          ? fetchPreview(API_URL + "/questions/" + question.id + "/expected-answer-image")
          : Promise.resolve(undefined),
      ]);
      previews[question.id] = { prompt, expected };
    }));
    setImagePreviews(previews);
  }, [bankId, headers]);

  useEffect(() => {
    load().catch((loadError) => setError(loadError.message));
  }, [load]);

  useEffect(() => () => {
    Object.values(imagePreviews).forEach((preview) => {
      if (preview.prompt) URL.revokeObjectURL(preview.prompt);
      if (preview.expected) URL.revokeObjectURL(preview.expected);
    });
  }, [imagePreviews]);

  function changeType(nextType: string) {
    setType(nextType);
    if (nextType === "MCQ" && correct.length !== 1) setCorrect(["0"]);
    if (nextType === "multi_select" && correct.length === 0) setCorrect(["0"]);
  }

  function addOption() {
    setOptionTexts((current) => [...current, ""]);
  }

  function removeOption(index: number) {
    if (optionTexts.length <= 2) return;
    setOptionTexts((current) => current.filter((_, optionIndex) => optionIndex !== index));
    setCorrect((current) =>
      current
        .filter((value) => Number(value) !== index)
        .map((value) => String(Number(value) > index ? Number(value) - 1 : Number(value)))
    );
  }

  function toggleCorrect(index: number) {
    setCorrect((current) => {
      if (type === "MCQ") return [String(index)];
      return current.includes(String(index))
        ? current.filter((value) => value !== String(index))
        : [...current, String(index)];
    });
  }

  async function addQuestion(event: FormEvent) {
    event.preventDefault();
    setError("");

    const isChoice = type === "MCQ" || type === "multi_select";
    if (!text.trim() && !questionImage) {
      setError("Enter question text or upload a question image.");
      return;
    }
    if (isChoice) {
      if (optionTexts.length < 2 || optionTexts.some((option) => !option.trim())) {
        setError("Add at least two options and fill in every option.");
        return;
      }
      if (new Set(optionTexts.map((option) => option.trim().toLocaleLowerCase())).size !== optionTexts.length) {
        setError("Duplicate options are not allowed.");
        return;
      }
      if (correct.length === 0) {
        setError("Select at least one correct answer.");
        return;
      }
    }

    setWorking(true);
    try {
      const auth = headers();
      if (!auth) return;

      const payload = {
        question_text: text.trim() || null,
        question_type: type,
        subject: subject.trim(),
        difficulty,
        options: isChoice ? optionTexts.map((option) => option.trim()) : [],
        expected_answer: expected.trim() || null,
        marks: Number(marks),
        negative_marks: 0,
        correct_option_index: type === "MCQ" ? Number(correct[0]) : null,
        correct_option_indices: type === "multi_select" ? correct.map(Number) : null,
      };

      if (editingQuestion) {
        const response = await fetch(
          `${API_URL}/question-banks/${bankId}/questions/${editingQuestion.id}`,
          { method: "PATCH", headers: auth, body: JSON.stringify({
            ...payload,
            model_answer_text: editingQuestion.model_answer_text || null,
            tags: editingQuestion.tags || [],
          }) }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(errorMessage(data.detail, "Unable to update question."));
        }

        if (questionImage) {
          const imageForm = new FormData();
          imageForm.append("file", questionImage);
          const imageResponse = await fetch(`${API_URL}/questions/${editingQuestion.id}/image`, {
            method: "POST",
            headers: { Authorization: auth.Authorization },
            body: imageForm,
          });
          const imageData = await imageResponse.json().catch(() => ({}));
          if (!imageResponse.ok) {
            throw new Error(errorMessage(imageData.detail, "Question text was updated, but the prompt image could not be saved."));
          }
        }

        if (expectedAnswerImage) {
          const imageForm = new FormData();
          imageForm.append("file", expectedAnswerImage);
          const imageResponse = await fetch(`${API_URL}/questions/${editingQuestion.id}/expected-answer-image`, {
            method: "POST",
            headers: { Authorization: auth.Authorization },
            body: imageForm,
          });
          const imageData = await imageResponse.json().catch(() => ({}));
          if (!imageResponse.ok) {
            throw new Error(errorMessage(imageData.detail, "Question was updated, but the expected-answer image could not be saved."));
          }
        }
      } else {
        const formData = new FormData();
        formData.append("question_data", JSON.stringify(payload));
        if (questionImage) formData.append("question_image", questionImage);
        if (expectedAnswerImage) formData.append("expected_answer_image", expectedAnswerImage);

        const response = await fetch(
          `${API_URL}/question-banks/${bankId}/questions/with-images`,
          { method: "POST", headers: { Authorization: auth.Authorization }, body: formData }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(errorMessage(data.detail, "Unable to add question."));
        }
      }

      setEditingQuestion(null);
      setText("");
      setExpected("");
      setOptionTexts(["", "", "", ""]);
      setCorrect(["0"]);
      setQuestionImage(null);
      setExpectedAnswerImage(null);
      const promptInput = document.getElementById("question-image-file") as HTMLInputElement | null;
      const answerInput = document.getElementById("expected-answer-image-file") as HTMLInputElement | null;
      if (promptInput) promptInput.value = "";
      if (answerInput) answerInput.value = "";
      await load();
    } catch (addError) {
      setError(addError instanceof Error ? addError.message : "Unable to add question.");
    } finally {
      setWorking(false);
    }
  }

  function editQuestion(question: Question) {
    setEditingQuestion(question);
    setText(question.question_text || "");
    setType(question.question_type);
    setDifficulty(question.difficulty);
    setSubject(question.subject || "");
    setMarks(String(question.marks));
    setExpected(question.expected_answer || "");
    setOptionTexts(
      question.options.length
        ? question.options.map((option) => option.option_text)
        : ["", "", "", ""]
    );
    const selectedCorrect = question.options
      .map((option, index) => option.is_correct ? String(index) : null)
      .filter((value): value is string => value !== null);
    setCorrect(selectedCorrect.length ? selectedCorrect : ["0"]);
    setQuestionImage(null);
    setExpectedAnswerImage(null);
    const promptInput = document.getElementById("question-image-file") as HTMLInputElement | null;
    const answerInput = document.getElementById("expected-answer-image-file") as HTMLInputElement | null;
    if (promptInput) promptInput.value = "";
    if (answerInput) answerInput.value = "";
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelEdit() {
    setEditingQuestion(null);
    setText("");
    setExpected("");
    setOptionTexts(["", "", "", ""]);
    setCorrect(["0"]);
    setQuestionImage(null);
    setExpectedAnswerImage(null);
    const promptInput = document.getElementById("question-image-file") as HTMLInputElement | null;
    const answerInput = document.getElementById("expected-answer-image-file") as HTMLInputElement | null;
    if (promptInput) promptInput.value = "";
    if (answerInput) answerInput.value = "";
  }

  async function removeQuestion(id: number) {
    if (!window.confirm("Delete this question from your question banks? Any existing examination copy will stay unchanged.")) return;
    const auth = headers();
    if (!auth) return;
    const response = await fetch(`${API_URL}/question-banks/${bankId}/questions/${id}/delete`, {
      method: "DELETE", headers: auth,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(errorMessage(data.detail, "Unable to delete question."));
      return;
    }
    await load();
  }

  const choice = type === "MCQ" || type === "multi_select";

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
        <div className="mx-auto flex max-w-6xl justify-between">
          <div>
            <Link href="/examiner/question-banks" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="text-sm text-slate-400">Manage Questions</p>
          </div>
          <Link href="/examiner/question-banks" className="rounded-lg border border-white/20 px-4 py-2 text-sm">
            All Banks
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-6xl space-y-8 px-6 py-10">
        <div>
          <h1 className="text-3xl font-bold">{bankName}</h1>
          <p className="mt-2 text-slate-400">Add questions now and use them in examinations later.</p>
        </div>

        {error && <p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}

        <form onSubmit={addQuestion} className="space-y-5 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold">{editingQuestion ? "Edit Question" : "Add a Question"}</h2>

          <div>
            <label htmlFor="question-text" className="mb-2 block text-sm font-medium">
              Question text <span className="text-slate-400">(optional if you upload a question image)</span>
            </label>
            <textarea
              id="question-text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={3}
              placeholder="Write your question"
              className="w-full rounded-lg border border-slate-700 bg-slate-800 p-3"
            />
          </div>

          <div className="rounded-xl border border-dashed border-slate-600 p-4">
            <label htmlFor="question-image-file" className="block text-sm font-medium">
              Question prompt image <span className="text-slate-400">(optional)</span>
            </label>
            <input
              id="question-image-file"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp"
              onChange={(event) => setQuestionImage(event.target.files?.[0] || null)}
              className="mt-2 block w-full text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-white"
            />
            {questionImage && <p className="mt-2 text-xs text-green-300">Selected: {questionImage.name}</p>}
            {editingQuestion?.question_image_available && !questionImage && <p className="mt-2 text-xs text-blue-300">An existing prompt image is saved. Upload a new image only if you want to replace it.</p>}
            <p className="mt-1 text-xs text-slate-400">Enter text, upload an image, or provide both. At least one is required.</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <label className="text-sm">
              Question type
              <select value={type} onChange={(event) => changeType(event.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3">
                <option value="MCQ">MCQ</option>
                <option value="multi_select">Multiple select</option>
                <option value="short_answer">Short answer</option>
                <option value="long_answer">Long answer</option>
                <option value="image_upload">Image upload answer</option>
              </select>
            </label>
            <label className="text-sm">
              Difficulty
              <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3">
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>
            <label className="text-sm">
              Subject
              <input required value={subject} onChange={(event) => setSubject(event.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3" />
            </label>
          </div>

          <label className="block text-sm">
            Maximum marks
            <input required type="number" min="0.01" step="0.01" value={marks} onChange={(event) => setMarks(event.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3" />
          </label>

          {choice && (
            <section className="space-y-3 rounded-xl border border-white/10 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold">Answer options</h3>
                  <p className="text-xs text-slate-400">
                    Four options are provided by default. {type === "MCQ" ? "Choose one correct answer." : "Choose one or more correct answers."}
                  </p>
                </div>
                <button type="button" onClick={addOption} className="rounded-lg border border-blue-400/40 px-3 py-2 text-sm text-blue-300">
                  + Add option
                </button>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {optionTexts.map((value, index) => (
                  <div key={index} className="rounded-lg bg-slate-800 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <label htmlFor={`option-${index}`} className="text-sm font-medium">Option {index + 1}</label>
                      <button
                        type="button"
                        onClick={() => removeOption(index)}
                        disabled={optionTexts.length <= 2}
                        className="text-xs text-red-300 disabled:cursor-not-allowed disabled:opacity-30"
                      >
                        Remove
                      </button>
                    </div>
                    <input
                      id={`option-${index}`}
                      required
                      value={value}
                      onChange={(event) => setOptionTexts((old) => old.map((item, itemIndex) => itemIndex === index ? event.target.value : item))}
                      className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 p-3"
                    />
                    <label className="mt-3 flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type={type === "MCQ" ? "radio" : "checkbox"}
                        name="correct-answer"
                        checked={correct.includes(String(index))}
                        onChange={() => toggleCorrect(index)}
                      />
                      Correct answer
                    </label>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div>
            <label htmlFor="expected-answer" className="block text-sm font-medium">
              Expected answer <span className="text-slate-400">(optional)</span>
            </label>
            <textarea
              id="expected-answer"
              value={expected}
              onChange={(event) => setExpected(event.target.value)}
              rows={3}
              placeholder="Type the expected/model answer (optional)"
              className="mt-2 w-full rounded-lg bg-slate-800 p-3"
            />
            <label htmlFor="expected-answer-image-file" className="mt-3 block text-sm">
              Expected-answer image <span className="text-slate-400">(optional)</span>
            </label>
            <input
              id="expected-answer-image-file"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp"
              onChange={(event) => setExpectedAnswerImage(event.target.files?.[0] || null)}
              className="mt-2 block w-full text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-white"
            />
            {expectedAnswerImage && <p className="mt-2 text-xs text-green-300">Selected: {expectedAnswerImage.name}</p>}
            {editingQuestion?.expected_answer_image_available && !expectedAnswerImage && <p className="mt-2 text-xs text-emerald-300">An existing expected-answer image is saved. Upload a new image only if you want to replace it.</p>}
            <p className="mt-1 text-xs text-slate-400">You may provide text, an image, both, or neither.</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button disabled={working} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold disabled:opacity-50">
              {working ? "Saving..." : editingQuestion ? "Save Changes" : "Add Question"}
            </button>
            {editingQuestion && <button type="button" onClick={cancelEdit} className="rounded-lg border border-white/20 px-5 py-3" disabled={working}>Cancel Edit</button>}
          </div>
        </form>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Questions in this bank ({questions.length})</h2>
          {questions.length === 0 ? (
            <p className="rounded-xl border border-white/10 p-6 text-slate-400">No questions have been added yet.</p>
          ) : questions.map((question) => (
            <article key={question.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-white/10 bg-slate-900 p-5">
              <div className="min-w-0 flex-1">
                <p className="text-xs text-cyan-300">{question.question_type} · {question.difficulty} · {question.marks} marks</p>
                {question.question_text && <p className="mt-2 whitespace-pre-wrap">{question.question_text}</p>}
                {question.question_image_available && (
                  <div className="mt-3">
                    <p className="text-xs text-blue-300">Question prompt image</p>
                    {imagePreviews[question.id]?.prompt && (
                      <img src={imagePreviews[question.id].prompt} alt="Question prompt" className="mt-2 max-h-48 max-w-full rounded-lg border border-white/10 bg-white object-contain" />
                    )}
                  </div>
                )}
                {question.expected_answer && <p className="mt-2 text-sm text-slate-300">Expected answer: {question.expected_answer}</p>}
                {question.expected_answer_image_available && (
                  <div className="mt-3">
                    <p className="text-xs text-emerald-300">Expected-answer image</p>
                    {imagePreviews[question.id]?.expected && (
                      <img src={imagePreviews[question.id].expected} alt="Expected answer" className="mt-2 max-h-48 max-w-full rounded-lg border border-white/10 bg-white object-contain" />
                    )}
                  </div>
                )}
                {question.options?.map((option) => (
                  <p key={option.id} className="mt-1 text-sm text-slate-400">{option.option_text}{option.is_correct ? " (Correct)" : ""}</p>
                ))}
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => editQuestion(question)} className="rounded-lg border border-white/20 px-3 py-2 text-sm">Edit</button>
                <button type="button" onClick={() => removeQuestion(question.id)} className="rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-300">Delete</button>
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}

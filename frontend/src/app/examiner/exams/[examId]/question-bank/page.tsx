"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type QuestionType = "MCQ" | "multi_select" | "short_answer" | "long_answer" | "image_upload";
type Difficulty = "easy" | "medium" | "hard";

interface BankQuestion {
  question_id: number;
  question_order: number;
  question_text: string;
  question_type: QuestionType;
  subject?: string | null;
  difficulty: Difficulty;
  marks: number;
  question_time_limit_seconds?: number | null;
}
interface SourceQuestion {
  question_id: number;
  question_text: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  marks: number;
}
interface SourceBank {
  source_exam_id: number;
  source_exam_title: string;
  subject?: string | null;
  questions: SourceQuestion[];
}
interface Student {
  id: number;
  full_name: string;
  email: string;
}
interface AssignedStudent extends Student {
  student_id: number;
}

const fieldClass = "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-500";
const cardClass = "rounded-2xl border border-white/10 bg-slate-900 p-5";

export default function ExamQuestionBankPage() {
  const params = useParams<{ examId: string }>();
  const router = useRouter();
  const examId = String(params.examId || "");

  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [sourceBanks, setSourceBanks] = useState<SourceBank[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [assignedStudents, setAssignedStudents] = useState<AssignedStudent[]>([]);
  const [selectedSources, setSelectedSources] = useState<number[]>([]);
  const [selectedStudents, setSelectedStudents] = useState<number[]>([]);
  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] = useState<QuestionType>("MCQ");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [marks, setMarks] = useState("1");
  const [negativeMarks, setNegativeMarks] = useState("0");
  const [subject, setSubject] = useState("");
  const [expectedAnswer, setExpectedAnswer] = useState("");
  const [modelAnswer, setModelAnswer] = useState("");
  const [options, setOptions] = useState(["", "", "", ""]);
  const [correctOption, setCorrectOption] = useState("0");
  const [correctOptions, setCorrectOptions] = useState<number[]>([0]);
  const [promptImage, setPromptImage] = useState<File | null>(null);
  const [filterType, setFilterType] = useState("all");
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return null;
    }
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  }, [router]);

  const request = useCallback(async (url: string, init: RequestInit = {}) => {
    const headers = getHeaders();
    if (!headers) throw new Error("Your session has expired. Please sign in again.");
    const response = await fetch(`${API_URL}${url}`, {
      ...init,
      headers: { ...headers, ...(init.headers || {}) },
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 || response.status === 403) {
      if (response.status === 401) router.replace("/login");
    }
    if (!response.ok) throw new Error(data.detail || "The request could not be completed.");
    return data;
  }, [getHeaders, router]);

  const loadAll = useCallback(async () => {
    if (!/^\d+$/.test(examId)) {
      setError("Invalid examination ID.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [bank, sources, eligible, assigned] = await Promise.all([
        request(`/exams/${examId}/questions`),
        request(`/exams/${examId}/question-bank/sources`),
        request(`/exams/${examId}/eligible-students`),
        request(`/exams/${examId}/assignments`),
      ]);
      setQuestions(Array.isArray(bank.questions) ? bank.questions : []);
      setSourceBanks(Array.isArray(sources.banks) ? sources.banks : []);
      setStudents(Array.isArray(eligible.students) ? eligible.students : []);
      setAssignedStudents(Array.isArray(assigned.students) ? assigned.students : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the question bank.");
    } finally {
      setLoading(false);
    }
  }, [examId, request]);

  useEffect(() => { void loadAll(); }, [loadAll]);

  const filteredQuestions = useMemo(() => questions.filter((question) =>
    (filterType === "all" || question.question_type === filterType) &&
    (filterDifficulty === "all" || question.difficulty === filterDifficulty)
  ), [questions, filterType, filterDifficulty]);

  function toggleSource(id: number) {
    setSelectedSources((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  }
  function toggleStudent(id: number) {
    setSelectedStudents((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  }
  function toggleCorrect(index: number) {
    setCorrectOptions((current) => current.includes(index) ? current.filter((value) => value !== index) : [...current, index]);
  }

  async function addQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const objective = questionType === "MCQ" || questionType === "multi_select";
    const cleanedOptions = options.map((item) => item.trim());
    if (!questionText.trim() || !subject.trim()) {
      setError("Enter the question and subject.");
      return;
    }
    if (objective && (cleanedOptions.some((item) => !item) || cleanedOptions.length < 2)) {
      setError("Complete all four objective options.");
      return;
    }
    if (questionType === "MCQ" && !Number.isInteger(Number(correctOption))) {
      setError("Choose the correct option.");
      return;
    }
    if (questionType === "multi_select" && correctOptions.length === 0) {
      setError("Select at least one correct option.");
      return;
    }
    setWorking(true);
    try {
      const payload: Record<string, unknown> = {
        question_text: questionText.trim(),
        question_type: questionType,
        subject: subject.trim(),
        difficulty,
        marks: Number(marks),
        negative_marks: Number(negativeMarks),
        expected_answer: expectedAnswer.trim() || null,
        model_answer_text: modelAnswer.trim() || null,
      };
      if (objective) payload.options = cleanedOptions;
      if (questionType === "MCQ") payload.correct_option_index = Number(correctOption);
      if (questionType === "multi_select") payload.correct_option_indices = correctOptions;
      const created = await request(`/exams/${examId}/questions`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (promptImage) {
        const form = new FormData();
        form.append("file", promptImage);
        const headers = getHeaders();
        if (!headers) return;
        const imageResponse = await fetch(`${API_URL}/questions/${created.question_id}/image`, {
          method: "POST",
          headers: { Authorization: headers.Authorization },
          body: form,
        });
        const imageData = await imageResponse.json().catch(() => ({}));
        if (!imageResponse.ok) throw new Error(imageData.detail || "Question saved, but its prompt image upload failed.");
      }
      setQuestionText("");
      setExpectedAnswer("");
      setModelAnswer("");
      setOptions(["", "", "", ""]);
      setPromptImage(null);
      setMessage("Question added to this examination bank.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add question.");
    } finally {
      setWorking(false);
    }
  }

  async function reuseSelected() {
    if (!selectedSources.length) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}/question-bank/reuse`, {
        method: "POST",
        body: JSON.stringify({ question_ids: selectedSources }),
      });
      setSelectedSources([]);
      setMessage("Selected questions copied as independent snapshots. Changes to source questions will not affect this exam.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reuse selected questions.");
    } finally { setWorking(false); }
  }

  async function removeQuestion(questionId: number) {
    if (!window.confirm("Remove this question from this examination bank? Original/source questions will be preserved.")) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}/questions/${questionId}`, { method: "DELETE" });
      setMessage("Question removed from this examination bank.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove question.");
    } finally { setWorking(false); }
  }

  async function deleteEntireBank() {
    if (!window.confirm("Delete the entire question bank for this examination? Shared source questions and questions used by other exams will be preserved. This cannot be undone.")) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}/question-bank`, { method: "DELETE" });
      setMessage("This examination's question bank has been deleted.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete the question bank.");
    } finally { setWorking(false); }
  }

  async function saveTimer(questionId: number, secondsValue: string) {
    setWorking(true); setError(""); setMessage("");
    try {
      const seconds = secondsValue.trim() ? Number(secondsValue) : null;
      await request(`/exams/${examId}/questions/${questionId}/timer`, {
        method: "PATCH",
        body: JSON.stringify({ seconds }),
      });
      setMessage("Question timer saved.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save question timer.");
    } finally { setWorking(false); }
  }

  async function assignSelectedStudents() {
    if (!selectedStudents.length) {
      setError("Select at least one student.");
      return;
    }
    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}/assignments`, {
        method: "POST",
        body: JSON.stringify({ student_ids: selectedStudents }),
      });
      setSelectedStudents([]);
      setMessage("Examination assigned to the selected students.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to assign students.");
    } finally { setWorking(false); }
  }

  async function removeAssignment(studentId: number) {
    if (!window.confirm("Remove this student's examination assignment?")) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}/assignments/${studentId}`, { method: "DELETE" });
      setMessage("Student assignment removed.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove assignment.");
    } finally { setWorking(false); }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link href="/examiner/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-cyan-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Examination / Question Bank</p>
          </div>
          <Link href="/examiner/exams" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Examinations</Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-8 px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Examination Question Bank</h1>
            <p className="mt-2 text-slate-400">Add new questions, copy questions from earlier banks, set timers, and assign students.</p>
          </div>
          <button onClick={deleteEntireBank} disabled={working || questions.length === 0} className="rounded-lg border border-red-500/50 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 disabled:opacity-40">Delete Entire Bank</button>
        </div>

        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
        {message && <div role="status" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">{message}</div>}

        <section className={cardClass}>
          <h2 className="text-xl font-semibold">Add a New Question</h2>
          <form onSubmit={addQuestion} className="mt-5 space-y-4">
            <textarea required value={questionText} onChange={(e) => setQuestionText(e.target.value)} placeholder="Write the question..." rows={3} className={fieldClass} />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <label className="text-sm text-slate-300">Question type
                <select value={questionType} onChange={(e) => setQuestionType(e.target.value as QuestionType)} className={fieldClass}>
                  <option value="MCQ">MCQ</option><option value="multi_select">Multiple select</option><option value="short_answer">Short answer</option><option value="long_answer">Long answer</option><option value="image_upload">Image upload</option>
                </select>
              </label>
              <label className="text-sm text-slate-300">Difficulty
                <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)} className={fieldClass}>
                  <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                </select>
              </label>
              <label className="text-sm text-slate-300">Subject
                <input required value={subject} onChange={(e) => setSubject(e.target.value)} className={fieldClass} />
              </label>
              <label className="text-sm text-slate-300">Maximum marks
                <input required type="number" min="0.01" step="0.01" value={marks} onChange={(e) => setMarks(e.target.value)} className={fieldClass} />
              </label>
              <label className="text-sm text-slate-300">Negative marks
                <input type="number" min="0" step="0.01" value={negativeMarks} onChange={(e) => setNegativeMarks(e.target.value)} className={fieldClass} />
              </label>
            </div>
            {(questionType === "MCQ" || questionType === "multi_select") && (
              <div className="grid gap-3 sm:grid-cols-2">
                {options.map((option, index) => (
                  <div key={index} className="rounded-lg border border-white/10 bg-slate-800/60 p-3">
                    <input value={option} onChange={(e) => setOptions((old) => old.map((v, i) => i === index ? e.target.value : v))} placeholder={`Option ${index + 1}`} className={fieldClass} />
                    <label className="mt-2 flex items-center gap-2 text-xs text-slate-300">
                      <input type={questionType === "MCQ" ? "radio" : "checkbox"} name="correct-option" checked={questionType === "MCQ" ? correctOption === String(index) : correctOptions.includes(index)} onChange={() => questionType === "MCQ" ? setCorrectOption(String(index)) : toggleCorrect(index)} />
                      Correct answer
                    </label>
                  </div>
                ))}
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm text-slate-300">Expected answer
                <textarea value={expectedAnswer} onChange={(e) => setExpectedAnswer(e.target.value)} rows={2} className={fieldClass} />
              </label>
              <label className="text-sm text-slate-300">Model answer
                <textarea value={modelAnswer} onChange={(e) => setModelAnswer(e.target.value)} rows={2} className={fieldClass} />
              </label>
            </div>
            <label className="block text-sm text-slate-300">Optional question prompt image
              <input type="file" accept="image/png,image/jpeg,image/webp,image/tiff,image/bmp" onChange={(e) => setPromptImage(e.target.files?.[0] || null)} className="mt-2 block w-full text-sm text-slate-300" />
            </label>
            <button disabled={working} className="rounded-lg bg-cyan-600 px-5 py-2.5 font-semibold hover:bg-cyan-500 disabled:opacity-50">{working ? "Saving..." : "Add Question"}</button>
          </form>
        </section>

        <section className={cardClass}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="text-xl font-semibold">Current Question Bank</h2><p className="mt-1 text-sm text-slate-400">{questions.length} question(s)</p></div>
            <div className="flex gap-2">
              <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className={fieldClass + " w-auto"}><option value="all">All types</option><option value="MCQ">MCQ</option><option value="multi_select">Multiple select</option><option value="short_answer">Short answer</option><option value="long_answer">Long answer</option><option value="image_upload">Image upload</option></select>
              <select value={filterDifficulty} onChange={(e) => setFilterDifficulty(e.target.value)} className={fieldClass + " w-auto"}><option value="all">All levels</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select>
            </div>
          </div>
          {loading ? <p className="py-8 text-slate-400">Loading bank...</p> : filteredQuestions.length === 0 ? <p className="py-8 text-slate-400">No questions match this filter.</p> : (
            <div className="mt-5 space-y-3">
              {filteredQuestions.map((question) => (
                <article key={question.question_id} className="rounded-xl border border-white/10 bg-slate-800/50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-cyan-300">Q{question.question_order} · {question.question_type} · {question.difficulty} · {question.marks} marks</p>
                      <p className="mt-2 whitespace-pre-wrap">{question.question_text}</p>
                    </div>
                    <button onClick={() => removeQuestion(question.question_id)} disabled={working} className="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-40">Remove</button>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <label className="text-xs text-slate-400">Question timer (seconds; blank = no separate limit)
                      <input key={`timer-${question.question_id}-${question.question_time_limit_seconds}`} type="number" min="1" max="7200" defaultValue={question.question_time_limit_seconds ?? ""} onBlur={(e) => void saveTimer(question.question_id, e.target.value)} className="ml-2 w-28 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white" />
                    </label>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className={cardClass}>
          <h2 className="text-xl font-semibold">Reuse Previous Question Banks</h2>
          <p className="mt-1 text-sm text-slate-400">Choose questions from earlier examinations. Each selected question is copied into this bank, so later edits to the source will not alter this exam.</p>
          {sourceBanks.length === 0 ? <p className="py-6 text-sm text-slate-400">No reusable question banks are available.</p> : (
            <div className="mt-4 space-y-4">
              {sourceBanks.map((bank) => (
                <div key={bank.source_exam_id} className="rounded-xl border border-white/10 p-4">
                  <h3 className="font-semibold">{bank.source_exam_title}</h3>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {bank.questions.map((question) => (
                      <label key={question.question_id} className="flex items-start gap-3 rounded-lg bg-slate-800/60 p-3 text-sm">
                        <input type="checkbox" checked={selectedSources.includes(question.question_id)} onChange={() => toggleSource(question.question_id)} className="mt-1" />
                        <span><span className="block">{question.question_text}</span><span className="mt-1 block text-xs text-slate-400">{question.question_type} · {question.difficulty} · {question.marks} marks</span></span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
              <button onClick={reuseSelected} disabled={working || selectedSources.length === 0} className="rounded-lg bg-violet-600 px-5 py-2.5 font-semibold hover:bg-violet-500 disabled:opacity-50">Copy Selected Questions ({selectedSources.length})</button>
            </div>
          )}
        </section>

        <section className={cardClass}>
          <h2 className="text-xl font-semibold">Assign Students</h2>
          <p className="mt-1 text-sm text-slate-400">Only assigned students can see and start this examination.</p>
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {students.map((student) => (
              <label key={student.id} className="flex items-center gap-3 rounded-lg bg-slate-800/60 p-3 text-sm">
                <input type="checkbox" checked={selectedStudents.includes(student.id)} onChange={() => toggleStudent(student.id)} />
                <span>{student.full_name}<span className="block text-xs text-slate-400">{student.email}</span></span>
              </label>
            ))}
          </div>
          {students.length === 0 && <p className="py-5 text-sm text-slate-400">No active Student accounts are available.</p>}
          <button onClick={assignSelectedStudents} disabled={working || selectedStudents.length === 0} className="mt-4 rounded-lg bg-cyan-600 px-5 py-2.5 font-semibold hover:bg-cyan-500 disabled:opacity-50">Assign Selected Students ({selectedStudents.length})</button>
          <div className="mt-6 border-t border-white/10 pt-5">
            <h3 className="font-semibold">Currently Assigned ({assignedStudents.length})</h3>
            <div className="mt-3 space-y-2">
              {assignedStudents.map((student) => (
                <div key={student.student_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-800/50 p-3 text-sm">
                  <span>{student.full_name}<span className="ml-2 text-xs text-slate-400">{student.email}</span></span>
                  <button onClick={() => removeAssignment(student.student_id)} disabled={working} className="text-xs text-red-300 hover:underline disabled:opacity-40">Remove assignment</button>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

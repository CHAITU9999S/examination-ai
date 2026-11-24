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
  negative_marks?: number;
  tags?: string[];
  expected_answer?: string | null;
  model_answer_text?: string | null;
  question_image_available?: boolean;
  options?: { id: number; option_text: string; is_correct: boolean }[];
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
  is_active: boolean;
  session_status?: string | null;
}
interface ExamConfiguration {
  title: string;
  subject: string;
  duration_minutes: number;
  total_questions: number;
  randomize_questions: boolean;
  selection_rules: Record<string, unknown>;
  start_time: string;
  end_time: string;
  negative_marking: boolean;
  proctoring_enabled: boolean;
  gaze_tracking_sensitivity: number | null;
  max_tab_switch_warnings: number | null;
  can_edit: boolean;
  created_by_name?: string;
  created_by_role?: string;
}
interface ConfigRevision {
  revision_number: number;
  configuration: Record<string, unknown>;
  changed_by: number;
  created_at: string;
}
interface QuestionMarksRevision {
  revision_number: number;
  marks_snapshot: Record<string, number>;
  changed_by: number;
  created_at: string;
}

const INDIA_TIME_ZONE = "Asia/Kolkata";

function toISTDateTimeLocal(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const istDate = new Date(date.getTime() + 330 * 60 * 1000);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${istDate.getUTCFullYear()}-${pad(istDate.getUTCMonth() + 1)}-${pad(istDate.getUTCDate())}T${pad(istDate.getUTCHours())}:${pad(istDate.getUTCMinutes())}`;
}

function istDateTimeToIso(value: string) {
  const withSeconds = value.length === 16 ? `${value}:00` : value;
  const date = new Date(`${withSeconds}+05:30`);
  if (Number.isNaN(date.getTime())) throw new Error("Enter a valid IST schedule time.");
  return date.toISOString();
}

const configDifficulties = ["easy", "medium", "hard"] as const;
const configQuestionTypes = ["MCQ", "multi_select", "short_answer", "long_answer", "image_upload"] as const;
const defaultConfigGroupCounts: Record<string, string> = Object.fromEntries(
  configDifficulties.flatMap((difficulty) =>
    configQuestionTypes.map((type) => [`${difficulty}|${type}`, "0"])
  )
);
const fieldClass = "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-500";
const cardClass = "rounded-2xl border border-white/10 bg-slate-900 p-5";

export default function ExamQuestionBankPage() {
  const params = useParams<{ examId: string }>();
  const router = useRouter();
  const examId = String(params.examId || "");

  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [examConfig, setExamConfig] = useState<ExamConfiguration | null>(null);
  const [configRevisions, setConfigRevisions] = useState<ConfigRevision[]>([]);
  const [revisionsUsed, setRevisionsUsed] = useState(0);
  const [questionMarksByGroup, setQuestionMarksByGroup] = useState<Record<string, string>>({});
  const [questionMarksRevisions, setQuestionMarksRevisions] = useState<QuestionMarksRevision[]>([]);
  const [questionMarksRevisionsUsed, setQuestionMarksRevisionsUsed] = useState(0);
  const [questionMarksCanEdit, setQuestionMarksCanEdit] = useState(false);
  const [questionMarksLocked, setQuestionMarksLocked] = useState(false);
  const [useConfigGroupCounts, setUseConfigGroupCounts] = useState(false);
  const [configGroupCounts, setConfigGroupCounts] = useState<Record<string, string>>(defaultConfigGroupCounts);
  const [staffRole, setStaffRole] = useState<"admin" | "examiner">("examiner");
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
  const [tags, setTags] = useState("");
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
  const [validationMessage, setValidationMessage] = useState("");

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
      const [profile, bank, config, marksSettings] = await Promise.all([
        request("/users/me"),
        request(`/exams/${examId}/questions`),
        request(`/exams/${examId}`),
        request(`/exams/${examId}/question-marks`),
      ]);
      setStaffRole(profile.role === "admin" ? "admin" : "examiner");
      setExamConfig({
        ...config,
        subject: config.subject || "",
        start_time: toISTDateTimeLocal(config.start_time),
        end_time: toISTDateTimeLocal(config.end_time),
      });
      setSubject(config.subject || "");
      const savedGroupCounts = config.selection_rules?.group_counts as Record<string, number> | undefined;
      setUseConfigGroupCounts(Boolean(savedGroupCounts));
      setConfigGroupCounts({
        ...defaultConfigGroupCounts,
        ...(savedGroupCounts
          ? Object.fromEntries(Object.entries(savedGroupCounts).map(([key, value]) => [key, String(value)]))
          : {}),
      });
      setQuestionMarksByGroup(
        Object.fromEntries(
          Object.entries(marksSettings.marks_by_group || {}).map(([key, value]) => [key, String(value)])
        )
      );
      setQuestionMarksRevisions(Array.isArray(marksSettings.revisions) ? marksSettings.revisions : []);
      setQuestionMarksRevisionsUsed(Number(marksSettings.revisions_used || 0));
      setQuestionMarksCanEdit(Boolean(marksSettings.can_edit));
      setQuestionMarksLocked(Boolean(marksSettings.has_sessions));
      setQuestions(Array.isArray(bank.questions) ? bank.questions : []);

      if (!config.can_edit) {
        setConfigRevisions([]);
        setRevisionsUsed(0);
        setSourceBanks([]);
        setStudents([]);
        setAssignedStudents([]);
        return;
      }

      const [sources, eligible, assigned, revisions] = await Promise.all([
        request(`/exams/${examId}/question-bank/sources`),
        request(`/exams/${examId}/eligible-students`),
        request(`/exams/${examId}/assignments`),
        request(`/exams/${examId}/configuration-revisions`),
      ]);
      setConfigRevisions(Array.isArray(revisions.revisions) ? revisions.revisions : []);
      setRevisionsUsed(Number(revisions.revisions_used || 0));
      setSourceBanks(Array.isArray(sources.banks) ? sources.banks : []);
      setStudents(Array.isArray(eligible.students) ? eligible.students : []);
      setAssignedStudents(Array.isArray(assigned.students) ? assigned.students : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the examination.");
    } finally {
      setLoading(false);
    }
  }, [examId, request]);

  useEffect(() => { void loadAll(); }, [loadAll]);

  const filteredQuestions = useMemo(() => questions.filter((question) =>
    (filterType === "all" || question.question_type === filterType) &&
    (filterDifficulty === "all" || question.difficulty === filterDifficulty)
  ), [questions, filterType, filterDifficulty]);

  const questionMarkGroups = useMemo(() => {
    const groups: Record<string, { questionType: QuestionType; difficulty: Difficulty; count: number }> = {};
    for (const question of questions) {
      const key = `${question.difficulty}|${question.question_type}`;
      if (!groups[key]) {
        groups[key] = {
          questionType: question.question_type,
          difficulty: question.difficulty,
          count: 0,
        };
      }
      groups[key].count += 1;
    }
    return Object.entries(groups).map(([key, group]) => ({ key, ...group }));
  }, [questions]);

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
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
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
      setTags("");
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
      setMessage("Selected question content and answers were copied as independent snapshots. Source marks were not copied; set the maximum marks for this examination in Question Paper Marks Settings. Changes to source questions will not affect this exam.");
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

  async function updateExamConfiguration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!examConfig) return;
    let selectionRules: Record<string, unknown> = {};
    if (useConfigGroupCounts) {
      const parsed = Object.fromEntries(
        Object.entries(configGroupCounts).map(([key, value]) => [key, Number(value || 0)])
      ) as Record<string, number>;
      if (Object.values(parsed).some((value) => !Number.isInteger(value) || value < 0)) {
        setError("Question group counts must be non-negative whole numbers.");
        return;
      }
      const configuredTotal = Object.values(parsed).reduce((sum, value) => sum + value, 0);
      if (configuredTotal !== Number(examConfig.total_questions)) {
        setError(`Question group counts must add up to ${examConfig.total_questions}. Current total: ${configuredTotal}.`);
        return;
      }
      selectionRules = { group_counts: parsed };
    }

    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}`, {
        method: "PUT",
        body: JSON.stringify({
          ...examConfig,
          selection_rules: selectionRules,
          duration_minutes: Number(examConfig.duration_minutes),
          total_questions: Number(examConfig.total_questions),
          start_time: examConfig.start_time ? istDateTimeToIso(examConfig.start_time) : null,
          end_time: examConfig.end_time ? istDateTimeToIso(examConfig.end_time) : null,
        }),
      });
      setMessage("Examination configuration updated and revision history saved.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update examination configuration.");
    } finally { setWorking(false); }
  }

  async function saveExamSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!examConfig?.start_time || !examConfig.end_time) {
      setError("Enter both the examination opening and closing times.");
      return;
    }

    let startTime: string;
    let endTime: string;
    try {
      startTime = istDateTimeToIso(examConfig.start_time);
      endTime = istDateTimeToIso(examConfig.end_time);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enter valid examination times.");
      return;
    }

    if (new Date(endTime) <= new Date(startTime)) {
      setError("The examination closing time must be after its opening time.");
      return;
    }

    setWorking(true);
    setError("");
    setMessage("");
    try {
      await request(`/exams/${examId}/schedule`, {
        method: "PATCH",
        body: JSON.stringify({ start_time: startTime, end_time: endTime }),
      });
      setMessage("Examination schedule saved.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the examination schedule.");
    } finally {
      setWorking(false);
    }
  }

  async function saveQuestionMarks(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedMarks = Object.fromEntries(
      questionMarkGroups.map((group) => [group.key, Number(questionMarksByGroup[group.key])])
    );
    if (Object.values(parsedMarks).some((value) => !Number.isFinite(value) || value <= 0)) {
      setError("Enter a positive maximum mark for every question group.");
      return;
    }

    setWorking(true);
    setError("");
    setMessage("");
    try {
      await request(`/exams/${examId}/question-marks`, {
        method: "PUT",
        body: JSON.stringify({ marks_by_group: parsedMarks }),
      });
      setMessage("Question paper marks updated and saved in their own revision history.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update question paper marks.");
    } finally {
      setWorking(false);
    }
  }

  async function validatePaperConfiguration() {
    setWorking(true); setError(""); setValidationMessage("");
    try {
      const data = await request(`/exams/${examId}/validate-configuration`);
      setValidationMessage(data.message || "Question paper configuration is valid.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Question paper configuration is invalid.");
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

  async function saveNegativeMarks(questionId: number, value: string) {
    setWorking(true); setError(""); setMessage("");
    try {
      const negativeMarks = Number(value);
      if (!Number.isFinite(negativeMarks) || negativeMarks < 0) {
        throw new Error("Negative marks must be a non-negative number.");
      }
      await request(`/exams/${examId}/questions/${questionId}/negative-marks`, {
        method: "PATCH",
        body: JSON.stringify({ negative_marks: negativeMarks }),
      });
      setMessage("Question penalty saved. It applies only when negative marking is enabled for this examination.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save question penalty.");
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
    if (!window.confirm("Revoke this student's access to the examination? They will no longer be able to open or continue it. Their existing exam records will be kept.")) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await request(`/exams/${examId}/assignments/${studentId}`, { method: "DELETE" });
      setMessage("Student access to this examination has been revoked.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove assignment.");
    } finally { setWorking(false); }
  }

  if (examConfig && !examConfig.can_edit) {
    return (
      <main className="min-h-screen bg-slate-950 text-white">
        <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
            <div><Link href="/staff/examinations" className="text-2xl font-bold">ExamGuard <span className="text-cyan-400">AI</span></Link><p className="text-sm text-slate-400">View Examination</p></div>
            <Link href="/staff/examinations" className="rounded-lg border border-white/20 px-4 py-2 text-sm">Back to Examinations</Link>
          </div>
        </header>
        <div className="mx-auto max-w-7xl space-y-6 px-6 py-10">
          <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
            <h1 className="text-3xl font-bold">{examConfig.title}</h1>
            <p className="mt-2 text-slate-400">{examConfig.subject || "No subject"}</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Maximum time</p><p className="mt-1 font-semibold">{examConfig.duration_minutes} minutes</p></div>
              <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Questions</p><p className="mt-1 font-semibold">{questions.length}</p></div>
              <div className="rounded-lg bg-slate-800 p-4"><p className="text-xs text-slate-400">Owner</p><p className="mt-1 font-semibold">{examConfig.created_by_name || "Another staff account"}</p><p className="text-xs capitalize text-slate-400">{examConfig.created_by_role || ""}</p></div>
            </div>
            <p className="mt-4 text-sm text-slate-400">This examination belongs to another creator. You can view its questions, but you cannot change its settings or records.</p>
          </section>
          <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Examination Questions ({questions.length})</h2>
            {questions.map((question) => (
              <article key={question.question_id} className="mt-4 rounded-xl border border-white/10 bg-slate-800/60 p-5">
                <p className="text-xs text-cyan-300">Question {question.question_order} · {question.question_type} · {question.difficulty} · {question.marks} marks</p>
                <p className="mt-3 whitespace-pre-wrap">{question.question_text}</p>
                {question.options?.map((option) => <p key={option.id} className="mt-2 text-sm text-slate-300">{option.option_text}{option.is_correct ? " (Correct answer)" : ""}</p>)}
                {question.expected_answer && <p className="mt-3 text-sm text-slate-400">Expected answer: {question.expected_answer}</p>}
                {question.model_answer_text && <p className="mt-2 text-sm text-slate-400">Model answer: {question.model_answer_text}</p>}
              </article>
            ))}
            {questions.length === 0 && <p className="py-8 text-slate-400">No questions have been added yet.</p>}
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link href={staffRole === "admin" ? "/admin/dashboard" : "/examiner/dashboard"} className="text-2xl font-bold">ExamGuard <span className="text-cyan-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Examination / Question Bank</p>
          </div>
          <div className="flex flex-wrap gap-2"><Link href="/staff/manage-exams" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Manage Examination</Link><Link href={staffRole === "admin" ? "/admin/dashboard" : "/examiner/dashboard"} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">Dashboard</Link></div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-8 px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Examination Question Bank</h1>
            <p className="mt-2 text-slate-400">Add new questions, copy questions from earlier banks, set timers, and assign students.</p>
          </div>
          <button onClick={deleteEntireBank} disabled={working} className="rounded-lg border border-red-500/50 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 disabled:opacity-40">Delete Entire Bank</button>
        </div>

        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
        {message && <div role="status" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">{message}</div>}

        {examConfig && (
          <section className={cardClass}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold">Examination Configuration</h2>
                <p className="mt-1 text-sm text-slate-400">Configuration changes are limited to three revisions before the first student session.</p>
              </div>
              <span className="text-xs text-cyan-300">{revisionsUsed}/3 revisions used</span>
            </div>
            <form onSubmit={updateExamConfiguration} className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <label className="text-sm text-slate-300">Exam title
                  <input required maxLength={200} value={examConfig.title} onChange={(e) => setExamConfig((v) => v ? { ...v, title: e.target.value } : v)} className={fieldClass} />
                </label>
                <label className="text-sm text-slate-300">Subject
                  <input required maxLength={100} value={examConfig.subject} onChange={(e) => setExamConfig((v) => v ? { ...v, subject: e.target.value } : v)} className={fieldClass} />
                </label>
                <label className="text-sm text-slate-300">Duration (minutes)
                  <input required type="number" min="1" value={examConfig.duration_minutes} onChange={(e) => setExamConfig((v) => v ? { ...v, duration_minutes: Number(e.target.value) } : v)} className={fieldClass} />
                </label>
                <label className="text-sm text-slate-300">Total questions
                  <input required type="number" min="1" value={examConfig.total_questions} onChange={(e) => setExamConfig((v) => v ? { ...v, total_questions: Number(e.target.value) } : v)} className={fieldClass} />
                </label>

              </div>
              <div className="rounded-xl border border-white/10 bg-slate-800/60 p-4">
                <label className="flex items-center gap-3 text-sm text-slate-200">
                  <input type="checkbox" checked={useConfigGroupCounts} onChange={(e) => setUseConfigGroupCounts(e.target.checked)} />
                  Use exact question counts by type and difficulty
                </label>
                {useConfigGroupCounts && (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-xs">
                      <thead><tr className="border-b border-white/10 text-slate-400"><th className="p-2">Difficulty</th>{configQuestionTypes.map((type) => <th key={type} className="p-2">{type}</th>)}</tr></thead>
                      <tbody>{configDifficulties.map((difficulty) => (
                        <tr key={difficulty} className="border-b border-white/5">
                          <th className="p-2 capitalize text-slate-300">{difficulty}</th>
                          {configQuestionTypes.map((type) => {
                            const key = `${difficulty}|${type}`;
                            return <td key={key} className="p-2"><input type="number" min="0" step="1" value={configGroupCounts[key] ?? "0"} onChange={(e) => setConfigGroupCounts((current) => ({ ...current, [key]: e.target.value }))} className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-white" /></td>;
                          })}
                        </tr>
                      ))}</tbody>
                    </table>
                    <p className="mt-2 text-xs text-cyan-300">Configured: {Object.values(configGroupCounts).reduce((sum, value) => sum + (Number(value) || 0), 0)} / {examConfig.total_questions}</p>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-5 text-sm text-slate-300">
                <label className="flex items-center gap-2"><input type="checkbox" checked={examConfig.randomize_questions} onChange={(e) => setExamConfig((v) => v ? { ...v, randomize_questions: e.target.checked } : v)} /> Randomize papers</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={examConfig.negative_marking} onChange={(e) => setExamConfig((v) => v ? { ...v, negative_marking: e.target.checked } : v)} /> Negative marking</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={examConfig.proctoring_enabled} onChange={(e) => setExamConfig((v) => v ? { ...v, proctoring_enabled: e.target.checked } : v)} /> Proctoring</label>
              </div>
              <button type="submit" disabled={working || !examConfig.can_edit || revisionsUsed >= 3} className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-40">
                {revisionsUsed >= 3 ? "Revision Limit Reached" : "Save Configuration Revision"}
              </button>
            </form>
            <div className="mt-6 border-t border-white/10 pt-5">
              <h3 className="font-semibold">Configuration History</h3>
              <div className="mt-3 space-y-2">
                {configRevisions.map((revision) => (
                  <div key={revision.revision_number} className="rounded-lg bg-slate-800/60 p-3 text-xs text-slate-300">
                    <span className="font-semibold">{revision.revision_number === 0 ? "Initial configuration" : `Revision ${revision.revision_number}`}</span>
                    <span className="ml-3 text-slate-500">{new Date(revision.created_at).toLocaleString("en-IN", { timeZone: INDIA_TIME_ZONE })} IST · Staff account #{revision.changed_by}</span>
                    <p className="mt-2 text-slate-400">{String(revision.configuration.title || "Untitled")} · {String(revision.configuration.duration_minutes || "—")} minutes · {String(revision.configuration.total_questions || "—")} questions · Subject: {String(revision.configuration.subject || "—")}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {examConfig && (
          <section className={cardClass}>
            <h2 className="text-xl font-semibold">Examination Schedule</h2>
            <p className="mt-1 text-sm text-slate-400">
              You can schedule this examination now or later. Students cannot start it until both times are saved.
            </p>
            <p className="mt-2 text-sm text-cyan-300">
              Current schedule: {examConfig.start_time && examConfig.end_time
                ? `${new Date(istDateTimeToIso(examConfig.start_time)).toLocaleString("en-IN", { timeZone: INDIA_TIME_ZONE })} IST to ${new Date(istDateTimeToIso(examConfig.end_time)).toLocaleString("en-IN", { timeZone: INDIA_TIME_ZONE })} IST`
                : "Not scheduled"}
            </p>
            {examConfig.start_time && examConfig.end_time &&
              new Date(istDateTimeToIso(examConfig.end_time)).getTime() <= Date.now() && (
                <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                  This examination schedule has expired. If no student examination session has been created, you can set a new future opening and closing time below. Save the new schedule before assigning students.
                </div>
              )}
            <p className="mt-2 text-xs text-slate-400">
              To reopen an expired examination, choose a future opening time and closing time, then save the schedule. Your existing questions and examination details will be kept.
            </p>
            <form onSubmit={saveExamSchedule} className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm text-slate-300">Opening time (IST)
                <input required type="datetime-local" value={examConfig.start_time} onChange={(e) => setExamConfig((v) => v ? { ...v, start_time: e.target.value } : v)} className={fieldClass + " mt-2"} />
              </label>
              <label className="text-sm text-slate-300">Closing time (IST)
                <input required type="datetime-local" value={examConfig.end_time} onChange={(e) => setExamConfig((v) => v ? { ...v, end_time: e.target.value } : v)} className={fieldClass + " mt-2"} />
              </label>
              <div className="sm:col-span-2">
                <button type="submit" disabled={working || !examConfig.can_edit} className="rounded-lg bg-cyan-600 px-5 py-2.5 text-sm font-semibold hover:bg-cyan-500 disabled:opacity-40">
                  Save Examination Schedule
                </button>
                {!examConfig.can_edit && <p className="mt-2 text-xs text-slate-500">Only the examination creator can change this schedule.</p>}
              </div>
            </form>
          </section>
        )}

        <section className={cardClass}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">Question Paper Marks Settings</h2>
              <p className="mt-1 text-sm text-slate-400">Set the maximum marks for this examination's questions by type and difficulty. These values belong only to this examination, not to the source question banks. This has its own three-revision limit and is separate from exam settings and student answer marks.</p>
            </div>
            <span className="text-xs text-cyan-300">{questionMarksRevisionsUsed}/3 revisions used</span>
          </div>
          {questionMarkGroups.length === 0 ? (
            <p className="mt-4 text-sm text-slate-400">Add questions to this bank before setting group marks.</p>
          ) : (
            <form onSubmit={saveQuestionMarks} className="mt-4 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {questionMarkGroups.map((group) => (
                  <label key={group.key} className="text-sm text-slate-300">
                    <span className="block capitalize">{group.difficulty} · {group.questionType.replaceAll("_", " ")} ({group.count} question(s))</span>
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      required
                      value={questionMarksByGroup[group.key] ?? ""}
                      onChange={(event) => setQuestionMarksByGroup((current) => ({ ...current, [group.key]: event.target.value }))}
                      className={fieldClass + " mt-2"}
                    />
                  </label>
                ))}
              </div>
              <button
                type="submit"
                disabled={working || !questionMarksCanEdit || questionMarksRevisionsUsed >= 3}
                className="rounded-lg bg-cyan-600 px-5 py-2.5 text-sm font-semibold hover:bg-cyan-500 disabled:opacity-40"
              >
                {questionMarksRevisionsUsed >= 3 ? "Marks Revision Limit Reached" : "Save Question Marks"}
              </button>
              {questionMarksLocked && <p className="text-xs text-slate-500">These marks are locked because a student session has already been created.</p>}
              {!questionMarksLocked && !questionMarksCanEdit && <p className="text-xs text-slate-500">You can view these marks, but only the examination creator can change them.</p>}
            </form>
          )}
          <div className="mt-5 border-t border-white/10 pt-4">
            <h3 className="font-semibold">Question Marks History</h3>
            {questionMarksRevisions.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">No question marks revisions have been made.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {questionMarksRevisions.map((revision) => (
                  <div key={revision.revision_number} className="rounded-lg bg-slate-800/60 p-3 text-xs text-slate-300">
                    <span className="font-semibold">Revision {revision.revision_number}</span>
                    <span className="ml-3 text-slate-500">{new Date(revision.created_at).toLocaleString("en-IN", { timeZone: INDIA_TIME_ZONE })} IST · Staff account #{revision.changed_by}</span>
                    <p className="mt-2 text-slate-400">{Object.entries(revision.marks_snapshot).map(([key, value]) => `${key.replace("|", " · ")}: ${value} marks`).join(" | ")}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

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
            <label className="block text-sm text-slate-300">Tags (separate with commas)
              <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="Example: algebra, equations, practice" className={fieldClass + " mt-2"} />
            </label>
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
                      {question.tags && question.tags.length > 0 && <p className="mt-2 text-xs text-slate-400">Tags: {question.tags.join(", ")}</p>}
                      {question.options && question.options.length > 0 && (
                        <ul className="mt-3 space-y-1 text-sm text-slate-300">
                          {question.options.map((option) => (
                            <li key={option.id}>• {option.option_text}{option.is_correct ? " (Correct answer)" : ""}</li>
                          ))}
                        </ul>
                      )}
                      {question.expected_answer && <p className="mt-3 text-sm text-slate-400">Expected answer: {question.expected_answer}</p>}
                      {question.model_answer_text && <p className="mt-2 text-sm text-slate-400">Model answer: {question.model_answer_text}</p>}
                      {question.question_image_available && <p className="mt-2 text-xs text-cyan-300">Question prompt image attached</p>}
                    </div>
                    <button onClick={() => removeQuestion(question.question_id)} disabled={working} className="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-40">Remove from Bank</button>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <label className="text-xs text-slate-400">Negative marks for a wrong answer
                      <input key={`negative-${question.question_id}-${question.negative_marks ?? 0}`} type="number" min="0" step="0.01" defaultValue={question.negative_marks ?? 0} onBlur={(e) => void saveNegativeMarks(question.question_id, e.target.value)} className="ml-2 w-28 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white" />
                    </label>
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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">Validate Examination Paper</h2>
              <p className="mt-1 text-sm text-slate-400">Check that the bank has enough questions for every configured type/difficulty group and that marks are consistent.</p>
            </div>
            <button onClick={validatePaperConfiguration} disabled={working} className="rounded-lg border border-cyan-500/40 px-4 py-2 text-sm text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-50">Validate Paper Configuration</button>
          </div>
          {validationMessage && <p role="status" className="mt-3 text-sm text-emerald-300">{validationMessage}</p>}
        </section>

        <section className={cardClass}>
          <h2 className="text-xl font-semibold">Reuse Previous Question Banks</h2>
          <p className="mt-1 text-sm text-slate-400">Choose questions from earlier examinations. Question text, correct answers, expected answers, options and images are copied as independent snapshots. Source maximum marks are not reused; this examination uses its own marks settings.</p>
          {sourceBanks.length === 0 ? <p className="py-6 text-sm text-slate-400">No reusable question banks are available.</p> : (
            <div className="mt-4 space-y-4">
              {sourceBanks.map((bank) => (
                <div key={bank.source_exam_id} className="rounded-xl border border-white/10 p-4">
                  <h3 className="font-semibold">{bank.source_exam_title}</h3>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {bank.questions.filter((question) =>
                      (filterType === "all" || question.question_type === filterType) &&
                      (filterDifficulty === "all" || question.difficulty === filterDifficulty)
                    ).map((question) => (
                      <label key={question.question_id} className="flex items-start gap-3 rounded-lg bg-slate-800/60 p-3 text-sm">
                        <input type="checkbox" checked={selectedSources.includes(question.question_id)} onChange={() => toggleSource(question.question_id)} className="mt-1" />
                        <span><span className="block">{question.question_text}</span><span className="mt-1 block text-xs text-slate-400">{question.question_type} · {question.difficulty} · Source exam: {question.marks} marks (not copied)</span></span>
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
          <p className="mt-1 text-sm text-slate-400">Only assigned students can see and start this examination. If its schedule has expired, update and save a future schedule above before assigning students.</p>
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
            <h3 className="font-semibold">Student Assignment History ({assignedStudents.length})</h3>
            <p className="mt-1 text-xs text-slate-400">This list also shows students whose access was revoked, so examination history remains visible.</p>
            <div className="mt-3 space-y-2">
              {assignedStudents.map((student) => (
                <div key={student.student_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-800/50 p-3 text-sm">
                  <span>
                    {student.full_name}
                    <span className="ml-2 text-xs text-slate-400">{student.email}</span>
                    <span className={student.is_active ? "ml-2 text-xs text-emerald-300" : "ml-2 text-xs text-amber-300"}>
                      {student.is_active ? "Access active" : "Access revoked"}
                    </span>
                    {student.session_status && <span className="ml-2 text-xs text-slate-400">Exam session: {student.session_status.replaceAll("_", " ")}</span>}
                  </span>
                  {student.is_active && (
                    <button onClick={() => removeAssignment(student.student_id)} disabled={working} className="text-xs text-red-300 hover:underline disabled:opacity-40">Revoke Access</button>
                  )}
                </div>
              ))}
              {assignedStudents.length === 0 && <p className="text-sm text-slate-400">No students have been assigned yet.</p>}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

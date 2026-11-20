
"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const difficultyLevels = ["easy", "medium", "hard"] as const;
const questionTypes = ["MCQ", "multi_select", "short_answer", "long_answer", "image_upload"] as const;
const defaultGroupCounts: Record<string, string> = Object.fromEntries(
  difficultyLevels.flatMap((difficulty) =>
    questionTypes.map((type) => [`${difficulty}|${type}`, "0"])
  )
);

interface Exam {
  id: number;
  title: string;
  subject?: string | null;
  duration_minutes: number;
  total_questions: number;
  start_time?: string | null;
  end_time?: string | null;
  negative_marking?: boolean;
  proctoring_enabled?: boolean;
  created_by?: number | null;
}

const INDIA_TIME_ZONE = "Asia/Kolkata";

function istDateTimeToIso(value: string) {
  const withSeconds = value.length === 16 ? `${value}:00` : value;
  const date = new Date(`${withSeconds}+05:30`);
  if (Number.isNaN(date.getTime())) throw new Error("Enter a valid IST schedule time.");
  return date.toISOString();
}

function formatDate(value?: string | null) {
  if (!value) return "Not scheduled";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Invalid date";

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: INDIA_TIME_ZONE,
  });
}

export default function ExaminerExamsPage() {
  const router = useRouter();

  const [exams, setExams] = useState<Exam[]>([]);
  const [staffRole, setStaffRole] = useState<"admin" | "examiner">("examiner");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [duration, setDuration] = useState("60");
  const [totalQuestions, setTotalQuestions] = useState("20");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [negativeMarking, setNegativeMarking] = useState(false);
  const [proctoringEnabled, setProctoringEnabled] = useState(true);
  const [gazeSensitivity, setGazeSensitivity] = useState("0.5");
  const [maxTabWarnings, setMaxTabWarnings] = useState("3");
  const [randomizeQuestions, setRandomizeQuestions] = useState(true);
  const [useGroupCounts, setUseGroupCounts] = useState(false);
  const [groupCounts, setGroupCounts] = useState<Record<string, string>>(defaultGroupCounts);

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

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const profileResponse = await fetch(`${API_URL}/users/me`, {
        method: "GET",
        headers,
        cache: "no-store",
      });
      if (!profileResponse.ok) throw new Error("Unable to load your staff account.");
      const profile = await profileResponse.json();
      setStaffRole(profile.role === "admin" ? "admin" : "examiner");

      const response = await fetch(`${API_URL}/exams`, {
        method: "GET",
        headers,
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load examinations.");
      }

      const data = await response.json();

      const examList = Array.isArray(data)
        ? data
        : Array.isArray(data.exams)
          ? data.exams
          : null;

      if (!examList) {
        throw new Error("Unexpected examination data returned by the server.");
      }

      setExams(
        profile.role === "admin"
          ? examList.filter((exam: Exam) => exam.created_by === Number(profile.id))
          : examList
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load examinations."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadExams();
  }, [loadExams]);

  function resetForm() {
    setTitle("");
    setSubject("");
    setDuration("60");
    setTotalQuestions("20");
    setStartTime("");
    setEndTime("");
    setNegativeMarking(false);
    setProctoringEnabled(true);
    setGazeSensitivity("0.5");
    setMaxTabWarnings("3");
    setRandomizeQuestions(true);
    setUseGroupCounts(false);
    setGroupCounts(defaultGroupCounts);
  }

  async function createExam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setMessage("");

    const durationValue = Number(duration);
    const questionCount = Number(totalQuestions);
    const sensitivity = Number(gazeSensitivity);
    const tabWarnings = Number(maxTabWarnings);

    if (!title.trim() || !subject.trim()) {
      setError("Enter the examination title and subject.");
      return;
    }

    if (
      !Number.isInteger(durationValue) ||
      durationValue <= 0
    ) {
      setError("Duration must be a positive whole number.");
      return;
    }

    if (
      !Number.isInteger(questionCount) ||
      questionCount <= 0
    ) {
      setError("Question count must be a positive whole number.");
      return;
    }

    if (!startTime || !endTime) {
      setError("Select both examination start and end times.");
      return;
    }

    let startIso: string;
    let endIso: string;
    try {
      startIso = istDateTimeToIso(startTime);
      endIso = istDateTimeToIso(endTime);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Enter valid IST schedule times.");
      return;
    }
    const startDate = new Date(startIso);
    const endDate = new Date(endIso);

    if (
      Number.isNaN(startDate.getTime()) ||
      Number.isNaN(endDate.getTime()) ||
      endDate <= startDate
    ) {
      setError("The examination end time must be after its start time.");
      return;
    }

    if (
      !Number.isFinite(sensitivity) ||
      sensitivity < 0 ||
      sensitivity > 1
    ) {
      setError("Gaze sensitivity must be between 0 and 1.");
      return;
    }

    if (
      !Number.isInteger(tabWarnings) ||
      tabWarnings < 0
    ) {
      setError("Maximum tab warnings must be a non-negative whole number.");
      return;
    }

    let selectionRules: Record<string, unknown> = {};
    if (useGroupCounts) {
      const parsedGroups = Object.fromEntries(
        Object.entries(groupCounts).map(([key, value]) => [key, Number(value || 0)])
      ) as Record<string, number>;
      const configuredTotal = Object.values(parsedGroups).reduce((sum, value) => sum + value, 0);
      if (Object.values(parsedGroups).some((value) => !Number.isInteger(value) || value < 0)) {
        setError("Every type/difficulty count must be a non-negative whole number.");
        return;
      }
      if (configuredTotal !== questionCount) {
        setError(`The type/difficulty counts must add up to ${questionCount} questions. Current total: ${configuredTotal}.`);
        return;
      }
      selectionRules = { group_counts: parsedGroups };
    }

    setCreating(true);

    try {
      const headers = getHeaders();
      if (!headers) return;

      const payload = {
        title: title.trim(),
        subject: subject.trim(),
        duration_minutes: durationValue,
        total_questions: questionCount,
        start_time: startIso,
        end_time: endIso,
        randomize_questions: randomizeQuestions,
        selection_rules: selectionRules,
        negative_marking: negativeMarking,
        proctoring_enabled: proctoringEnabled,
        gaze_tracking_sensitivity: sensitivity,
        max_tab_switch_warnings: tabWarnings,
      };

      const response = await fetch(`${API_URL}/exams`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to create examination."
        );
      }

      setMessage("Examination created successfully.");
      resetForm();
      await loadExams();
      if (data.exam_id) {
        router.push(`/examiner/exams/${data.exam_id}/question-bank`);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create examination."
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
              href={staffRole === "admin" ? "/admin/dashboard" : "/examiner/dashboard"}
              className="text-2xl font-bold"
            >
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>

            <p className="mt-1 text-sm text-slate-400">
              {staffRole === "admin" ? "Administrator" : "Examiner"} / Examination Management
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
        <h1 className="text-3xl font-bold">
          Examination Management
        </h1>

        <p className="mt-2 text-slate-400">
          Create and configure your online examinations.
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
          <h2 className="text-xl font-bold">Create Examination</h2>

          <form onSubmit={createExam} className="mt-6 space-y-6">
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="title" className="mb-2 block text-sm font-medium">
                  Examination title
                </label>

                <input
                  id="title"
                  required
                  maxLength={200}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Enter examination title"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="subject" className="mb-2 block text-sm font-medium">
                  Subject
                </label>

                <input
                  id="subject"
                  required
                  maxLength={100}
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  placeholder="Enter subject"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="duration" className="mb-2 block text-sm font-medium">
                  Duration (minutes)
                </label>

                <input
                  id="duration"
                  type="number"
                  min="1"
                  step="1"
                  required
                  value={duration}
                  onChange={(event) => setDuration(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="totalQuestions" className="mb-2 block text-sm font-medium">
                  Total questions
                </label>

                <input
                  id="totalQuestions"
                  type="number"
                  min="1"
                  step="1"
                  required
                  value={totalQuestions}
                  onChange={(event) => setTotalQuestions(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="startTime" className="mb-2 block text-sm font-medium">
                  Examination start (IST)
                </label>

                <input
                  id="startTime"
                  type="datetime-local"
                  required
                  value={startTime}
                  onChange={(event) => setStartTime(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="endTime" className="mb-2 block text-sm font-medium">
                  Examination end (IST)
                </label>

                <input
                  id="endTime"
                  type="datetime-local"
                  required
                  value={endTime}
                  onChange={(event) => setEndTime(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
              <h3 className="font-semibold">Examination Settings</h3>

              <div className="mt-4 space-y-4">
                <label className="flex items-center gap-3 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={randomizeQuestions}
                    onChange={(event) =>
                      setRandomizeQuestions(event.target.checked)
                    }
                    className="h-4 w-4"
                  />
                  Randomize question order
                </label>

                <label className="flex items-center gap-3 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={negativeMarking}
                    onChange={(event) =>
                      setNegativeMarking(event.target.checked)
                    }
                    className="h-4 w-4"
                  />
                  Enable negative marking
                </label>

                <label className="flex items-center gap-3 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={proctoringEnabled}
                    onChange={(event) =>
                      setProctoringEnabled(event.target.checked)
                    }
                    className="h-4 w-4"
                  />
                  Enable AI-assisted proctoring
                </label>
              </div>
            </div>


            <div className="rounded-xl border border-white/10 bg-slate-800/60 p-5">
              <label className="flex items-center gap-3 text-sm font-semibold text-slate-200">
                <input
                  type="checkbox"
                  checked={useGroupCounts}
                  onChange={(event) => setUseGroupCounts(event.target.checked)}
                  className="h-4 w-4"
                />
                Configure exact question counts by difficulty and question type
              </label>
              {useGroupCounts && (
                <div className="mt-4 overflow-x-auto">
                  <p className="mb-3 text-xs text-slate-400">
                    Enter how many questions the system must select from each group. All cells together must equal the total question count.
                  </p>
                  <table className="w-full min-w-[720px] text-left text-xs">
                    <thead>
                      <tr className="border-b border-white/10 text-slate-400">
                        <th className="p-2">Difficulty</th>
                        {questionTypes.map((type) => <th key={type} className="p-2">{type}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {difficultyLevels.map((level) => (
                        <tr key={level} className="border-b border-white/5">
                          <th className="p-2 capitalize text-slate-300">{level}</th>
                          {questionTypes.map((type) => {
                            const key = `${level}|${type}`;
                            return (
                              <td key={key} className="p-2">
                                <input
                                  type="number"
                                  min="0"
                                  step="1"
                                  value={groupCounts[key] ?? "0"}
                                  onChange={(event) => setGroupCounts((current) => ({ ...current, [key]: event.target.value }))}
                                  className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-white"
                                  aria-label={`${level} ${type} question count`}
                                />
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-3 text-xs text-cyan-300">
                    Configured: {Object.values(groupCounts).reduce((sum, value) => sum + (Number(value) || 0), 0)} / {totalQuestions || 0}
                  </p>
                </div>
              )}
            </div>

            {proctoringEnabled && (
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="gazeSensitivity"
                    className="mb-2 block text-sm font-medium"
                  >
                    Gaze tracking sensitivity (0–1)
                  </label>

                  <input
                    id="gazeSensitivity"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={gazeSensitivity}
                    onChange={(event) =>
                      setGazeSensitivity(event.target.value)
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label
                    htmlFor="maxTabWarnings"
                    className="mb-2 block text-sm font-medium"
                  >
                    Maximum tab-switch warnings
                  </label>

                  <input
                    id="maxTabWarnings"
                    type="number"
                    min="0"
                    step="1"
                    value={maxTabWarnings}
                    onChange={(event) =>
                      setMaxTabWarnings(event.target.value)
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-blue-600 px-6 py-3 font-semibold transition hover:bg-blue-500 disabled:opacity-60"
            >
              {creating ? "Creating Examination..." : "Create Examination"}
            </button>
          </form>
        </section>

        <section className="mt-10 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">My Examinations</h2>

              <p className="mt-1 text-sm text-slate-400">
                {exams.length} examination(s)
              </p>
            </div>

            <button
              type="button"
              onClick={loadExams}
              disabled={loading}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="py-10 text-center text-slate-400">
              Loading examinations...
            </p>
          ) : exams.length === 0 ? (
            <p className="py-10 text-center text-slate-400">
              You have not created any examinations yet.
            </p>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Title</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Questions</th>
                    <th className="px-4 py-3">Start Time</th>
                    <th className="px-4 py-3">End Time</th>
                    <th className="px-4 py-3">Manage</th>
                  </tr>
                </thead>

                <tbody>
                  {exams.map((exam) => (
                    <tr
                      key={exam.id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="px-4 py-4 font-semibold">
                        {exam.title}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.subject || "—"}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.duration_minutes} minutes
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {exam.total_questions}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {formatDate(exam.start_time)}
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {formatDate(exam.end_time)}
                      </td>
                      <td className="px-4 py-4">
                        <Link
                          href={`/examiner/exams/${exam.id}/question-bank`}
                          className="rounded-lg bg-cyan-600/20 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-600/30"
                        >
                          Manage Bank & Students
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
  }
  

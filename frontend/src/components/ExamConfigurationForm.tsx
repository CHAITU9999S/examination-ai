
"use client";

import { useState, type FormEvent } from "react";

type Difficulty = "easy" | "medium" | "hard";

export interface ExamConfigurationData {
  title: string;
  subject: string;
  duration_minutes: number;
  total_questions: number;
  start_time: string;
  end_time: string;
  randomize_questions: boolean;
  negative_marking: boolean;
  proctoring_enabled: boolean;
  gaze_tracking_sensitivity: number;
  max_tab_switch_warnings: number;
  selection_rules: {
    difficulty_distribution?: Record<Difficulty, number>;
  };
}

interface ExamConfigurationFormProps {
  onSubmit: (
    data: ExamConfigurationData
  ) => void | Promise<void>;
  submitting?: boolean;
}

export default function ExamConfigurationForm({
  onSubmit,
  submitting = false,
}: ExamConfigurationFormProps) {
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [duration, setDuration] = useState("60");
  const [totalQuestions, setTotalQuestions] = useState("20");

  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  const [randomize, setRandomize] = useState(true);
  const [negativeMarking, setNegativeMarking] = useState(false);
  const [proctoring, setProctoring] = useState(true);

  const [gazeSensitivity, setGazeSensitivity] = useState("0.7");
  const [maxTabWarnings, setMaxTabWarnings] = useState("3");

  const [useDifficultyDistribution, setUseDifficultyDistribution] =
    useState(false);

  const [difficultyCounts, setDifficultyCounts] = useState<
    Record<Difficulty, string>
  >({
    easy: "",
    medium: "",
    hard: "",
  });

  const [error, setError] = useState("");

  function updateDifficulty(
    difficulty: Difficulty,
    value: string
  ) {
    setDifficultyCounts((previous) => ({
      ...previous,
      [difficulty]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const cleanedTitle = title.trim();
    const cleanedSubject = subject.trim();

    const parsedDuration = Number(duration);
    const parsedTotalQuestions = Number(totalQuestions);
    const parsedSensitivity = Number(gazeSensitivity);
    const parsedTabWarnings = Number(maxTabWarnings);

    if (!cleanedTitle) {
      setError("Enter the examination title.");
      return;
    }

    if (!cleanedSubject) {
      setError("Enter the examination subject.");
      return;
    }

    if (
      !Number.isInteger(parsedDuration) ||
      parsedDuration <= 0
    ) {
      setError("Duration must be a positive whole number.");
      return;
    }

    if (
      !Number.isInteger(parsedTotalQuestions) ||
      parsedTotalQuestions <= 0
    ) {
      setError("Total questions must be a positive whole number.");
      return;
    }

    if (!startTime || !endTime) {
      setError("Select both examination start and end times.");
      return;
    }

    const startDate = new Date(startTime);
    const endDate = new Date(endTime);

    if (
      Number.isNaN(startDate.getTime()) ||
      Number.isNaN(endDate.getTime()) ||
      endDate <= startDate
    ) {
      setError("The examination end time must be after its start time.");
      return;
    }

    if (
      !Number.isFinite(parsedSensitivity) ||
      parsedSensitivity < 0 ||
      parsedSensitivity > 1
    ) {
      setError("Gaze sensitivity must be between 0 and 1.");
      return;
    }

    if (
      !Number.isInteger(parsedTabWarnings) ||
      parsedTabWarnings < 0
    ) {
      setError("Maximum tab warnings must be zero or a positive whole number.");
      return;
    }

    const selectionRules: ExamConfigurationData["selection_rules"] = {};

    if (useDifficultyDistribution) {
      const distribution: Record<Difficulty, number> = {
        easy: Number(difficultyCounts.easy || 0),
        medium: Number(difficultyCounts.medium || 0),
        hard: Number(difficultyCounts.hard || 0),
      };

      const values = Object.values(distribution);

      if (
        values.some(
          (value) =>
            !Number.isInteger(value) || value < 0
        )
      ) {
        setError("Difficulty counts must be non-negative whole numbers.");
        return;
      }

      const distributionTotal = values.reduce(
        (sum, value) => sum + value,
        0
      );

      if (distributionTotal !== parsedTotalQuestions) {
        setError(
          "The easy, medium and hard counts must add up to the total number of questions."
        );
        return;
      }

      selectionRules.difficulty_distribution = distribution;
    }

    const examData: ExamConfigurationData = {
      title: cleanedTitle,
      subject: cleanedSubject,
      duration_minutes: parsedDuration,
      total_questions: parsedTotalQuestions,
      start_time: startDate.toISOString(),
      end_time: endDate.toISOString(),
      randomize_questions: randomize,
      negative_marking: negativeMarking,
      proctoring_enabled: proctoring,
      gaze_tracking_sensitivity: parsedSensitivity,
      max_tab_switch_warnings: parsedTabWarnings,
      selection_rules: selectionRules,
    };

    try {
      await onSubmit(examData);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to create the examination. Please try again."
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
          Examination Configuration
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Configure the examination schedule, questions and security settings.
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
          htmlFor="exam-title"
          className="mb-2 block text-sm font-medium text-slate-700"
        >
          Examination Title
        </label>

        <input
          id="exam-title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Enter examination title"
          required
          maxLength={200}
          disabled={submitting}
          className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="exam-subject"
          className="mb-2 block text-sm font-medium text-slate-700"
        >
          Subject
        </label>

        <input
          id="exam-subject"
          type="text"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder="e.g. Computer Science"
          required
          disabled={submitting}
          className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="exam-duration"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Duration (minutes)
          </label>

          <input
            id="exam-duration"
            type="number"
            min="1"
            step="1"
            value={duration}
            onChange={(event) => setDuration(event.target.value)}
            required
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="exam-total-questions"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Total Questions
          </label>

          <input
            id="exam-total-questions"
            type="number"
            min="1"
            step="1"
            value={totalQuestions}
            onChange={(event) => setTotalQuestions(event.target.value)}
            required
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="exam-start"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Examination Start
          </label>

          <input
            id="exam-start"
            type="datetime-local"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
            required
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="exam-end"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Examination End
          </label>

          <input
            id="exam-end"
            type="datetime-local"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            required
            disabled={submitting}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="space-y-4 rounded-lg border border-slate-200 p-4">
        <h3 className="font-semibold text-slate-800">
          Question Selection
        </h3>

        <label className="flex items-center gap-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={randomize}
            onChange={(event) => setRandomize(event.target.checked)}
            disabled={submitting}
            className="h-4 w-4"
          />
          Randomize questions for each student
        </label>

        <label className="flex items-center gap-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={useDifficultyDistribution}
            onChange={(event) =>
              setUseDifficultyDistribution(event.target.checked)
            }
            disabled={submitting}
            className="h-4 w-4"
          />
          Specify difficulty distribution
        </label>

        {useDifficultyDistribution && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {(["easy", "medium", "hard"] as Difficulty[]).map(
              (difficulty) => (
                <div key={difficulty}>
                  <label
                    htmlFor={`difficulty-${difficulty}`}
                    className="mb-1 block text-sm font-medium capitalize text-slate-700"
                  >
                    {difficulty}
                  </label>

                  <input
                    id={`difficulty-${difficulty}`}
                    type="number"
                    min="0"
                    step="1"
                    value={difficultyCounts[difficulty]}
                    onChange={(event) =>
                      updateDifficulty(difficulty, event.target.value)
                    }
                    disabled={submitting}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              )
            )}
          </div>
        )}
      </div>

      <div className="space-y-4 rounded-lg border border-slate-200 p-4">
        <h3 className="font-semibold text-slate-800">
          Examination Security
        </h3>

        <label className="flex items-center gap-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={negativeMarking}
            onChange={(event) =>
              setNegativeMarking(event.target.checked)
            }
            disabled={submitting}
            className="h-4 w-4"
          />
          Enable negative marking
        </label>

        <label className="flex items-center gap-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={proctoring}
            onChange={(event) => setProctoring(event.target.checked)}
            disabled={submitting}
            className="h-4 w-4"
          />
          Enable AI-assisted online proctoring
        </label>

        {proctoring && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="gaze-sensitivity"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                Gaze Tracking Sensitivity (0–1)
              </label>

              <input
                id="gaze-sensitivity"
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={gazeSensitivity}
                onChange={(event) =>
                  setGazeSensitivity(event.target.value)
                }
                disabled={submitting}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label
                htmlFor="max-tab-warnings"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                Maximum Tab Warnings
              </label>

              <input
                id="max-tab-warnings"
                type="number"
                min="0"
                step="1"
                value={maxTabWarnings}
                onChange={(event) =>
                  setMaxTabWarnings(event.target.value)
                }
                disabled={submitting}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Creating Examination..." : "Create Examination"}
      </button>
    </form>
  );
}

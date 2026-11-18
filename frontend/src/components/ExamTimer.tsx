
"use client";

interface ExamTimerProps {
  remainingSeconds: number;
  onTimeExpired?: () => void;
  warningThresholdSeconds?: number;
}

function formatTime(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));

  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;

  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

export default function ExamTimer({
  remainingSeconds,
  onTimeExpired,
  warningThresholdSeconds = 300,
}: ExamTimerProps) {
  const safeRemainingSeconds = Math.max(
    0,
    Math.floor(remainingSeconds)
  );

  const isExpired = safeRemainingSeconds <= 0;

  const isWarning =
    !isExpired &&
    safeRemainingSeconds <= warningThresholdSeconds;

  return (
    <section
      aria-label="Examination timer"
      aria-live="polite"
      className={`rounded-xl border p-4 shadow-sm ${
        isExpired
          ? "border-red-300 bg-red-50"
          : isWarning
            ? "border-orange-300 bg-orange-50"
            : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">
            Time Remaining
          </p>

          <p
            className={`mt-1 font-mono text-3xl font-bold tabular-nums ${
              isExpired
                ? "text-red-700"
                : isWarning
                  ? "text-orange-700"
                  : "text-slate-900"
            }`}
          >
            {formatTime(safeRemainingSeconds)}
          </p>
        </div>

        <div
          className={`rounded-lg px-3 py-2 text-sm font-semibold ${
            isExpired
              ? "bg-red-100 text-red-700"
              : isWarning
                ? "bg-orange-100 text-orange-700"
                : "bg-green-100 text-green-700"
          }`}
        >
          {isExpired
            ? "Time expired"
            : isWarning
              ? "Time running out"
              : "Exam in progress"}
        </div>
      </div>

      {isExpired && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          Your examination time has ended.
        </p>
      )}

      {!isExpired && isWarning && (
        <p className="mt-3 text-sm text-orange-700">
          Please review your answers and submit before time runs out.
        </p>
      )}
    </section>
  );
}

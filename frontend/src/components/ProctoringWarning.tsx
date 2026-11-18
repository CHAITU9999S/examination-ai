
"use client";

import { useEffect, useState } from "react";

export type ProctoringWarningType =
  | "tab_switch"
  | "window_blur"
  | "face_not_detected"
  | "multiple_faces"
  | "gaze_away"
  | "webcam_error"
  | "general";

export interface ProctoringWarningItem {
  id: string | number;
  type: ProctoringWarningType;
  message?: string;
  timestamp?: string;
}

interface ProctoringWarningProps {
  warnings: ProctoringWarningItem[];
  maxVisible?: number;
  onDismiss?: (warningId: string | number) => void;
}

const WARNING_DETAILS: Record<
  ProctoringWarningType,
  { title: string; description: string }
> = {
  tab_switch: {
    title: "Tab Switch Detected",
    description:
      "You switched away from the examination tab. Return to the examination window.",
  },
  window_blur: {
    title: "Window Focus Lost",
    description:
      "The examination window lost focus. Keep the examination window active.",
  },
  face_not_detected: {
    title: "Face Not Detected",
    description:
      "Your face could not be detected. Sit in front of the webcam with your face visible.",
  },
  multiple_faces: {
    title: "Multiple Faces Detected",
    description:
      "More than one face was detected. Only the registered candidate should be visible.",
  },
  gaze_away: {
    title: "Attention Warning",
    description:
      "Your gaze appears to be away from the screen. Please focus on the examination.",
  },
  webcam_error: {
    title: "Webcam Problem",
    description:
      "The webcam is not working correctly. Check camera permission and connection.",
  },
  general: {
    title: "Proctoring Alert",
    description:
      "A proctoring event has been detected. Follow the examination instructions.",
  },
};

export default function ProctoringWarning({
  warnings,
  maxVisible = 5,
  onDismiss,
}: ProctoringWarningProps) {
  const [visibleWarnings, setVisibleWarnings] = useState<
    ProctoringWarningItem[]
  >([]);

  useEffect(() => {
    const safeMax = Number.isFinite(maxVisible)
      ? Math.max(1, Math.floor(maxVisible))
      : 5;

    setVisibleWarnings(warnings.slice(-safeMax).reverse());
  }, [warnings, maxVisible]);

  function dismissWarning(id: string | number) {
    setVisibleWarnings((current) =>
      current.filter((warning) => warning.id !== id)
    );

    onDismiss?.(id);
  }

  if (visibleWarnings.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Examination proctoring warnings"
      className="space-y-3"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">
          Proctoring Alerts
        </h2>

        <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
          {visibleWarnings.length} alert
          {visibleWarnings.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="space-y-2" aria-live="polite">
        {visibleWarnings.map((warning) => {
          const details = WARNING_DETAILS[warning.type];

          const timestamp = warning.timestamp
            ? new Date(warning.timestamp)
            : null;

          const validTimestamp =
            timestamp && !Number.isNaN(timestamp.getTime());

          return (
            <article
              key={warning.id}
              className="rounded-lg border border-amber-200 bg-amber-50 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold text-amber-900">
                    {details.title}
                  </h3>

                  <p className="mt-1 text-sm text-amber-800">
                    {warning.message?.trim() || details.description}
                  </p>

                  {validTimestamp && (
                    <p className="mt-2 text-xs text-amber-700">
                      {timestamp.toLocaleTimeString()}
                    </p>
                  )}
                </div>

                {onDismiss && (
                  <button
                    type="button"
                    onClick={() => dismissWarning(warning.id)}
                    aria-label={`Dismiss ${details.title}`}
                    className="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-amber-800 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>

      <p className="text-xs text-slate-500">
        Proctoring alerts are recorded for examination review. Follow the
        examination rules and contact the examiner if you believe an alert
        is incorrect.
      </p>
    </section>
  );
}

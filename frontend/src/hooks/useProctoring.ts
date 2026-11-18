
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ProctoringEventType =
  | "tab_switch"
  | "window_blur"
  | "window_focus"
  | "face_not_detected"
  | "multiple_faces"
  | "gaze_away"
  | "webcam_error";

export interface ProctoringEvent {
  event_type: ProctoringEventType;
  description: string;
  timestamp: string;
  gaze_data?: Record<string, unknown> | null;
}

interface UseProctoringOptions {
  enabled: boolean;
  onEvent?: (event: ProctoringEvent) => void;
  maxTabWarnings?: number;
  duplicateEventCooldownMs?: number;
}

interface UseProctoringReturn {
  events: ProctoringEvent[];
  tabSwitchCount: number;
  warningCount: number;
  isAutoFlagged: boolean;
  isMonitoring: boolean;
  reportFaceNotDetected: () => void;
  reportMultipleFaces: () => void;
  reportGazeAway: (gazeData?: Record<string, unknown>) => void;
  reportWebcamError: (description?: string) => void;
  clearEvents: () => void;
}

export function useProctoring({
  enabled,
  onEvent,
  maxTabWarnings = 3,
  duplicateEventCooldownMs = 3000,
}: UseProctoringOptions): UseProctoringReturn {
  const [events, setEvents] = useState<ProctoringEvent[]>([]);
  const [tabSwitchCount, setTabSwitchCount] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [isAutoFlagged, setIsAutoFlagged] = useState(false);
  const tabSwitchCountRef = useRef(0);
  const autoFlaggedRef = useRef(false);
  const [isMonitoring, setIsMonitoring] = useState(false);

  const lastEventTimeRef = useRef<Record<string, number>>({});
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const reportEvent = useCallback(
    (
      eventType: ProctoringEventType,
      description: string,
      gazeData?: Record<string, unknown>
    ) => {
      if (!enabled || typeof window === "undefined") {
        return;
      }

      const now = Date.now();
      const previousTime = lastEventTimeRef.current[eventType] ?? 0;
      const cooldown = Math.max(0, duplicateEventCooldownMs);

      if (now - previousTime < cooldown) {
        return;
      }

      lastEventTimeRef.current[eventType] = now;

      const event: ProctoringEvent = {
        event_type: eventType,
        description,
        timestamp: new Date(now).toISOString(),
        ...(gazeData ? { gaze_data: gazeData } : {}),
      };

      setEvents((current) => [...current, event]);
      setWarningCount((current) => current + 1);

      if (eventType === "tab_switch") {
        tabSwitchCountRef.current += 1;
        setTabSwitchCount(tabSwitchCountRef.current);

        const threshold = Math.max(0, Math.floor(maxTabWarnings));
        if (
          threshold > 0
          && !autoFlaggedRef.current
          && tabSwitchCountRef.current >= threshold
        ) {
          autoFlaggedRef.current = true;
          setIsAutoFlagged(true);
        }
      }

      onEventRef.current?.(event);
    },
    [enabled, duplicateEventCooldownMs, maxTabWarnings]
  );

  const reportFaceNotDetected = useCallback(() => {
    reportEvent(
      "face_not_detected",
      "Candidate face was not detected by the webcam detector."
    );
  }, [reportEvent]);

  const reportMultipleFaces = useCallback(() => {
    reportEvent(
      "multiple_faces",
      "Multiple faces were detected in the webcam frame."
    );
  }, [reportEvent]);

  const reportGazeAway = useCallback(
    (gazeData?: Record<string, unknown>) => {
      reportEvent(
        "gaze_away",
        "Candidate gaze was detected away from the examination screen.",
        gazeData
      );
    },
    [reportEvent]
  );

  const reportWebcamError = useCallback(
    (description?: string) => {
      reportEvent(
        "webcam_error",
        description || "The examination webcam encountered an error."
      );
    },
    [reportEvent]
  );

  const clearEvents = useCallback(() => {
    setEvents([]);
    setTabSwitchCount(0);
    tabSwitchCountRef.current = 0;
    setWarningCount(0);
    setIsAutoFlagged(false);
    autoFlaggedRef.current = false;
    lastEventTimeRef.current = {};
  }, []);

  useEffect(() => {
    if (!enabled) {
      setIsMonitoring(false);
      return;
    }

    setIsMonitoring(true);

    function handleVisibilityChange() {
      if (document.visibilityState === "hidden") {
        reportEvent(
          "tab_switch",
          "The examination tab became hidden."
        );
      }
    }

    function handleWindowBlur() {
      reportEvent(
        "window_blur",
        "The examination window lost focus."
      );
    }

    function handleWindowFocus() {
      reportEvent(
        "window_focus",
        "The examination window regained focus."
      );
    }

    document.addEventListener(
      "visibilitychange",
      handleVisibilityChange
    );

    window.addEventListener("blur", handleWindowBlur);
    window.addEventListener("focus", handleWindowFocus);

    return () => {
      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange
      );

      window.removeEventListener("blur", handleWindowBlur);
      window.removeEventListener("focus", handleWindowFocus);

      setIsMonitoring(false);
    };
  }, [enabled, reportEvent]);

  return {
    events,
    tabSwitchCount,
    warningCount,
    isAutoFlagged,
    isMonitoring,
    reportFaceNotDetected,
    reportMultipleFaces,
    reportGazeAway,
    reportWebcamError,
    clearEvents,
  };
}

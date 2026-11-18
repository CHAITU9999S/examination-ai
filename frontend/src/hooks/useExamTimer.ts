
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseExamTimerOptions {
  initialSeconds: number;
  autoStart?: boolean;
  onExpire?: () => void;
}

interface UseExamTimerReturn {
  remainingSeconds: number;
  isRunning: boolean;
  isExpired: boolean;
  start: () => void;
  pause: () => void;
  reset: (seconds?: number) => void;
  formatTime: () => string;
}

function normalizeSeconds(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(0, Math.floor(value));
}

export function useExamTimer({
  initialSeconds,
  autoStart = true,
  onExpire,
}: UseExamTimerOptions): UseExamTimerReturn {
  const normalizedInitial = normalizeSeconds(initialSeconds);

  const [remainingSeconds, setRemainingSeconds] = useState(
    normalizedInitial
  );

  const [isRunning, setIsRunning] = useState(
    autoStart && normalizedInitial > 0
  );

  const [isExpired, setIsExpired] = useState(
    normalizedInitial === 0
  );

  const expiryCallbackRef = useRef(onExpire);
  const expiryCalledRef = useRef(normalizedInitial === 0);

  useEffect(() => {
    expiryCallbackRef.current = onExpire;
  }, [onExpire]);

  const handleExpiry = useCallback(() => {
    setRemainingSeconds(0);
    setIsRunning(false);
    setIsExpired(true);

    if (!expiryCalledRef.current) {
      expiryCalledRef.current = true;
      expiryCallbackRef.current?.();
    }
  }, []);

  useEffect(() => {
    if (!isRunning || isExpired) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setRemainingSeconds((current) => {
        if (current <= 1) {
          window.clearInterval(intervalId);
          handleExpiry();
          return 0;
        }

        return current - 1;
      });
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isRunning, isExpired, handleExpiry]);

  const start = useCallback(() => {
    if (remainingSeconds > 0 && !isExpired) {
      setIsRunning(true);
    }
  }, [remainingSeconds, isExpired]);

  const pause = useCallback(() => {
    setIsRunning(false);
  }, []);

  const reset = useCallback((seconds?: number) => {
    const nextSeconds = normalizeSeconds(
      seconds ?? normalizedInitial
    );

    expiryCalledRef.current = nextSeconds === 0;

    setRemainingSeconds(nextSeconds);
    setIsExpired(nextSeconds === 0);
    setIsRunning(nextSeconds > 0);
  }, [normalizedInitial]);

  const formatTime = useCallback(() => {
    const hours = Math.floor(remainingSeconds / 3600);
    const minutes = Math.floor((remainingSeconds % 3600) / 60);
    const seconds = remainingSeconds % 60;

    return [hours, minutes, seconds]
      .map((value) => String(value).padStart(2, "0"))
      .join(":");
  }, [remainingSeconds]);

  return {
    remainingSeconds,
    isRunning,
    isExpired,
    start,
    pause,
    reset,
    formatTime,
  };
}

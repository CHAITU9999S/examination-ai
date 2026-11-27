
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combines conditional CSS classes and resolves Tailwind conflicts.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Formats a valid date for display.
 */
export function formatDate(
  value: string | Date | null | undefined,
  locale = "en-IN"
): string {
  if (!value) {
    return "Not available";
  }

  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Invalid date";
  }

  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

/**
 * Formats a date and time for display.
 */
export function formatDateTime(
  value: string | Date | null | undefined,
  locale = "en-IN"
): string {
  if (!value) {
    return "Not available";
  }

  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Invalid date";
  }

  const utcDate = value instanceof Date
    ? value
    : new Date(typeof value === "string" && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value + "Z" : value);

  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(utcDate) + " IST";
}

/** Formats API timestamps (including naive UTC values) as Indian Standard Time. */
export function formatISTDateTime(
  value: string | Date | null | undefined,
  fallback = "Not available"
): string {
  if (!value) return fallback;
  const date = value instanceof Date
    ? value
    : new Date(typeof value === "string" && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value + "Z" : value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(date) + " IST";
}

/**
 * Formats seconds into HH:MM:SS.
 */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) {
    return "00:00:00";
  }

  const safeSeconds = Math.max(0, Math.floor(seconds));

  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;

  return [hours, minutes, remainingSeconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

/**
 * Calculates percentage safely.
 */
export function calculatePercentage(
  obtained: number,
  total: number
): number {
  if (
    !Number.isFinite(obtained) ||
    !Number.isFinite(total) ||
    total <= 0
  ) {
    return 0;
  }

  return Number(((obtained / total) * 100).toFixed(2));
}

/**
 * Formats a number with a maximum number of decimal places.
 */
export function formatNumber(
  value: number,
  maximumFractionDigits = 2
): string {
  if (!Number.isFinite(value)) {
    return "0";
  }

  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits,
  }).format(value);
}

/**
 * Truncates text to a maximum length.
 */
export function truncateText(
  value: string | null | undefined,
  maxLength = 100
): string {
  if (!value) {
    return "";
  }

  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, Math.max(0, maxLength)).trimEnd()}...`;
}

/**
 * Converts bytes into a readable file size.
 */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "0 Bytes";
  }

  if (bytes === 0) {
    return "0 Bytes";
  }

  const units = ["Bytes", "KB", "MB", "GB", "TB"];
  const unitIndex = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );

  const size = bytes / Math.pow(1024, unitIndex);

  return `${Number(size.toFixed(2))} ${units[unitIndex]}`;
}

/**
 * Returns true when a date falls between the supplied dates.
 */
export function isDateBetween(
  value: string | Date,
  start: string | Date,
  end: string | Date
): boolean {
  const currentDate = new Date(value).getTime();
  const startDate = new Date(start).getTime();
  const endDate = new Date(end).getTime();

  if (
    !Number.isFinite(currentDate) ||
    !Number.isFinite(startDate) ||
    !Number.isFinite(endDate)
  ) {
    return false;
  }

  return currentDate >= startDate && currentDate <= endDate;
}

/**
 * Creates a debounced version of a function.
 */
export function debounce<T extends (...args: never[]) => void>(
  callback: T,
  delay = 300
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      callback(...args);
    }, Math.max(0, delay));
  };
}

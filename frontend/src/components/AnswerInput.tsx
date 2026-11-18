
"use client";

import { useState, type ChangeEvent } from "react";

export type AnswerQuestionType =
  | "MCQ"
  | "multi_select"
  | "short_answer"
  | "long_answer"
  | "image_upload";

export interface AnswerOption {
  id: number;
  option_text: string;
}

interface AnswerInputProps {
  questionType: AnswerQuestionType;
  options?: AnswerOption[];
  value: string | string[];
  onChange: (value: string | string[]) => void;
  onImageSelected?: (file: File | null) => void;
  disabled?: boolean;
  maxImageSizeMB?: number;
}

export default function AnswerInput({
  questionType,
  options = [],
  value,
  onChange,
  onImageSelected,
  disabled = false,
  maxImageSizeMB = 10,
}: AnswerInputProps) {
  const [imageError, setImageError] = useState("");
  const [selectedFileName, setSelectedFileName] = useState("");

  function getSelectedValues(): string[] {
    if (Array.isArray(value)) {
      return value;
    }

    if (!value) {
      return [];
    }

    try {
      const parsed = JSON.parse(value);

      if (
        Array.isArray(parsed) &&
        parsed.every((item) => typeof item === "string")
      ) {
        return parsed;
      }
    } catch {
      // A non-JSON value is treated as a single selected value.
    }

    return [value];
  }

  function handleMultiSelect(optionId: number) {
    const selectedValues = getSelectedValues();
    const id = String(optionId);

    const updatedValues = selectedValues.includes(id)
      ? selectedValues.filter((item) => item !== id)
      : [...selectedValues, id];

    onChange(updatedValues);
  }

  function handleImageChange(
    event: ChangeEvent<HTMLInputElement>
  ) {
    setImageError("");

    const file = event.target.files?.[0];

    if (!file) {
      setSelectedFileName("");
      onImageSelected?.(null);
      return;
    }

    const allowedTypes = [
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/tiff",
      "image/bmp",
    ];

    if (!allowedTypes.includes(file.type)) {
      setImageError(
        "Unsupported image format. Upload JPEG, PNG, WEBP, TIFF or BMP."
      );
      event.target.value = "";
      setSelectedFileName("");
      onImageSelected?.(null);
      return;
    }

    if (file.size > maxImageSizeMB * 1024 * 1024) {
      setImageError(
        `Image size must not exceed ${maxImageSizeMB} MB.`
      );
      event.target.value = "";
      setSelectedFileName("");
      onImageSelected?.(null);
      return;
    }

    setSelectedFileName(file.name);
    onImageSelected?.(file);
  }

  if (questionType === "MCQ") {
    const selectedValue = Array.isArray(value)
      ? value[0] ?? ""
      : value;

    return (
      <fieldset
        disabled={disabled}
        className="space-y-3"
      >
        <legend className="mb-3 text-sm font-semibold text-slate-700">
          Select one answer
        </legend>

        {options.map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition ${
              selectedValue === String(option.id)
                ? "border-blue-500 bg-blue-50"
                : "border-slate-200 bg-white hover:bg-slate-50"
            } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
          >
            <input
              type="radio"
              name="exam-answer"
              value={option.id}
              checked={selectedValue === String(option.id)}
              onChange={() => onChange(String(option.id))}
              className="h-4 w-4 accent-blue-600"
            />

            <span className="text-sm text-slate-800">
              {option.option_text}
            </span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (questionType === "multi_select") {
    const selectedValues = getSelectedValues();

    return (
      <fieldset
        disabled={disabled}
        className="space-y-3"
      >
        <legend className="mb-3 text-sm font-semibold text-slate-700">
          Select all correct answers
        </legend>

        {options.map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition ${
              selectedValues.includes(String(option.id))
                ? "border-blue-500 bg-blue-50"
                : "border-slate-200 bg-white hover:bg-slate-50"
            } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
          >
            <input
              type="checkbox"
              value={option.id}
              checked={selectedValues.includes(String(option.id))}
              onChange={() => handleMultiSelect(option.id)}
              className="h-4 w-4 accent-blue-600"
            />

            <span className="text-sm text-slate-800">
              {option.option_text}
            </span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (questionType === "short_answer") {
    return (
      <div className="space-y-2">
        <label
          htmlFor="short-answer"
          className="block text-sm font-semibold text-slate-700"
        >
          Your Answer
        </label>

        <textarea
          id="short-answer"
          value={Array.isArray(value) ? "" : value}
          onChange={(event) => onChange(event.target.value)}
          rows={4}
          maxLength={10000}
          disabled={disabled}
          placeholder="Type your answer here..."
          className="w-full rounded-lg border border-slate-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
        />
      </div>
    );
  }

  if (questionType === "long_answer") {
    return (
      <div className="space-y-2">
        <label
          htmlFor="long-answer"
          className="block text-sm font-semibold text-slate-700"
        >
          Your Detailed Answer
        </label>

        <textarea
          id="long-answer"
          value={Array.isArray(value) ? "" : value}
          onChange={(event) => onChange(event.target.value)}
          rows={10}
          maxLength={100000}
          disabled={disabled}
          placeholder="Write your detailed answer here..."
          className="w-full rounded-lg border border-slate-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
        />
      </div>
    );
  }

  if (questionType === "image_upload") {
    return (
      <div className="space-y-3">
        <label
          htmlFor="image-answer"
          className="block text-sm font-semibold text-slate-700"
        >
          Upload Your Answer Image
        </label>

        <input
          id="image-answer"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp"
          onChange={handleImageChange}
          disabled={disabled}
          className="block w-full rounded-lg border border-slate-300 p-3 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:font-medium file:text-blue-700 disabled:bg-slate-100"
        />

        {selectedFileName && (
          <p className="text-sm text-green-700">
            Selected file: {selectedFileName}
          </p>
        )}

        {imageError && (
          <p role="alert" className="text-sm text-red-600">
            {imageError}
          </p>
        )}

        <p className="text-xs text-slate-500">
          Supported formats: JPEG, PNG, WEBP, TIFF and BMP.
          Maximum size: {maxImageSizeMB} MB.
        </p>
      </div>
    );
  }

  return (
    <p role="alert" className="text-sm text-red-600">
      Unsupported question type.
    </p>
  );
}


"use client";

import {
  useEffect,
  useState,
  type ChangeEvent,
} from "react";

interface ImageUploadProps {
  onFileSelect: (file: File | null) => void;
  maxSizeMB?: number;
  disabled?: boolean;
  acceptedTypes?: string[];
}

const DEFAULT_ACCEPTED_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/tiff",
  "image/bmp",
];

export default function ImageUpload({
  onFileSelect,
  maxSizeMB = 10,
  disabled = false,
  acceptedTypes = DEFAULT_ACCEPTED_TYPES,
}: ImageUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl("");
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  function handleFileChange(
    event: ChangeEvent<HTMLInputElement>
  ) {
    setError("");

    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    if (!acceptedTypes.includes(file.type)) {
      setError(
        "Unsupported image format. Please select a supported image."
      );
      event.target.value = "";
      return;
    }

    if (file.size === 0) {
      setError("The selected file is empty.");
      event.target.value = "";
      return;
    }

    if (file.size > maxSizeMB * 1024 * 1024) {
      setError(`Image size must not exceed ${maxSizeMB} MB.`);
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
    onFileSelect(file);
  }

  function removeFile() {
    setSelectedFile(null);
    setError("");
    onFileSelect(null);

    const input = document.getElementById(
      "exam-image-upload"
    ) as HTMLInputElement | null;

    if (input) {
      input.value = "";
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">
          Upload Answer Image
        </h3>

        <p className="mt-1 text-sm text-slate-500">
          Upload a clear photograph or scan of your handwritten answer.
        </p>
      </div>

      <label
        htmlFor="exam-image-upload"
        className={`flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-5 text-center transition hover:border-blue-500 hover:bg-blue-50 ${
          disabled ? "cursor-not-allowed opacity-50" : ""
        }`}
      >
        <span className="text-3xl" aria-hidden="true">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="36"
            height="36"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 16V4" />
            <path d="m7 9 5-5 5 5" />
            <path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" />
          </svg>
        </span>

        <span className="mt-2 text-sm font-semibold text-slate-700">
          Choose an image
        </span>

        <span className="mt-1 text-xs text-slate-500">
          JPEG, PNG, WEBP, TIFF or BMP · Maximum {maxSizeMB} MB
        </span>

        <input
          id="exam-image-upload"
          type="file"
          accept={acceptedTypes.join(",")}
          onChange={handleFileChange}
          disabled={disabled}
          className="sr-only"
        />
      </label>

      {error && (
        <p
          role="alert"
          className="rounded-lg bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      {selectedFile && (
        <div className="space-y-3 rounded-lg border border-green-200 bg-green-50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="break-all text-sm font-semibold text-slate-800">
                {selectedFile.name}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
              </p>
            </div>

            <button
              type="button"
              onClick={removeFile}
              disabled={disabled}
              className="rounded-lg px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
            >
              Remove
            </button>
          </div>

          {previewUrl && selectedFile.type !== "image/tiff" && selectedFile.type !== "image/bmp" && (
            <div>
              <p className="mb-2 text-xs font-medium text-slate-600">
                Image Preview
              </p>

              <img
                src={previewUrl}
                alt="Selected examination answer preview"
                className="max-h-72 w-full rounded-lg border border-slate-200 bg-white object-contain"
              />
            </div>
          )}

          <p className="text-xs font-medium text-green-700">
            Image selected. It will be uploaded when the parent form submits it.
          </p>
        </div>
      )}
    </section>
  );
}

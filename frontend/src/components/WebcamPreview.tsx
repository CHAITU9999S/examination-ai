
"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

interface WebcamPreviewProps {
  enabled?: boolean;
  onCameraStatusChange?: (
    status: "active" | "denied" | "unavailable" | "error"
  ) => void;
  onStreamReady?: (stream: MediaStream | null) => void;
  facingMode?: "user" | "environment";
  showPreview?: boolean;
  compact?: boolean;
}

export default function WebcamPreview({
  enabled = true,
  onCameraStatusChange,
  onStreamReady,
  facingMode = "user",
  showPreview = true,
  compact = false,
}: WebcamPreviewProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [status, setStatus] = useState<
    "loading" | "active" | "denied" | "unavailable" | "error" | "disabled"
  >("loading");

  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let mounted = true;

    async function startCamera() {
      if (!enabled) {
        setStatus("disabled");
        setErrorMessage("");
        onStreamReady?.(null);
        onCameraStatusChange?.("unavailable");
        return;
      }

      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices?.getUserMedia
      ) {
        setStatus("unavailable");
        setErrorMessage(
          "Your browser does not support webcam access. Use a supported browser over HTTPS."
        );
        onCameraStatusChange?.("unavailable");
        return;
      }

      setStatus("loading");
      setErrorMessage("");

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode,
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
        });

        if (!mounted) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        setStatus("active");
        onStreamReady?.(stream);
        onCameraStatusChange?.("active");
      } catch (error) {
        if (!mounted) {
          return;
        }

        const cameraError = error as DOMException;

        let message =
          "Unable to access the camera. Check your browser permissions.";

        let nextStatus: "denied" | "unavailable" | "error" = "error";

        if (cameraError.name === "NotAllowedError") {
          message =
            "Camera permission was denied. Allow camera access in your browser settings.";
          nextStatus = "denied";
        } else if (
          cameraError.name === "NotFoundError" ||
          cameraError.name === "DevicesNotFoundError"
        ) {
          message = "No camera was found on this device.";
          nextStatus = "unavailable";
        } else if (
          cameraError.name === "NotReadableError" ||
          cameraError.name === "TrackStartError"
        ) {
          message =
            "The camera is currently being used by another application.";
        }

        setStatus(nextStatus);
        setErrorMessage(message);
        onStreamReady?.(null);
        onCameraStatusChange?.(nextStatus);
      }
    }

    startCamera();

    return () => {
      mounted = false;

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }

      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }

      onStreamReady?.(null);
    };
  }, [
    enabled,
    facingMode,
    onCameraStatusChange,
    onStreamReady,
  ]);

  return (
    <section className={`overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ${compact ? "text-xs" : ""}`}>
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4">
        <h2 className="font-semibold text-slate-900">
          Webcam Proctoring
        </h2>

        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            status === "active"
              ? "bg-green-100 text-green-700"
              : status === "loading"
                ? "bg-blue-100 text-blue-700"
                : status === "disabled"
                  ? "bg-slate-100 text-slate-600"
                  : "bg-red-100 text-red-700"
          }`}
        >
          {status === "active"
            ? "Camera Active"
            : status === "loading"
              ? "Connecting..."
              : status === "disabled"
                ? "Disabled"
                : "Camera Unavailable"}
        </span>
      </div>

      <div className="relative aspect-video bg-slate-950">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="Live examination webcam preview"
          className={`h-full w-full object-cover ${
            status === "active" && showPreview ? "block" : "hidden"
          }`}
        />

        {(status !== "active" || !showPreview) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center px-5 text-center text-white">
            <span className="text-4xl" aria-hidden="true">
              {status === "loading" ? "⌛" : status === "active" ? "◉" : "📷"}
            </span>

            <p className="mt-3 text-sm font-medium">
              {status === "loading"
                ? "Starting webcam..."
                : status === "active" && !showPreview
                  ? "Preview hidden. Camera monitoring continues."
                  : status === "disabled"
                    ? "Webcam is disabled for this examination."
                    : "Webcam preview is unavailable."}
            </p>
          </div>
        )}
      </div>

      <div className="p-4">
        {status === "active" && (
          <p className="text-sm text-green-700">
            Your webcam is active for the examination.
          </p>
        )}

        {errorMessage && (
          <p role="alert" className="text-sm text-red-600">
            {errorMessage}
          </p>
        )}

        {status === "disabled" && (
          <p className="text-sm text-slate-500">
            Camera access is not requested while proctoring is disabled.
          </p>
        )}

        <p className="mt-2 text-xs text-slate-500">
          Camera access requires your permission and a secure HTTPS connection.
          Camera video is not automatically recorded or uploaded by this component.
        </p>
      </div>
    </section>
  );
}

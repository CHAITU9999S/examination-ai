"use client";

import { useEffect, useRef, useState } from "react";

interface FaceProctoringProps {
  stream: MediaStream | null;
  enabled: boolean;
  sensitivity?: number;
  onFaceMissing: () => void;
  onMultipleFaces: () => void;
  onGazeAway: (data: Record<string, unknown>) => void;
  onDetectorError: (message: string) => void;
}

type DetectorStatus = "idle" | "loading" | "ready" | "unavailable";

const WASM_ROOT =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

function point(landmarks: Array<{ x: number; y: number }>, index: number) {
  return landmarks[index];
}

interface HorizontalGazeEstimate {
  position: number;
  confidence: number;
}

function estimateHorizontalGaze(
  landmarks: Array<{ x: number; y: number }>
): HorizontalGazeEstimate | null {
  // Compare both iris positions relative to their own eye corners.
  // A large disagreement between the eyes is treated as unreliable.
  // This remains an approximate screen-attention heuristic.
  const leftIris = point(landmarks, 468);
  const leftOuter = point(landmarks, 33);
  const leftInner = point(landmarks, 133);
  const rightIris = point(landmarks, 473);
  const rightInner = point(landmarks, 362);
  const rightOuter = point(landmarks, 263);

  if (
    !leftIris || !leftOuter || !leftInner ||
    !rightIris || !rightInner || !rightOuter
  ) {
    return null;
  }

  const leftWidth = Math.abs(leftInner.x - leftOuter.x);
  const rightWidth = Math.abs(rightOuter.x - rightInner.x);

  if (leftWidth < 0.001 || rightWidth < 0.001) return null;

  const leftRatio =
    (leftIris.x - Math.min(leftOuter.x, leftInner.x)) / leftWidth;
  const rightRatio =
    (rightIris.x - Math.min(rightInner.x, rightOuter.x)) / rightWidth;

  if (
    !Number.isFinite(leftRatio) ||
    !Number.isFinite(rightRatio) ||
    leftRatio < -0.15 ||
    leftRatio > 1.15 ||
    rightRatio < -0.15 ||
    rightRatio > 1.15
  ) {
    return null;
  }

  const eyeDisagreement = Math.abs(leftRatio - rightRatio);
  if (eyeDisagreement > 0.25) return null;

  return {
    position: (leftRatio + rightRatio) / 2,
    confidence: Math.max(0, Math.min(1, 1 - eyeDisagreement / 0.25)),
  };
}

export default function FaceProctoring({
  stream,
  enabled,
  sensitivity = 0.5,
  onFaceMissing,
  onMultipleFaces,
  onGazeAway,
  onDetectorError,
}: FaceProctoringProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const lastDetectionRef = useRef(0);
  const missingSinceRef = useRef<number | null>(null);
  const gazeAwaySinceRef = useRef<number | null>(null);
  const gazeSamplesRef = useRef<HorizontalGazeEstimate[]>([]);
  const lastReportedRef = useRef<Record<string, number>>({});
  const [status, setStatus] = useState<DetectorStatus>("idle");

  useEffect(() => {
    if (!enabled || !stream) {
      setStatus("idle");
      return;
    }

    let cancelled = false;
    let landmarker: { detectForVideo: (video: HTMLVideoElement, timestamp: number) => { faceLandmarks?: Array<Array<{ x: number; y: number }>> }; close: () => void } | null = null;
    let video = videoRef.current;

    const reportWithCooldown = (
      key: string,
      callback: () => void,
      cooldownMs = 5000
    ) => {
      const now = Date.now();
      if (now - (lastReportedRef.current[key] || 0) < cooldownMs) return;
      lastReportedRef.current[key] = now;
      callback();
    };

    async function start() {
      setStatus("loading");
      gazeSamplesRef.current = [];
      gazeAwaySinceRef.current = null;
      missingSinceRef.current = null;

      try {
        if (!video) throw new Error("Video element is unavailable.");
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        await video.play();

        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks(WASM_ROOT);

        try {
          landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
            runningMode: "VIDEO",
            numFaces: 3,
            outputFaceBlendshapes: false,
          });
        } catch {
          landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
            runningMode: "VIDEO",
            numFaces: 3,
            outputFaceBlendshapes: false,
          });
        }

        if (cancelled) {
          landmarker.close();
          landmarker = null;
          return;
        }

        setStatus("ready");

        const threshold = Math.min(0.4, Math.max(0.2, 0.25 + sensitivity * 0.1));

        const detect = (now: number) => {
          if (cancelled || !landmarker || !video || video.readyState < 2) {
            animationRef.current = requestAnimationFrame(detect);
            return;
          }

          if (now - lastDetectionRef.current >= 150) {
            lastDetectionRef.current = now;

            try {
              const result = landmarker.detectForVideo(video, now);
              const faces = result.faceLandmarks || [];

              if (faces.length === 0) {
                if (missingSinceRef.current === null) missingSinceRef.current = now;
                if (now - missingSinceRef.current >= 1500) {
                  reportWithCooldown("missing", onFaceMissing);
                }
                gazeAwaySinceRef.current = null;
              } else {
                missingSinceRef.current = null;
              }

              if (faces.length > 1) {
                reportWithCooldown("multiple", onMultipleFaces, 7000);
              }

              if (faces.length === 1) {
                const estimate = estimateHorizontalGaze(faces[0]);

                if (estimate) {
                  gazeSamplesRef.current = [
                    ...gazeSamplesRef.current.slice(-6),
                    estimate,
                  ];

                  // Smooth short-lived landmark jitter before classifying gaze.
                  const samples = gazeSamplesRef.current;
                  const smoothedGaze = samples.reduce(
                    (total, sample) => total + sample.position,
                    0
                  ) / samples.length;
                  const averageConfidence = samples.reduce(
                    (total, sample) => total + sample.confidence,
                    0
                  ) / samples.length;

                  const lookingAway =
                    smoothedGaze < threshold ||
                    smoothedGaze > 1 - threshold;

                  if (lookingAway && samples.length >= 4) {
                    if (gazeAwaySinceRef.current === null) {
                      gazeAwaySinceRef.current = now;
                    }

                    if (now - gazeAwaySinceRef.current >= 1200) {
                      reportWithCooldown("gaze", () => onGazeAway({
                        direction: smoothedGaze < threshold ? "left" : "right",
                        normalized_horizontal_position: Number(smoothedGaze.toFixed(3)),
                        confidence: Number(averageConfidence.toFixed(2)),
                        consistent_samples: samples.length,
                        detector: "mediapipe_face_landmarker",
                        estimation: "bilateral_iris_ratio_smoothed",
                      }));
                    }
                  } else {
                    gazeAwaySinceRef.current = null;
                  }
                } else {
                  gazeSamplesRef.current = [];
                  gazeAwaySinceRef.current = null;
                }
              } else {
                gazeSamplesRef.current = [];
                gazeAwaySinceRef.current = null;
              }
            } catch (error) {
              const message = error instanceof Error ? error.message : "Face detector failed.";
              reportWithCooldown("detector-error", () => onDetectorError(message), 15000);
            }
          }

          animationRef.current = requestAnimationFrame(detect);
        };

        animationRef.current = requestAnimationFrame(detect);
      } catch (error) {
        if (cancelled) return;
        setStatus("unavailable");
        const message = error instanceof Error
          ? error.message
          : "Unable to initialize the face detector.";
        onDetectorError(message);
      }
    }

    void start();

    return () => {
      cancelled = true;
      if (animationRef.current !== null) cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
      if (landmarker) landmarker.close();
      if (video) video.srcObject = null;
    };
  }, [
    stream,
    enabled,
    sensitivity,
    onFaceMissing,
    onMultipleFaces,
    onGazeAway,
    onDetectorError,
  ]);

  if (!enabled) return null;

  return (
    <div className="rounded-lg border border-white/10 bg-slate-800/70 p-3">
      <video ref={videoRef} muted autoPlay playsInline className="hidden" />
      <p className="text-xs text-slate-300">
        Face and gaze analysis:{" "}
        <span className={status === "ready" ? "font-semibold text-green-400" : "font-semibold text-amber-300"}>
          {status === "ready"
            ? "Active (on this device)"
            : status === "loading"
              ? "Loading detector..."
              : status === "unavailable"
                ? "Unavailable"
                : "Waiting for camera"}
        </span>
      </p>
      <p className="mt-1 text-[11px] text-slate-400">
        Camera frames are analysed locally in this browser and are not uploaded by this detector.
        Gaze checks are approximate and may be affected by lighting, glasses, and camera position.
      </p>
    </div>
  );
}

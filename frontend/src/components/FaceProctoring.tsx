"use client";

import { useEffect, useRef, useState } from "react";

interface FaceProctoringProps {
  stream: MediaStream | null;
  enabled: boolean;
  sensitivity?: number;
  onFaceMissing: () => void;
  onFaceVerified: () => void;
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

interface GazeEstimate {
  horizontalPosition: number;
  verticalPosition: number;
  confidence: number;
}

function estimateGaze(
  landmarks: Array<{ x: number; y: number }>
): GazeEstimate | null {
  // Compare both iris positions relative to each eye's own corners and lids.
  // Large left/right or up/down disagreement is treated as unreliable.
  // This remains an approximate screen-attention heuristic.
  const leftIris = point(landmarks, 468);
  const leftOuter = point(landmarks, 33);
  const leftInner = point(landmarks, 133);
  const leftTop = point(landmarks, 159);
  const leftBottom = point(landmarks, 145);
  const rightIris = point(landmarks, 473);
  const rightInner = point(landmarks, 362);
  const rightOuter = point(landmarks, 263);
  const rightTop = point(landmarks, 386);
  const rightBottom = point(landmarks, 374);

  if (
    !leftIris || !leftOuter || !leftInner || !leftTop || !leftBottom ||
    !rightIris || !rightInner || !rightOuter || !rightTop || !rightBottom
  ) {
    return null;
  }

  const leftWidth = Math.abs(leftInner.x - leftOuter.x);
  const rightWidth = Math.abs(rightOuter.x - rightInner.x);
  const leftHeight = Math.abs(leftBottom.y - leftTop.y);
  const rightHeight = Math.abs(rightBottom.y - rightTop.y);

  if (
    leftWidth < 0.001 || rightWidth < 0.001 ||
    leftHeight < 0.001 || rightHeight < 0.001
  ) {
    return null;
  }

  const leftHorizontal =
    (leftIris.x - Math.min(leftOuter.x, leftInner.x)) / leftWidth;
  const rightHorizontal =
    (rightIris.x - Math.min(rightInner.x, rightOuter.x)) / rightWidth;
  const leftVertical =
    (leftIris.y - Math.min(leftTop.y, leftBottom.y)) / leftHeight;
  const rightVertical =
    (rightIris.y - Math.min(rightTop.y, rightBottom.y)) / rightHeight;

  const ratios = [
    leftHorizontal,
    rightHorizontal,
    leftVertical,
    rightVertical,
  ];

  if (
    ratios.some((ratio) =>
      !Number.isFinite(ratio) || ratio < -0.15 || ratio > 1.15
    )
  ) {
    return null;
  }

  const horizontalDisagreement = Math.abs(
    leftHorizontal - rightHorizontal
  );
  const verticalDisagreement = Math.abs(
    leftVertical - rightVertical
  );

  if (
    horizontalDisagreement > 0.25 ||
    verticalDisagreement > 0.35
  ) {
    return null;
  }

  const horizontalConfidence = 1 - horizontalDisagreement / 0.25;
  const verticalConfidence = 1 - verticalDisagreement / 0.35;

  return {
    horizontalPosition: (leftHorizontal + rightHorizontal) / 2,
    verticalPosition: (leftVertical + rightVertical) / 2,
    confidence: Math.max(
      0,
      Math.min(1, horizontalConfidence, verticalConfidence)
    ),
  };
}

export default function FaceProctoring({
  stream,
  enabled,
  sensitivity = 0.5,
  onFaceMissing,
  onFaceVerified,
  onMultipleFaces,
  onGazeAway,
  onDetectorError,
}: FaceProctoringProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const lastDetectionRef = useRef(0);
  const missingSinceRef = useRef<number | null>(null);
  const facePresentSinceRef = useRef<number | null>(null);
  const faceVerifiedRef = useRef(false);
  const gazeAwaySinceRef = useRef<number | null>(null);
  const gazeSamplesRef = useRef<GazeEstimate[]>([]);
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
      facePresentSinceRef.current = null;
      faceVerifiedRef.current = false;

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
                facePresentSinceRef.current = null;
                if (missingSinceRef.current === null) missingSinceRef.current = now;
                if (now - missingSinceRef.current >= 1500) {
                  reportWithCooldown("missing", onFaceMissing);
                }
                gazeAwaySinceRef.current = null;
              } else {
                missingSinceRef.current = null;
              }

              if (faces.length > 1) {
                facePresentSinceRef.current = null;
                reportWithCooldown("multiple", onMultipleFaces, 7000);
              }

              if (faces.length === 1) {
                // Require one continuously detected face for at least one
                // second before marking the exam-entry face check complete.
                if (facePresentSinceRef.current === null) {
                  facePresentSinceRef.current = now;
                }
                if (
                  !faceVerifiedRef.current &&
                  now - facePresentSinceRef.current >= 1000
                ) {
                  faceVerifiedRef.current = true;
                  onFaceVerified();
                }

                const estimate = estimateGaze(faces[0]);

                if (estimate) {
                  gazeSamplesRef.current = [
                    ...gazeSamplesRef.current.slice(-6),
                    estimate,
                  ];

                  // Smooth short-lived landmark jitter before classifying gaze.
                  const samples = gazeSamplesRef.current;
                  const smoothedHorizontal = samples.reduce(
                    (total, sample) => total + sample.horizontalPosition,
                    0
                  ) / samples.length;
                  const smoothedVertical = samples.reduce(
                    (total, sample) => total + sample.verticalPosition,
                    0
                  ) / samples.length;
                  const averageConfidence = samples.reduce(
                    (total, sample) => total + sample.confidence,
                    0
                  ) / samples.length;

                  const horizontalAway =
                    smoothedHorizontal < threshold ||
                    smoothedHorizontal > 1 - threshold;
                  const verticalAway =
                    smoothedVertical < threshold ||
                    smoothedVertical > 1 - threshold;
                  const lookingAway = horizontalAway || verticalAway;

                  if (lookingAway && samples.length >= 4) {
                    if (gazeAwaySinceRef.current === null) {
                      gazeAwaySinceRef.current = now;
                    }

                    if (now - gazeAwaySinceRef.current >= 1200) {
                      reportWithCooldown("gaze", () => onGazeAway({
                        direction: horizontalAway
                          ? (smoothedHorizontal < threshold ? "left" : "right")
                          : (smoothedVertical < threshold ? "up" : "down"),
                        normalized_horizontal_position: Number(smoothedHorizontal.toFixed(3)),
                        normalized_vertical_position: Number(smoothedVertical.toFixed(3)),
                        confidence: Number(averageConfidence.toFixed(2)),
                        consistent_samples: samples.length,
                        detector: "mediapipe_face_landmarker",
                        estimation: "bilateral_iris_ratio_2d_smoothed",
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
    onFaceVerified,
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

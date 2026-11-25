"use client";

import { useEffect, useRef, useState } from "react";

interface FaceProctoringProps {
  stream: MediaStream | null;
  enabled: boolean;
  sensitivity?: number;
  onFaceMissing: () => void;
  onFaceVerified: (photo: Blob) => void;
  onMultipleFaces: () => void;
  onGazeAway: (data: Record<string, unknown>) => void;
  onDetectorError: (message: string) => void;
}

type DetectorStatus = "idle" | "loading" | "ready" | "unavailable";

interface NormalizedPoint {
  x: number;
  y: number;
}

interface GazeEstimate {
  horizontalPosition: number;
  verticalPosition: number;
  confidence: number;
}

interface DetectedFace {
  keypoints: Array<{ x: number; y: number }>;
}

interface FaceLandmarksDetector {
  estimateFaces(
    input: HTMLVideoElement,
    estimationConfig?: { flipHorizontal?: boolean }
  ): Promise<DetectedFace[]>;
  dispose(): void;
}

function estimateGaze(
  landmarks: NormalizedPoint[]
): GazeEstimate | null {
  // Iris positions are compared against each eye's own corners and eyelids.
  // Large disagreement between the two eyes is treated as unreliable.
  // This is an approximate attention heuristic, not calibrated eye tracking.
  const leftIris = landmarks[468];
  const leftOuter = landmarks[33];
  const leftInner = landmarks[133];
  const leftTop = landmarks[159];
  const leftBottom = landmarks[145];
  const rightIris = landmarks[473];
  const rightInner = landmarks[362];
  const rightOuter = landmarks[263];
  const rightTop = landmarks[386];
  const rightBottom = landmarks[374];

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

  if (horizontalDisagreement > 0.25 || verticalDisagreement > 0.35) {
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
  const [alertMessage, setAlertMessage] = useState("");

  useEffect(() => {
    if (!enabled || !stream) {
      setStatus("idle");
      return;
    }

    let cancelled = false;
    let detector: FaceLandmarksDetector | null = null;
    const video = videoRef.current;

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

    const scheduleNextFrame = () => {
      if (!cancelled) {
        animationRef.current = requestAnimationFrame(detect);
      }
    };

    const processFaces = (
      faces: DetectedFace[],
      now: number,
      videoElement: HTMLVideoElement
    ) => {
      if (faces.length === 0) {
        facePresentSinceRef.current = null;
        if (missingSinceRef.current === null) {
          missingSinceRef.current = now;
        }
        if (now - missingSinceRef.current >= 1500) {
          setAlertMessage("Face not detected. Keep your face clearly visible in the webcam.");
          reportWithCooldown("missing", onFaceMissing);
        }
        gazeAwaySinceRef.current = null;
        gazeSamplesRef.current = [];
        return;
      }

      missingSinceRef.current = null;

      if (faces.length > 1) {
        setAlertMessage("Multiple faces detected. Only the candidate should be visible.");
        facePresentSinceRef.current = null;
        reportWithCooldown("multiple", onMultipleFaces, 7000);
        gazeAwaySinceRef.current = null;
        gazeSamplesRef.current = [];
        return;
      }

      setAlertMessage("");

      // Require one continuously detected face for at least one second
      // before marking the exam-entry face-presence check complete.
      if (facePresentSinceRef.current === null) {
        facePresentSinceRef.current = now;
      }

      if (
        !faceVerifiedRef.current &&
        now - facePresentSinceRef.current >= 1000
      ) {
        faceVerifiedRef.current = true;
        const captureCanvas = document.createElement("canvas");
        captureCanvas.width = videoElement.videoWidth;
        captureCanvas.height = videoElement.videoHeight;
        const captureContext = captureCanvas.getContext("2d");
        if (captureContext && captureCanvas.width > 0 && captureCanvas.height > 0) {
          captureContext.drawImage(videoElement, 0, 0, captureCanvas.width, captureCanvas.height);
          captureCanvas.toBlob((photo) => {
            if (photo && !cancelled) onFaceVerified(photo);
          }, "image/jpeg", 0.82);
        } else {
          onDetectorError("The camera frame could not be captured. Please retry the photo.");
        }
      }

      const width = videoElement.videoWidth;
      const height = videoElement.videoHeight;
      if (!width || !height || faces[0].keypoints.length < 478) {
        gazeSamplesRef.current = [];
        gazeAwaySinceRef.current = null;
        return;
      }

      // TensorFlow.js returns pixel coordinates. Convert to normalized
      // coordinates so the gaze ratios are independent of camera resolution.
      const normalizedLandmarks = faces[0].keypoints.map((keypoint) => ({
        x: keypoint.x / width,
        y: keypoint.y / height,
      }));

      const estimate = estimateGaze(normalizedLandmarks);
      if (!estimate) {
        gazeSamplesRef.current = [];
        gazeAwaySinceRef.current = null;
        return;
      }

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

      const threshold = Math.min(
        0.4,
        Math.max(0.2, 0.25 + sensitivity * 0.1)
      );
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
          setAlertMessage("Please look toward the examination screen.");
          reportWithCooldown("gaze", () => onGazeAway({
            direction: horizontalAway
              ? (smoothedHorizontal < threshold ? "left" : "right")
              : (smoothedVertical < threshold ? "up" : "down"),
            normalized_horizontal_position: Number(
              smoothedHorizontal.toFixed(3)
            ),
            normalized_vertical_position: Number(
              smoothedVertical.toFixed(3)
            ),
            confidence: Number(averageConfidence.toFixed(2)),
            consistent_samples: samples.length,
            detector: "mediapipe_face_mesh_tensorflow_js",
            runtime: "tensorflowjs_webgl_or_cpu",
            estimation: "bilateral_iris_ratio_2d_smoothed",
          }));
        }
      } else {
        gazeAwaySinceRef.current = null;
        setAlertMessage("");
      }
    };

    function detect(now: number) {
      if (cancelled || !detector || !video || video.readyState < 2) {
        scheduleNextFrame();
        return;
      }

      if (now - lastDetectionRef.current < 150) {
        scheduleNextFrame();
        return;
      }

      lastDetectionRef.current = now;

      // Do not overlap asynchronous model inference calls.
      void detector.estimateFaces(video, { flipHorizontal: false })
        .then((faces) => {
          if (!cancelled) {
            processFaces(faces, now, video);
          }
        })
        .catch((error: unknown) => {
          if (cancelled) return;
          const message = error instanceof Error
            ? error.message
            : "Face detector failed.";
          reportWithCooldown(
            "detector-error",
            () => onDetectorError(message),
            15000
          );
        })
        .finally(scheduleNextFrame);
    }

    async function start() {
      setStatus("loading");
      setAlertMessage("");
      gazeSamplesRef.current = [];
      gazeAwaySinceRef.current = null;
      missingSinceRef.current = null;
      facePresentSinceRef.current = null;
      faceVerifiedRef.current = false;
      lastDetectionRef.current = 0;

      try {
        if (!video) {
          throw new Error("Video element is unavailable.");
        }

        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        await video.play();

        // Load TensorFlow.js and register its browser inference backends.
        const tf = await import("@tensorflow/tfjs-core");
        await import("@tensorflow/tfjs-converter");
        await import("@tensorflow/tfjs-backend-webgl");
        await import("@tensorflow/tfjs-backend-cpu");
        await import("@mediapipe/face_mesh");

        let backendReady = false;
        try {
          backendReady = await tf.setBackend("webgl");
        } catch {
          backendReady = false;
        }

        if (!backendReady) {
          backendReady = await tf.setBackend("cpu");
        }

        if (!backendReady) {
          throw new Error("TensorFlow.js could not initialize WebGL or CPU.");
        }

        await tf.ready();

        const faceLandmarksDetection = await import(
          "@tensorflow-models/face-landmarks-detection"
        );

        detector = await faceLandmarksDetection.createDetector(
          faceLandmarksDetection.SupportedModels.MediaPipeFaceMesh,
          {
            runtime: "tfjs",
            maxFaces: 3,
            refineLandmarks: true,
          }
        );

        if (cancelled) {
          detector.dispose();
          detector = null;
          return;
        }

        setStatus("ready");
        animationRef.current = requestAnimationFrame(detect);
      } catch (error) {
        if (cancelled) return;
        setStatus("unavailable");
        const message = error instanceof Error
          ? error.message
          : "Unable to initialize the TensorFlow.js face detector.";
        setAlertMessage("Proctoring detector unavailable: " + message);
        onDetectorError(message);
      }
    }

    void start();

    return () => {
      cancelled = true;
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
      }
      animationRef.current = null;
      detector?.dispose();
      if (video) {
        video.pause();
        video.srcObject = null;
      }
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
            ? "Active (TensorFlow.js on this device)"
            : status === "loading"
              ? "Loading TensorFlow.js detector..."
              : status === "unavailable"
                ? "Unavailable"
                : "Waiting for camera"}
        </span>
      </p>
      {alertMessage && (
        <p role="alert" aria-live="assertive" className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          {alertMessage}
        </p>
      )}
      <p className="mt-1 text-[11px] text-slate-400">
        MediaPipe FaceMesh runs through the TensorFlow.js runtime in this browser.
        Camera frames are analysed locally and are not uploaded. Gaze checks are
        approximate and may be affected by lighting, glasses, and camera position.
      </p>
    </div>
  );
}

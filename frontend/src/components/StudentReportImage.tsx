"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function StudentReportImage({ url, alt }: { url: string; alt: string }) {
  const [imageUrl, setImageUrl] = useState("");

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    const token = localStorage.getItem("examguard_access_token");
    if (!token) return;
    fetch(API_URL + url, { headers: { Authorization: "Bearer " + token }, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load report image.");
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setImageUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(() => { if (!cancelled) setImageUrl(""); });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [url]);

  return imageUrl ? <img src={imageUrl} alt={alt} className="mt-3 max-h-80 max-w-full rounded-lg border border-white/10 object-contain" /> : null;
}

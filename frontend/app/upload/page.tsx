"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import VideoUploader from "@/components/VideoUploader";
import ProcessingProgress from "@/components/ProcessingProgress";
import { uploadVideo, startProcessing, getVideoStatus } from "@/lib/api";
import { VideoStatusOut } from "@/types";

type Phase = "idle" | "uploading" | "processing" | "done" | "error";

export default function UploadPage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [videoId, setVideoId] = useState<number | null>(null);
  const [status, setStatus] = useState<VideoStatusOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const router = useRouter();

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setPhase("uploading");
      try {
        const video = await uploadVideo(file);
        setVideoId(video.id);
        await startProcessing(video.id);
        setPhase("processing");

        pollRef.current = setInterval(async () => {
          try {
            const s = await getVideoStatus(video.id);
            setStatus(s);
            if (s.status === "complete" || s.status === "failed") {
              stopPolling();
              setPhase(s.status === "complete" ? "done" : "error");
            }
          } catch {
            // transient network hiccup while polling — keep trying
          }
        }, 1500);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
        setPhase("error");
      }
    },
    [stopPolling]
  );

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <div className="font-tech text-xs tracking-[0.3em] text-[var(--color-amber)] uppercase mb-2">
          Step 1 of 2
        </div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">
          Upload CCTV footage
        </h1>
      </div>

      {phase === "idle" && <VideoUploader onFileSelected={handleFile} />}

      {phase === "uploading" && (
        <div className="border border-[var(--color-line)] bg-[var(--color-panel)] rounded-md p-10 text-center font-tech text-[var(--color-text-muted)] text-sm">
          Uploading video…
        </div>
      )}

      {(phase === "processing" || phase === "done") && status && (
        <ProcessingProgress status={status} />
      )}

      {phase === "error" && (
        <div className="border border-[var(--color-red)]/40 bg-[var(--color-red)]/5 rounded-md p-6">
          <p className="text-[var(--color-red)] font-tech text-sm">
            {status?.error_message || error || "Something went wrong."}
          </p>
        </div>
      )}

      {phase === "done" && videoId && (
        <div className="mt-6 flex justify-end">
          <button
            onClick={() => router.push("/search")}
            className="px-6 py-3 rounded bg-[var(--color-amber)] text-[#0a0d0b] font-tech text-sm tracking-widest uppercase hover:brightness-110 transition"
          >
            Go to Search →
          </button>
        </div>
      )}
    </div>
  );
}

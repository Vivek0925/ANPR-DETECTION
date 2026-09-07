"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Detection } from "@/types";
import { mediaUrl } from "@/lib/api";

interface Props {
  detection: Detection;
}

export default function VideoViewer({ detection }: Props) {
  return <VideoViewerInner key={detection.id} detection={detection} />;
}

function VideoViewerInner({ detection }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const router = useRouter();
  const [seeked, setSeeked] = useState(false);

  const videoUrl = mediaUrl(detection.video_url);

  const doSeek = () => {
    const video = videoRef.current;
    if (!video || seeked) return;
    video.currentTime = detection.timestamp_seconds;
    setSeeked(true);
  };

  return (
    <div>
      <button
        onClick={() => router.push("/search")}
        className="font-tech text-xs uppercase tracking-widest text-[var(--color-text-muted)] hover:text-[var(--color-amber)] mb-6 inline-flex items-center gap-2 transition-colors"
      >
        ← Back to results
      </button>

      <div className="grid md:grid-cols-[1fr_280px] gap-6">
        <div className="reticle border border-[var(--color-line)] bg-black rounded-md overflow-hidden">
          <span className="rt-tl" />
          <span className="rt-br" />
          {videoUrl ? (
            <video
              ref={videoRef}
              src={videoUrl}
              controls
              autoPlay
              onLoadedMetadata={doSeek}
              onCanPlay={doSeek}
              className="w-full aspect-video bg-black"
            />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-[var(--color-text-muted)] font-tech text-sm">
              Video source unavailable
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <div className="border border-[var(--color-line)] bg-[var(--color-panel)] rounded-md p-4">
            <div className="font-tech text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)] mb-2">
              Detected Vehicle
            </div>
            <div className="font-tech text-3xl text-[var(--color-amber)] tracking-wider mb-1">
              {detection.plate_number}
            </div>
            <div className="text-sm text-[var(--color-text-muted)] capitalize">
              {detection.vehicle_type ?? "vehicle"}
            </div>
          </div>

          <div className="border border-[var(--color-line)] bg-[var(--color-panel)] rounded-md p-4">
            <div className="font-tech text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)] mb-2">
              Timestamp
            </div>
            <div className="font-tech text-3xl text-[var(--color-text)]">
              {detection.formatted_timestamp}
            </div>
          </div>

          {mediaUrl(detection.plate_crop_url) && (
            <div className="reticle border border-[var(--color-line)] bg-[var(--color-panel)] rounded-md p-3">
              <span className="rt-tl" />
              <span className="rt-br" />
              <div className="font-tech text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)] mb-2">
                Plate Snapshot
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={mediaUrl(detection.plate_crop_url) ?? undefined}
                alt={detection.plate_number ?? "Plate snapshot"}
                className="w-full rounded border border-[var(--color-line)]"
              />
            </div>
          )}

          <div className="border border-[var(--color-line)] bg-[var(--color-panel)] rounded-md p-4 text-xs font-tech text-[var(--color-text-muted)] space-y-1">
            <div className="flex justify-between">
              <span>Source File</span>
              <span className="text-[var(--color-text)] truncate ml-2">
                {detection.video_filename}
              </span>
            </div>
            <div className="flex justify-between">
              <span>OCR Confidence</span>
              <span className="text-[var(--color-text)]">
                {detection.ocr_confidence !== null
                  ? `${Math.round(detection.ocr_confidence * 100)}%`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Detection Confidence</span>
              <span className="text-[var(--color-text)]">
                {detection.detection_confidence !== null
                  ? `${Math.round(detection.detection_confidence * 100)}%`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Frame #</span>
              <span className="text-[var(--color-text)]">
                {detection.frame_number}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

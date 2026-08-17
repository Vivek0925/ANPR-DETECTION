"use client";

import { VideoStatusOut } from "@/types";

interface Props {
  status: VideoStatusOut;
}

const BAR_WIDTH = 40;

function asciiBar(percent: number): string {
  const filled = Math.round((percent / 100) * BAR_WIDTH);
  return "█".repeat(filled) + "░".repeat(Math.max(0, BAR_WIDTH - filled));
}

export default function ProcessingProgress({ status }: Props) {
  const isFailed = status.status === "failed";
  const isComplete = status.status === "complete";

  return (
    <div className="reticle border border-[var(--color-line)] bg-[var(--color-panel)] rounded-md p-6">
      <span className="rt-tl" />
      <span className="rt-br" />

      <div className="flex items-center justify-between mb-4">
        <span className="font-tech text-xs tracking-[0.3em] uppercase text-[var(--color-text-muted)]">
          {isFailed
            ? "Processing Failed"
            : isComplete
              ? "Processing Complete"
              : "Processing CCTV..."}
        </span>
        <span
          className={`font-tech text-xs px-2 py-0.5 rounded ${
            isFailed
              ? "bg-[var(--color-red)]/15 text-[var(--color-red)]"
              : isComplete
                ? "bg-[var(--color-green)]/15 text-[var(--color-green)]"
                : "bg-[var(--color-amber)]/15 text-[var(--color-amber)]"
          }`}
        >
          {status.status.toUpperCase()}
        </span>
      </div>

      {isFailed ? (
        <p className="text-[var(--color-red)] text-sm font-tech leading-relaxed">
          {status.error_message || "Unknown error."}
        </p>
      ) : (
        <>
          <div className="font-tech text-[var(--color-amber)] text-sm mb-2 select-none">
            {asciiBar(status.progress_percent)}{" "}
            {status.progress_percent.toFixed(0)}%
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 text-sm">
            <Stat label="Duration" value={fmtDuration(status.duration)} />
            <Stat label="Frames Processed" value={status.frames_processed} />
            <Stat
              label="Vehicles / Events"
              value={status.vehicle_events_detected}
            />
            <Stat label="Frame Detections" value={status.vehicles_detected} />
            <Stat label="Unique Plates" value={status.unique_plates} />
          </div>
        </>
      )}
    </div>
  );
}

function fmtDuration(d: number | null): string {
  if (d === null || Number.isNaN(d)) return "—";
  const m = Math.floor(d / 60);
  const s = Math.floor(d % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-[var(--color-text-muted)] text-xs uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className="font-tech text-lg text-[var(--color-text)]">{value}</div>
    </div>
  );
}

"use client";

import { DetectionOut } from "@/types";
import { mediaUrl } from "@/lib/api";
import { useRouter } from "next/navigation";

interface Props {
  plateNumber: string;
  results: DetectionOut[];
}

export default function SearchResults({ plateNumber, results }: Props) {
  const router = useRouter();

  if (results.length === 0) {
    return (
      <div className="border border-dashed border-[var(--color-line)] rounded-md p-10 text-center">
        <p className="font-tech text-[var(--color-text-muted)] text-sm">
          No appearances found for{" "}
          <span className="text-[var(--color-amber)]">{plateNumber}</span>
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-4 border-b border-[var(--color-line)] pb-3">
        <h2 className="font-tech text-xl text-[var(--color-amber)] tracking-wider">
          {plateNumber}
        </h2>
        <span className="font-tech text-sm text-[var(--color-text-muted)]">
          {results.length} appearance{results.length !== 1 ? "s" : ""} found
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {results.map((r) => {
          const thumb = mediaUrl(r.snapshot_url) || mediaUrl(r.plate_crop_url);
          return (
            <button
              key={r.id}
              onClick={() =>
                router.push(
                  `/viewer?detection=${r.id}`
                )
              }
              className="reticle text-left flex items-center gap-4 border border-[var(--color-line)] bg-[var(--color-panel)] hover:bg-[var(--color-panel-raised)] hover:border-[var(--color-amber)]/50 rounded-md p-4 transition-colors group"
            >
              <span className="rt-tl opacity-0 group-hover:opacity-90 transition-opacity" />
              <span className="rt-br opacity-0 group-hover:opacity-90 transition-opacity" />

              {thumb ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={thumb}
                  alt={r.plate_number}
                  className="w-20 h-14 object-cover rounded border border-[var(--color-line)] flex-shrink-0"
                />
              ) : (
                <div className="w-20 h-14 rounded border border-[var(--color-line)] flex-shrink-0 flex items-center justify-center text-[var(--color-text-muted)] text-xs font-tech">
                  no img
                </div>
              )}

              <div className="flex-1 min-w-0">
                <div className="font-tech text-2xl text-[var(--color-text)] tracking-wide">
                  {r.formatted_timestamp}
                </div>
                <div className="text-sm text-[var(--color-text-muted)] truncate">
                  {r.video_filename} &middot; {r.vehicle_type ?? "vehicle"}
                </div>
              </div>

              <div className="text-right flex-shrink-0">
                <div className="font-tech text-sm text-[var(--color-green)]">
                  {r.ocr_confidence !== null
                    ? `${Math.round(r.ocr_confidence * 100)}%`
                    : "—"}
                </div>
                <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wide mt-1">
                  View Video
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

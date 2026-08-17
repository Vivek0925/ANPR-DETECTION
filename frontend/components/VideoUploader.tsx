"use client";

import { useCallback, useRef, useState } from "react";

interface Props {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function VideoUploader({ onFileSelected, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      onFileSelected(files[0]);
    },
    [onFileSelected]
  );

  return (
    <div
      className={`reticle scanline-bg border border-dashed rounded-md p-14 text-center transition-colors cursor-pointer ${
        dragging
          ? "border-[var(--color-amber)] bg-[var(--color-amber)]/5"
          : "border-[var(--color-line)] bg-[var(--color-panel)]"
      } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
    >
      <span className="rt-tl" />
      <span className="rt-br" />
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/avi,video/quicktime,video/x-matroska,video/webm"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <div className="font-tech text-xs tracking-[0.3em] text-[var(--color-amber)] uppercase mb-3">
        Feed Intake
      </div>
      <p className="text-[var(--color-text)] mb-1">
        Drop a CCTV recording here, or click to browse
      </p>
      <p className="text-sm text-[var(--color-text-muted)] font-tech">
        .mp4 &middot; .avi &middot; .mov &middot; .mkv &middot; .webm
      </p>
    </div>
  );
}

"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import VideoViewer from "@/components/VideoViewer";
import { getDetection } from "@/lib/api";
import type { Detection } from "@/types";

function ViewerPageInner() {
  const params = useSearchParams();
  const detectionId = params.get("detection");

  const [detection, setDetection] = useState<Detection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!detectionId) return;
    getDetection(Number(detectionId))
      .then(setDetection)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [detectionId]);

  if (!detectionId) {
    return (
      <p className="text-sm text-[var(--color-text-muted)] font-tech">
        No detection selected. Go back to search and pick a result.
      </p>
    );
  }

  if (error) {
    return (
      <div className="border border-[var(--color-red)]/40 bg-[var(--color-red)]/5 rounded-md p-6">
        <p className="text-[var(--color-red)] font-tech text-sm">{error}</p>
      </div>
    );
  }

  if (!detection) {
    return (
      <p className="text-sm text-[var(--color-text-muted)] font-tech">
        Loading footage…
      </p>
    );
  }

  return <VideoViewer detection={detection} />;
}

export default function ViewerPage() {
  return (
    <Suspense fallback={null}>
      <ViewerPageInner />
    </Suspense>
  );
}

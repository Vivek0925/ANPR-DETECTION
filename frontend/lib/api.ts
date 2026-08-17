import {
  VideoOut,
  VideoStatusOut,
  SearchResultOut,
  DetectionOut,
} from "@/types";

// The backend URL. Configure via NEXT_PUBLIC_API_BASE_URL in .env.local for
// non-default setups; defaults to the local FastAPI dev server.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadVideo(file: File): Promise<VideoOut> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/videos/upload`, {
    method: "POST",
    body: formData,
  });
  return handle<VideoOut>(res);
}

export async function startProcessing(videoId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/videos/${videoId}/process`, {
    method: "POST",
  });
  await handle(res);
}

export async function getVideoStatus(
  videoId: number
): Promise<VideoStatusOut> {
  const res = await fetch(`${API_BASE}/videos/${videoId}/status`);
  return handle<VideoStatusOut>(res);
}

export async function listVideos(): Promise<VideoOut[]> {
  const res = await fetch(`${API_BASE}/videos`);
  return handle<VideoOut[]>(res);
}

export async function searchPlate(plate: string): Promise<SearchResultOut> {
  const res = await fetch(
    `${API_BASE}/search?plate=${encodeURIComponent(plate)}`
  );
  return handle<SearchResultOut>(res);
}

export async function getDetection(id: number): Promise<DetectionOut> {
  const res = await fetch(`${API_BASE}/detections/${id}`);
  return handle<DetectionOut>(res);
}

export function mediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export { API_BASE };

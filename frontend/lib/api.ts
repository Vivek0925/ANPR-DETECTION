import type {
  DashboardStats,
  Detection,
  SearchResult,
  Video,
  VideoStatus,
} from "@/types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";


async function request<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {

  const response = await fetch(
    `${API_URL}${endpoint}`,
    {
      ...options,
      cache: "no-store",
    }
  );


  if (!response.ok) {

    let message =
      `Request failed (${response.status})`;

    try {

      const data =
        await response.json();

      if (data?.detail) {
        message = data.detail;
      }

    } catch {
      // Keep default error.
    }

    throw new Error(message);
  }


  return response.json();
}


/* ========================================================= */
/* BACKEND HEALTH */
/* ========================================================= */

export async function checkBackend(): Promise<boolean> {

  try {

    await request("/");

    return true;

  } catch {

    return false;
  }
}


/* ========================================================= */
/* DASHBOARD */
/* ========================================================= */

export async function getDashboardStats() {

  return request<DashboardStats>(
    "/dashboard/stats"
  );
}


export async function getRecentDetections(
  limit = 6
) {

  return request<Detection[]>(
    `/detections/recent?limit=${limit}`
  );
}

export async function getDetection(
  detectionId: number
) {

  return request<Detection>(
    `/detections/${detectionId}`
  );
}


/* ========================================================= */
/* VIDEOS */
/* ========================================================= */

export async function getVideos() {

  return request<Video[]>(
    "/videos"
  );
}


export async function getVideo(
  videoId: number
) {

  return request<Video>(
    `/videos/${videoId}`
  );
}


export async function getVideoStatus(
  videoId: number
) {

  return request<VideoStatus>(
    `/videos/${videoId}/status`
  );
}


/* ========================================================= */
/* UPLOAD */
/* ========================================================= */

export async function uploadVideo(
  file: File
): Promise<Video> {

  const formData =
    new FormData();

  formData.append(
    "file",
    file
  );


  const response =
    await fetch(
      `${API_URL}/videos/upload`,
      {
        method: "POST",
        body: formData,
      }
    );


  if (!response.ok) {

    let message =
      "Video upload failed.";

    try {

      const data =
        await response.json();

      if (data?.detail) {
        message = data.detail;
      }

    } catch {
      // Ignore JSON parsing error.
    }

    throw new Error(message);
  }


  return response.json();
}


/* ========================================================= */
/* PROCESS VIDEO */
/* ========================================================= */

export async function processVideo(
  videoId: number
) {

  return request(
    `/videos/${videoId}/process`,
    {
      method: "POST",
    }
  );
}


/* ========================================================= */
/* SEARCH */
/* ========================================================= */

export async function searchPlate(
  plate: string
) {

  return request<SearchResult>(
    `/search?plate=${encodeURIComponent(
      plate
    )}`
  );
}


/* ========================================================= */
/* MEDIA URL */
/* ========================================================= */

export function getMediaUrl(
  path: string | null
) {

  if (!path) {
    return null;
  }


  if (
    path.startsWith("http://") ||
    path.startsWith("https://")
  ) {

    return path;
  }


  return `${API_URL}${path}`;
}

export const mediaUrl = getMediaUrl;

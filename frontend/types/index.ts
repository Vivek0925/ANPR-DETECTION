export type VideoStatus = "pending" | "processing" | "complete" | "failed";

export interface VideoOut {
  id: number;
  filename: string;
  duration: number | null;
  fps: number | null;
  total_frames: number | null;
  uploaded_at: string;
  status: VideoStatus;
  error_message: string | null;
  frames_processed: number;
  vehicles_detected: number;
  vehicle_events_detected: number;
  plates_recognized: number;
  progress_percent: number;
}

export interface VideoStatusOut {
  id: number;
  status: VideoStatus;
  progress_percent: number;
  frames_processed: number;
  vehicles_detected: number;
  vehicle_events_detected: number;
  plates_recognized: number;
  unique_plates: number;
  error_message: string | null;
  duration: number | null;
}

export interface DetectionOut {
  id: number;
  video_id: number;
  video_filename: string;
  plate_number: string;
  raw_ocr_text: string | null;
  timestamp_seconds: number;
  formatted_timestamp: string;
  frame_number: number;
  track_id: number | null;
  event_start_seconds: number | null;
  event_end_seconds: number | null;
  vehicle_type: string | null;
  ocr_confidence: number | null;
  detection_confidence: number | null;
  snapshot_url: string | null;
  plate_crop_url: string | null;
  video_url: string | null;
}

export interface SearchResultOut {
  plate_number: string;
  total_appearances: number;
  results: DetectionOut[];
}

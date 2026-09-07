export type DashboardStats = {
  total_videos: number;
  total_vehicles: number;
  total_plates: number;
  unique_plates: number;
  processing: number;
  completed: number;
  failed: number;
};

export type Video = {
  id: number;
  filename: string;
  filepath: string;
  status: string;

  uploaded_at?: string | null;

  duration?: number | null;

  frames_processed?: number | null;

  vehicles_detected?: number | null;

  vehicle_events_detected?: number | null;

  plates_recognized?: number | null;

  progress_percent?: number | null;

  error_message?: string | null;
};

export type VideoStatus = {
  id: number;

  status: string;

  progress_percent: number;

  frames_processed: number;

  vehicles_detected: number;

  vehicle_events_detected: number;

  plates_recognized: number;

  unique_plates: number;

  error_message?: string | null;

  duration?: number | null;
};

export type Detection = {
  id: number;

  video_id: number;

  video_filename: string;

  plate_number: string | null;

  raw_ocr_text: string | null;

  timestamp_seconds: number;

  formatted_timestamp: string;

  frame_number: number | null;

  track_id: number | null;

  event_start_seconds: number | null;

  event_end_seconds: number | null;

  vehicle_type: string | null;

  ocr_confidence: number | null;

  detection_confidence: number | null;

  snapshot_url: string | null;

  plate_crop_url: string | null;

  video_url: string;
};

export type DetectionOut = Detection;
export type VideoOut = Video;
export type VideoStatusOut = VideoStatus;
export type SearchResultOut = SearchResult;

export type SearchResult = {
  plate_number: string;

  total_appearances: number;

  results: Detection[];
};
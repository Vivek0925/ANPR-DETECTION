"use client";

import {
  ChangeEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ArrowLeft,
  CheckCircle2,
  FileVideo,
  Loader2,
  ShieldCheck,
  UploadCloud,
  X,
  XCircle,
} from "lucide-react";

import {
  getVideoStatus,
  processVideo,
  uploadVideo,
} from "@/lib/api";

import type {
  VideoStatus,
} from "@/types";


const ALLOWED_EXTENSIONS = [
  ".mp4",
  ".avi",
  ".mov",
  ".mkv",
  ".webm",
];


export default function UploadPage() {

  const router = useRouter();

  const inputRef =
    useRef<HTMLInputElement>(null);

  const [file, setFile] =
    useState<File | null>(null);

  const [dragging, setDragging] =
    useState(false);

  const [uploading, setUploading] =
    useState(false);

  const [videoId, setVideoId] =
    useState<number | null>(null);

  const [status, setStatus] =
    useState<VideoStatus | null>(null);

  const [error, setError] =
    useState("");

  const [complete, setComplete] =
    useState(false);


  // --------------------------------------------------
  // Select file
  // --------------------------------------------------

  function selectFile(
    selectedFile: File
  ) {

    const extension =
      selectedFile.name
        .substring(
          selectedFile.name.lastIndexOf(".")
        )
        .toLowerCase();

    if (
      !ALLOWED_EXTENSIONS.includes(
        extension
      )
    ) {

      setError(
        "Unsupported video format."
      );

      return;
    }

    setError("");

    setFile(selectedFile);

    setComplete(false);

    setStatus(null);
  }


  // --------------------------------------------------
  // File input
  // --------------------------------------------------

  function handleInput(
    event: ChangeEvent<HTMLInputElement>
  ) {

    const selected =
      event.target.files?.[0];

    if (selected) {
      selectFile(selected);
    }
  }


  // --------------------------------------------------
  // Drag/drop
  // --------------------------------------------------

  function handleDrop(
    event: React.DragEvent<HTMLDivElement>
  ) {

    event.preventDefault();

    setDragging(false);

    const dropped =
      event.dataTransfer.files?.[0];

    if (dropped) {
      selectFile(dropped);
    }
  }


  // --------------------------------------------------
  // Upload
  // --------------------------------------------------

  async function startUpload() {

    if (!file) {

      setError(
        "Please select a video first."
      );

      return;
    }

    try {

      setError("");

      setUploading(true);

      setComplete(false);

      // --------------------------------------------
      // Upload video
      // --------------------------------------------

      const uploaded =
        await uploadVideo(file);

      setVideoId(
        uploaded.id
      );

      // --------------------------------------------
      // Start AI processing
      // --------------------------------------------

      await processVideo(
        uploaded.id
      );

    } catch (err) {

      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Upload failed."
      );

      setUploading(false);
    }
  }


  // --------------------------------------------------
  // Poll backend
  // --------------------------------------------------

  useEffect(() => {

    if (videoId === null) {
      return;
    }

    const targetId = videoId;
    let active = true;

    async function poll() {

      try {

        const current =
          await getVideoStatus(
            targetId
          );

        if (!active) {
          return;
        }

        setStatus(current);

        // --------------------------------------------
        // IMPORTANT:
        //
        // Backend uses "complete", not "completed".
        // --------------------------------------------

        if (
          current.status === "complete" ||
          current.status === "completed"
        ) {

          setComplete(true);

          setUploading(false);

          // ------------------------------------------
          // Give the backend a moment to commit the
          // final detection rows, then open Search.
          // ------------------------------------------

          setTimeout(() => {

            router.push(
              "/search"
            );

          }, 800);

          return;
        }

        // --------------------------------------------
        // Failed
        // --------------------------------------------

        if (
          current.status === "failed"
        ) {

          setError(
            current.error_message ||
            "Video processing failed."
          );

          setUploading(false);

          return;
        }

      } catch (err) {

        console.error(err);

        setError(
          "Unable to retrieve processing status."
        );
      }
    }


    // Run immediately
    poll();


    // Then every 1 second
    const interval =
      setInterval(
        poll,
        1000
      );


    return () => {

      active = false;

      clearInterval(interval);
    };

  }, [videoId, router]);


  // --------------------------------------------------
  // Reset
  // --------------------------------------------------

  function reset() {

    setFile(null);

    setVideoId(null);

    setStatus(null);

    setComplete(false);

    setUploading(false);

    setError("");

    if (inputRef.current) {

      inputRef.current.value = "";
    }
  }


  // --------------------------------------------------
  // UI
  // --------------------------------------------------

  return (

    <div className="app-shell">

      {/* HEADER */}

      <header className="header">

        <Link
          href="/"
          className="logo"
        >

          <div className="logo-mark">

            <ShieldCheck
              size={21}
            />

          </div>

          <div>

            <strong>
              CCTV / RETRIEVAL
            </strong>

            <span>
              AI Vehicle Surveillance
            </span>

          </div>

        </Link>


        <nav className="main-nav">

          <Link href="/">
            Dashboard
          </Link>

          <Link
            href="/upload"
            className="active"
          >
            Upload
          </Link>

          <Link href="/search">
            Search
          </Link>

          <Link href="/history">
            History
          </Link>

        </nav>


        <div className="header-status">

          <span className="status-dot online" />

          Backend

        </div>

      </header>


      {/* MAIN */}

      <main className="form-page">

        <Link
          href="/"
          className="back-link"
        >

          <ArrowLeft size={16} />

          Dashboard

        </Link>


        <div className="form-heading">

          <p className="eyebrow">
            VIDEO ANALYSIS
          </p>

          <h1>
            Upload CCTV footage
          </h1>

          <p>
            Upload a traffic or CCTV video
            for vehicle and license plate
            detection.
          </p>

        </div>


        {/* ERROR */}

        {error && (

          <div className="error-message">

            <XCircle size={17} />

            {error}

          </div>

        )}


        {/* DROP ZONE */}

        {!file && !uploading ? (

          <div
            className={`drop-zone ${
              dragging
                ? "dragging"
                : ""
            }`}

            onDragOver={(event) => {

              event.preventDefault();

              setDragging(true);

            }}

            onDragLeave={() =>
              setDragging(false)
            }

            onDrop={handleDrop}

            onClick={() =>
              inputRef.current?.click()
            }
          >

            <div className="upload-icon">

              <UploadCloud
                size={29}
              />

            </div>


            <h2>
              Drop your video here
            </h2>

            <p>
              or click to browse files
            </p>

            <small>
              MP4, AVI, MOV, MKV or WEBM
            </small>


            <input
              ref={inputRef}
              type="file"
              accept="video/*"
              hidden
              onChange={handleInput}
            />

          </div>

        ) : (

          <div className="upload-card">

            {/* FILE */}

            <div className="selected-file">

              <div className="file-icon">

                <FileVideo
                  size={22}
                />

              </div>


              <div>

                <strong>
                  {file?.name}
                </strong>

                <span>

                  {file
                    ? formatFileSize(
                        file.size
                      )
                    : ""}

                </span>

              </div>


              {!uploading &&
                !complete && (

                  <button
                    onClick={reset}
                    className="icon-button"
                  >

                    <X size={18} />

                  </button>

                )}

            </div>


            {/* START */}

            {!uploading &&
              !complete && (

                <button
                  className="green-button full"
                  onClick={startUpload}
                >

                  <UploadCloud
                    size={18}
                  />

                  Upload & Start Analysis

                </button>

              )}


            {/* PROCESSING */}

            {uploading && status && (

              <div className="processing-section">

                <div className="processing-title">

                  <span>

                    {status.status ===
                    "complete"
                      ? "Processing complete"
                      : "Processing CCTV footage..."}

                  </span>

                  <strong>

                    {Math.round(
                      status.progress_percent
                    )}

                    %

                  </strong>

                </div>


                <div className="large-progress">

                  <span
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(
                          0,
                          status.progress_percent
                        )
                      )}%`,
                    }}
                  />

                </div>


                <div className="processing-stats">

                  <div>

                    <span>
                      Frames
                    </span>

                    <strong>
                      {
                        status.frames_processed
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Vehicles
                    </span>

                    <strong>
                      {
                        status.vehicles_detected
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Plates
                    </span>

                    <strong>
                      {
                        status.plates_recognized
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Unique
                    </span>

                    <strong>
                      {
                        status.unique_plates
                      }
                    </strong>

                  </div>

                </div>


                <div
                  style={{
                    marginTop: "18px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#15803d",
                    fontSize: "14px",
                  }}
                >

                  <Loader2
                    size={16}
                    className="animate-spin"
                  />

                  AI is analyzing the footage...

                </div>

              </div>

            )}


            {/* COMPLETE */}

            {complete && (

              <div className="complete-section">

                <CheckCircle2
                  size={42}
                />

                <h2>
                  Processing complete
                </h2>

                <p>
                  Your CCTV footage has
                  been analyzed successfully.
                </p>

                <p
                  style={{
                    color: "#15803d",
                    fontSize: "14px",
                    marginTop: "8px",
                  }}
                >
                  Opening plate search...
                </p>


                <div className="complete-actions">

                  <Link
                    href="/search"
                    className="green-button"
                  >
                    Search Plates
                  </Link>

                  <Link
                    href="/history"
                    className="outline-button"
                  >
                    View History
                  </Link>

                </div>

              </div>

            )}

          </div>

        )}

      </main>

    </div>
  );
}


// --------------------------------------------------
// File size
// --------------------------------------------------

function formatFileSize(
  bytes: number
) {

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {

    return `${(
      bytes / 1024
    ).toFixed(1)} KB`;
  }

  return `${(
    bytes /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}
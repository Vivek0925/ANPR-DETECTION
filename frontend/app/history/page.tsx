"use client";

import {
  useEffect,
  useState,
} from "react";

import Link from "next/link";

import {
  ArrowLeft,
  Clock3,
  FileVideo,
  History as HistoryIcon,
  ShieldCheck,
  Upload,
} from "lucide-react";

import {
  getVideos,
} from "@/lib/api";

import type {
  Video,
} from "@/types";


export default function HistoryPage() {

  const [videos, setVideos] =
    useState<Video[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


  async function loadVideos() {

    try {

      setError("");

      const data =
        await getVideos();

      setVideos(data);

    } catch (err) {

      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load history."
      );

    } finally {

      setLoading(false);

    }

  }


  useEffect(() => {

    loadVideos();


    const interval =
      setInterval(
        loadVideos,
        5000
      );


    return () =>
      clearInterval(interval);

  }, []);


  return (

    <div className="app-shell">

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

          <Link href="/upload">
            Upload
          </Link>

          <Link href="/search">
            Search
          </Link>

          <Link
            href="/history"
            className="active"
          >
            History
          </Link>

        </nav>


        <div className="header-status">

          <span className="status-dot online" />

          Backend

        </div>

      </header>


      <main className="form-page">

        <Link
          href="/"
          className="back-link"
        >

          <ArrowLeft size={16} />

          Dashboard

        </Link>


        <div className="page-heading">

          <div>

            <p className="eyebrow">
              VIDEO HISTORY
            </p>

            <h1>
              History
            </h1>

            <p>
              Previously uploaded CCTV
              footage and processing results.
            </p>

          </div>


          <Link
            href="/upload"
            className="green-button"
          >

            <Upload size={17} />

            Upload Footage

          </Link>

        </div>


        {error && (

          <div className="error-message">
            {error}
          </div>

        )}


        <section className="history-panel">

          {loading ? (

            <div className="history-empty">

              Loading history...

            </div>

          ) : videos.length === 0 ? (

            <div className="history-empty">

              <HistoryIcon
                size={32}
              />

              <strong>
                No video history
              </strong>

              <span>
                Uploaded videos will
                appear here.
              </span>


              <Link
                href="/upload"
                className="green-button"
              >

                Upload your first video

              </Link>

            </div>

          ) : (

            <div className="history-table">

              <div className="history-head">

                <span>
                  VIDEO
                </span>

                <span>
                  STATUS
                </span>

                <span>
                  VEHICLES
                </span>

                <span>
                  PLATES
                </span>

                <span>
                  PROGRESS
                </span>

                <span>
                  DURATION
                </span>

              </div>


              {videos.map(
                (video) => (

                  <div
                    className="history-row"
                    key={video.id}
                  >

                    <div className="history-file">

                      <div className="history-file-icon">

                        <FileVideo
                          size={19}
                        />

                      </div>


                      <div>

                        <strong
                          title={
                            video.filename
                          }
                        >

                          {video.filename}

                        </strong>

                        {video.uploaded_at && (

                          <span>

                            {formatDate(
                              video.uploaded_at
                            )}

                          </span>

                        )}

                      </div>

                    </div>


                    <StatusBadge
                      status={
                        video.status
                      }
                    />


                    <span>
                      {
                        video
                          .vehicles_detected ??
                        0
                      }
                    </span>


                    <span>
                      {
                        video
                          .plates_recognized ??
                        0
                      }
                    </span>


                    <span>

                      {Math.round(
                        video
                          .progress_percent ??
                        0
                      )}
                      %

                    </span>


                    <span className="duration">

                      <Clock3
                        size={14}
                      />

                      {formatDuration(
                        video.duration
                      )}

                    </span>

                  </div>

                )
              )}

            </div>

          )}

        </section>

      </main>

    </div>
  );
}


function StatusBadge({
  status,
}: {
  status: string;
}) {

  return (

    <span
      className={`status-badge ${
        status.toLowerCase()
      }`}
    >

      <span />

      {status}

    </span>

  );
}


function formatDate(
  date: string
) {

  const parsed =
    new Date(date);


  if (
    Number.isNaN(
      parsed.getTime()
    )
  ) {

    return date;

  }


  return parsed.toLocaleString(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    }
  );
}


function formatDuration(
  seconds?: number | null
) {

  if (
    seconds == null ||
    !Number.isFinite(seconds)
  ) {

    return "—";

  }


  const total =
    Math.floor(seconds);

  const hours =
    Math.floor(
      total / 3600
    );

  const minutes =
    Math.floor(
      (total % 3600) / 60
    );

  const secs =
    total % 60;


  if (hours > 0) {

    return [
      hours,
      String(minutes).padStart(
        2,
        "0"
      ),
      String(secs).padStart(
        2,
        "0"
      ),
    ].join(":");

  }


  return [
    String(minutes).padStart(
      2,
      "0"
    ),
    String(secs).padStart(
      2,
      "0"
    ),
  ].join(":");
}
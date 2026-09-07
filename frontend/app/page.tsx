"use client";

import {
  useEffect,
  useState,
} from "react";

import Link from "next/link";

import {
  ArrowRight,
  CarFront,
  CheckCircle2,
  Clock3,
  FileVideo,
  History,
  Search,
  ShieldCheck,
  Upload,
  Video,
  Wifi,
  XCircle,
} from "lucide-react";

import {
  checkBackend,
  getDashboardStats,
  getRecentDetections,
  getVideos,
  getMediaUrl,
} from "@/lib/api";

import type {
  DashboardStats,
  Detection,
  Video as VideoType,
} from "@/types";


export default function Dashboard() {

  const [stats, setStats] =
    useState<DashboardStats | null>(
      null
    );

  const [detections, setDetections] =
    useState<Detection[]>([]);

  const [videos, setVideos] =
    useState<VideoType[]>([]);

  const [backendOnline, setBackendOnline] =
    useState(false);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


  async function loadDashboard() {

    try {

      setError("");


      const online =
        await checkBackend();

      setBackendOnline(online);


      if (!online) {

        setStats(null);

        setDetections([]);

        setVideos([]);

        setError(
          "Unable to connect to the ANPR backend."
        );

        return;
      }


      const [
        statsData,
        detectionData,
        videoData,
      ] = await Promise.all([

        getDashboardStats(),

        getRecentDetections(6),

        getVideos(),

      ]);


      setStats(statsData);

      setDetections(
        detectionData
      );

      setVideos(
        videoData
      );


    } catch (err) {

      console.error(err);

      setBackendOnline(false);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load dashboard."
      );

    } finally {

      setLoading(false);

    }
  }


  useEffect(() => {

    loadDashboard();


    const interval =
      setInterval(
        loadDashboard,
        5000
      );


    return () =>
      clearInterval(interval);

  }, []);


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

          <Link
            href="/"
            className="active"
          >
            Dashboard
          </Link>

          <Link href="/upload">
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

          <span
            className={
              backendOnline
                ? "status-dot online"
                : "status-dot offline"
            }
          />

          {backendOnline
            ? "Backend Connected"
            : "Backend Offline"}

        </div>

      </header>


      {/* MAIN */}

      <main className="main-content">

        {/* TITLE */}

        <section className="page-heading">

          <div>

            <p className="eyebrow">
              OVERVIEW
            </p>

            <h1>
              Dashboard
            </h1>

            <p>
              AI vehicle surveillance
              and plate recognition.
            </p>

          </div>


          <Link
            href="/upload"
            className="green-button"
          >

            <Upload size={17} />

            Upload Footage

          </Link>

        </section>


        {/* ERROR */}

        {error && (

          <div className="error-message">

            <XCircle size={17} />

            {error}

          </div>

        )}


        {/* STATS */}

        <section className="stats">

          <Stat
            icon={
              <CarFront
                size={19}
              />
            }
            label="Vehicles Detected"
            value={
              loading
                ? "—"
                : String(
                    stats
                      ?.total_vehicles ??
                    0
                  )
            }
          />


          <Stat
            icon={
              <CreditCardIcon />
            }
            label="Plates Recognized"
            value={
              loading
                ? "—"
                : String(
                    stats
                      ?.total_plates ??
                    0
                  )
            }
          />


          <Stat
            icon={
              <ShieldCheck
                size={19}
              />
            }
            label="Unique Plates"
            value={
              loading
                ? "—"
                : String(
                    stats
                      ?.unique_plates ??
                    0
                  )
            }
          />


          <Stat
            icon={
              <Video size={19} />
            }
            label="Videos Processed"
            value={
              loading
                ? "—"
                : String(
                    stats
                      ?.completed ??
                    0
                  )
            }
          />

        </section>


        {/* DETECTIONS + PROCESSING */}

        <section className="two-column">


          {/* DETECTIONS */}

          <div className="panel">

            <div className="panel-header">

              <div>

                <h2>
                  Recent Detections
                </h2>

                <p>
                  Latest recognized
                  plates
                </p>

              </div>


              <Link href="/search">

                View all

                <ArrowRight
                  size={15}
                />

              </Link>

            </div>


            {detections.length === 0 ? (

              <EmptyState
                icon={
                  <Search
                    size={24}
                  />
                }
                title="No detections yet"
                text="Process a CCTV video to see plate detections here."
              />

            ) : (

              <div className="detection-list">

                {detections.map(
                  (detection) => (

                    <div
                      className="detection-row"
                      key={
                        detection.id
                      }
                    >

                      <div className="plate-icon">

                        <CarFront
                          size={18}
                        />

                      </div>


                      <div className="detection-main">

                        <strong>

                          {detection
                            .plate_number ||
                            detection
                              .raw_ocr_text ||
                            "Not recognized"}

                        </strong>

                        <span>

                          {detection
                            .vehicle_type ||
                            "Vehicle"}

                          {" · "}

                          {
                            detection
                              .video_filename
                          }

                        </span>

                      </div>


                      <div className="detection-time">

                        <Clock3
                          size={14}
                        />

                        {
                          detection
                            .formatted_timestamp
                        }

                      </div>

                    </div>

                  )
                )}

              </div>

            )}

          </div>


          {/* PROCESSING */}

          <div className="panel">

            <div className="panel-header">

              <div>

                <h2>
                  Processing
                </h2>

                <p>
                  Current system status
                </p>

              </div>

              <Wifi
                size={18}
                className={
                  backendOnline
                    ? "green-icon"
                    : ""
                }
              />

            </div>


            {stats &&
            stats.processing > 0 ? (

              <div className="processing-box">

                <div className="progress-number">

                  <strong>
                    Processing
                  </strong>

                  <span>
                    {stats.processing}
                    {" "}
                    video
                    {stats.processing !==
                    1
                      ? "s"
                      : ""}
                  </span>

                </div>


                <div className="processing-line">

                  <span />

                </div>


                <div className="processing-info">

                  <span>
                    Videos currently
                    processing
                  </span>

                  <strong>
                    {stats.processing}
                  </strong>

                </div>

              </div>

            ) : (

              <div className="idle-processing">

                <CheckCircle2
                  size={32}
                />

                <strong>
                  No active processing
                </strong>

                <span>
                  Upload a CCTV video
                  to begin analysis.
                </span>

                <Link
                  href="/upload"
                  className="small-button"
                >
                  Upload video
                </Link>

              </div>

            )}

          </div>

        </section>


        {/* RECENT VIDEOS */}

        <section className="panel videos-panel">

          <div className="panel-header">

            <div>

              <h2>
                Recent Videos
              </h2>

              <p>
                Uploaded CCTV footage
              </p>

            </div>


            <Link href="/history">

              View all

              <ArrowRight
                size={15}
              />

            </Link>

          </div>


          {videos.length === 0 ? (

            <EmptyState
              icon={
                <FileVideo
                  size={24}
                />
              }
              title="No videos uploaded"
              text="Upload CCTV footage to start your first analysis."
            />

          ) : (

            <div className="video-table">

              <div className="table-head">

                <span>
                  FILE
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

              </div>


              {videos
                .slice(0, 5)
                .map((video) => (

                  <div
                    className="video-row"
                    key={video.id}
                  >

                    <div className="file-cell">

                      <FileVideo
                        size={18}
                      />

                      <span
                        title={
                          video.filename
                        }
                      >
                        {video.filename}
                      </span>

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


                    <div className="mini-progress">

                      <div>

                        <span
                          style={{
                            width: `${Math.min(
                              100,
                              Math.max(
                                0,
                                video
                                  .progress_percent ??
                                0
                              )
                            )}%`,
                          }}
                        />

                      </div>

                      <small>
                        {Math.round(
                          video
                            .progress_percent ??
                          0
                        )}
                        %
                      </small>

                    </div>

                  </div>

                ))}

            </div>

          )}

        </section>

      </main>

    </div>
  );
}


/* ========================================================= */
/* STAT */
/* ========================================================= */

function Stat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {

  return (

    <div className="stat">

      <div className="stat-icon">
        {icon}
      </div>

      <div>

        <span>
          {label}
        </span>

        <strong>
          {value}
        </strong>

      </div>

    </div>

  );
}


/* ========================================================= */
/* EMPTY */
/* ========================================================= */

function EmptyState({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {

  return (

    <div className="empty-state">

      <div className="empty-icon">
        {icon}
      </div>

      <strong>
        {title}
      </strong>

      <span>
        {text}
      </span>

    </div>

  );
}


/* ========================================================= */
/* STATUS */
/* ========================================================= */

function StatusBadge({
  status,
}: {
  status: string;
}) {

  const normalized =
    status.toLowerCase();


  return (

    <span
      className={`status-badge ${normalized}`}
    >

      <span />

      {status}

    </span>

  );
}


/* ========================================================= */
/* ICON */
/* ========================================================= */

function CreditCardIcon() {

  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >

      <rect
        x="3"
        y="5"
        width="18"
        height="14"
        rx="2"
      />

      <path d="M3 10h18" />

      <path d="M7 15h3" />

    </svg>
  );
}
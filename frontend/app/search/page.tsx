"use client";

import {
  FormEvent,
  useState,
} from "react";

import Link from "next/link";

import {
  ArrowLeft,
  CarFront,
  Clock3,
  Search,
  ShieldCheck,
  Video,
} from "lucide-react";

import {
  getMediaUrl,
  searchPlate,
} from "@/lib/api";

import type {
  SearchResult,
} from "@/types";


export default function SearchPage() {

  const [query, setQuery] =
    useState("");

  const [result, setResult] =
    useState<SearchResult | null>(
      null
    );

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");


  async function handleSearch(
    event: FormEvent
  ) {

    event.preventDefault();


    const plate =
      query.trim();


    if (!plate) {

      setError(
        "Enter a license plate number."
      );

      return;
    }


    try {

      setLoading(true);

      setError("");

      setResult(null);


      const data =
        await searchPlate(
          plate
        );


      setResult(data);

    } catch (err) {

      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Search failed."
      );

    } finally {

      setLoading(false);

    }

  }


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

          <Link
            href="/search"
            className="active"
          >
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
            PLATE SEARCH
          </p>

          <h1>
            Search a license plate
          </h1>

          <p>
            Find every detected occurrence
            across your processed CCTV videos.
          </p>

        </div>


        <form
          className="search-form"
          onSubmit={
            handleSearch
          }
        >

          <Search
            size={20}
          />

          <input
            value={query}
            onChange={(event) =>
              setQuery(
                event.target.value
              )
            }
            placeholder="Enter plate number..."
          />


          <button
            type="submit"
            className="green-button"
            disabled={loading}
          >

            {loading
              ? "Searching..."
              : "Search"}

          </button>

        </form>


        {error && (

          <div className="error-message">

            {error}

          </div>

        )}


        {result && (

          <section className="search-results">

            <div className="results-summary">

              <div>

                <p>
                  SEARCH RESULTS
                </p>

                <h2>
                  {result.plate_number}
                </h2>

              </div>


              <div className="result-count">

                <strong>
                  {
                    result.total_appearances
                  }
                </strong>

                <span>
                  appearance
                  {result.total_appearances !==
                  1
                    ? "s"
                    : ""}
                </span>

              </div>

            </div>


            {result.results.length ===
            0 ? (

              <div className="empty-state large">

                <Search
                  size={28}
                />

                <strong>
                  No matching plate found
                </strong>

                <span>
                  This plate does not
                  appear in the processed
                  videos.
                </span>

              </div>

            ) : (

              <div className="result-list">

                {result.results.map(
                  (detection) => {

                    const snapshot =
                      getMediaUrl(
                        detection
                          .snapshot_url
                      );


                    return (

                      <div
                        className="result-card"
                        key={
                          detection.id
                        }
                      >

                        <div className="result-image">

                          {snapshot ? (

                            <img
                              src={
                                snapshot
                              }
                              alt="Vehicle detection"
                            />

                          ) : (

                            <CarFront
                              size={35}
                            />

                          )}

                        </div>


                        <div className="result-info">

                          <span className="plate-label">
                            PLATE
                          </span>

                          <h3>

                            {detection
                              .plate_number ||
                              detection
                                .raw_ocr_text ||
                              "Not recognized"}

                          </h3>


                          <div className="result-meta">

                            <span>

                              <CarFront
                                size={15}
                              />

                              {
                                detection
                                  .vehicle_type ||
                                "Vehicle"
                              }

                            </span>


                            <span>

                              <Clock3
                                size={15}
                              />

                              {
                                detection
                                  .formatted_timestamp
                              }

                            </span>


                            <span>

                              <Video
                                size={15}
                              />

                              {
                                detection
                                  .video_filename
                              }

                            </span>

                          </div>

                        </div>


                        <div className="confidence">

                          {detection
                            .ocr_confidence !=
                            null && (

                            <>

                              <span>
                                OCR
                              </span>

                              <strong>
                                {Math.round(
                                  detection
                                    .ocr_confidence
                                )}
                                %
                              </strong>

                            </>

                          )}

                        </div>

                      </div>

                    );
                  }
                )}

              </div>

            )}

          </section>

        )}

      </main>

    </div>
  );
}
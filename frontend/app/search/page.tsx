"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import SearchBar from "@/components/SearchBar";
import SearchResults from "@/components/SearchResults";
import { searchPlate } from "@/lib/api";
import { SearchResultOut } from "@/types";

function SearchPageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const initial = params.get("plate") || "";

  const [result, setResult] = useState<SearchResultOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const runSearch = async (plate: string) => {
    setLoading(true);
    setError(null);
    router.replace(`/search?plate=${encodeURIComponent(plate)}`);
    try {
      const r = await searchPlate(plate);
      setResult(r);
      setSearched(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <div className="font-tech text-xs tracking-[0.3em] text-[var(--color-amber)] uppercase mb-2">
          Step 2 of 2
        </div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)] mb-6">
          Search a vehicle number
        </h1>
        <SearchBar initialValue={initial} onSearch={runSearch} loading={loading} />
      </div>

      {error && (
        <div className="border border-[var(--color-red)]/40 bg-[var(--color-red)]/5 rounded-md p-4 mb-6">
          <p className="text-[var(--color-red)] font-tech text-sm">{error}</p>
        </div>
      )}

      {searched && result && (
        <SearchResults plateNumber={result.plate_number} results={result.results} />
      )}

      {!searched && !loading && (
        <p className="text-sm text-[var(--color-text-muted)] font-tech">
          Enter a registration number above, e.g.{" "}
          <span className="text-[var(--color-amber)]">CG04AB1234</span>
        </p>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchPageInner />
    </Suspense>
  );
}

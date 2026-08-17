"use client";

import { useState } from "react";

interface Props {
  initialValue?: string;
  onSearch: (plate: string) => void;
  loading?: boolean;
}

export default function SearchBar({ initialValue = "", onSearch, loading }: Props) {
  const [value, setValue] = useState(initialValue);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSearch(value.trim());
      }}
      className="flex gap-2"
    >
      <div className="flex-1 relative">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] font-tech text-xs uppercase tracking-widest pointer-events-none">
          Plate
        </span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="CG04AB1234"
          className="w-full bg-[var(--color-panel)] border border-[var(--color-line)] rounded pl-20 pr-4 py-3 font-tech text-lg tracking-widest text-[var(--color-amber)] placeholder:text-[var(--color-text-muted)]/40 focus:outline-none focus:border-[var(--color-amber)] transition-colors"
        />
      </div>
      <button
        type="submit"
        disabled={loading || !value.trim()}
        className="px-6 py-3 rounded bg-[var(--color-amber)] text-[#0a0d0b] font-tech text-sm tracking-widest uppercase disabled:opacity-40 hover:brightness-110 transition"
      >
        {loading ? "Searching…" : "Search"}
      </button>
    </form>
  );
}

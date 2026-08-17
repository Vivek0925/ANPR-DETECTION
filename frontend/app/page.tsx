import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center text-center py-20">
      <div className="font-tech text-xs tracking-[0.4em] text-[var(--color-amber)] uppercase mb-4">
        AI Vehicle Surveillance
      </div>
      <h1 className="text-4xl sm:text-5xl font-semibold text-[var(--color-text)] max-w-2xl leading-tight mb-6">
        Find the exact moment a plate appeared on camera.
      </h1>
      <p className="text-[var(--color-text-muted)] max-w-xl mb-10">
        Upload a recorded CCTV video. The system detects vehicles, reads
        number plates, and indexes every timestamp — so a search jumps
        straight to the footage.
      </p>
      <div className="flex gap-4">
        <Link
          href="/upload"
          className="px-6 py-3 rounded bg-[var(--color-amber)] text-[#0a0d0b] font-tech text-sm tracking-widest uppercase hover:brightness-110 transition"
        >
          Upload Footage
        </Link>
        <Link
          href="/search"
          className="px-6 py-3 rounded border border-[var(--color-line)] text-[var(--color-text)] font-tech text-sm tracking-widest uppercase hover:border-[var(--color-amber)]/60 transition"
        >
          Search a Plate
        </Link>
      </div>
    </div>
  );
}

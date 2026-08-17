"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/upload", label: "Upload" },
  { href: "/search", label: "Search" },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-[var(--color-line)] bg-[var(--color-panel)]/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3 group">
          <span className="relative inline-block w-2.5 h-2.5">
            <span className="absolute inset-0 rounded-full bg-[var(--color-green)] animate-pulse" />
          </span>
          <span className="font-tech text-sm tracking-[0.2em] text-[var(--color-text)] uppercase">
            CCTV<span className="text-[var(--color-amber)]">/</span>Retrieval
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((l) => {
            const active = pathname?.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`px-3 py-1.5 text-sm font-tech tracking-wide rounded transition-colors ${
                  active
                    ? "text-[var(--color-amber)] bg-[var(--color-amber)]/10"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

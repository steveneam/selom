import { LibraryView } from "@/components/library/library-view";

export const metadata = { title: "Library — Selom" };

export default function LibraryPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-12 lg:px-10 lg:py-14">
      <div className="max-w-2xl">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">Workspace Library</p>
        <h1 className="text-display mt-3 text-3xl text-foreground sm:text-4xl">
          Everything you&apos;ve saved, <span className="accent-keyword">across every project</span>
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Your account-level home for the assets that outlive any one dataset — papers you&apos;ve
          matched to skills, gene panels you&apos;ve curated, and the skills you&apos;ve added. Project-
          and data-agnostic: save once, reuse everywhere.
        </p>
      </div>

      <div className="mt-10">
        <LibraryView />
      </div>
    </div>
  );
}

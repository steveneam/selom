import { CatalogBrowser } from "@/components/store/catalog-browser";
import { CoverageMeter } from "@/components/store/coverage-meter";
import { CATALOG_TOTAL_ESTIMATE } from "@/lib/catalog/seed";

export const metadata = { title: "Skill Store — Selom" };

export default function StorePage() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-12 lg:px-10 lg:py-14">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">Skill Store</p>
          <h1 className="text-display mt-3 max-w-2xl text-3xl text-foreground sm:text-4xl">
            Install a skill, <span className="accent-keyword">light up</span> your data
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            ~{CATALOG_TOTAL_ESTIMATE} skills from bioSkills + ClawBio. Drop one into a project and apply it to
            your data — Verified skills run now; the rest run as we port them.
          </p>
        </div>

        {/* honest coverage meter (design §6.4) — runnable count is live from GET /skills */}
        <CoverageMeter />
      </div>

      <div className="mt-10">
        <CatalogBrowser />
      </div>
    </div>
  );
}

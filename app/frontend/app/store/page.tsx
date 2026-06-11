import { CatalogBrowser } from "@/components/store/catalog-browser";
import { CoverageMeter } from "@/components/store/coverage-meter";
import { CATALOG_TOTAL_ESTIMATE } from "@/lib/catalog/seed";

export const metadata = { title: "Skill Store — Selom" };

export default function StorePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-primary/80">Skill Store</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            Browse &amp; install bioinformatics skills
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            ~{CATALOG_TOTAL_ESTIMATE} skills from bioSkills + ClawBio. Install one into a project and
            apply it to your data — Verified skills run now; the rest run as we port them.
          </p>
        </div>

        {/* honest coverage meter (design §6.4) — runnable count is live from GET /skills */}
        <CoverageMeter />
      </div>

      <div className="mt-7">
        <CatalogBrowser />
      </div>
    </div>
  );
}

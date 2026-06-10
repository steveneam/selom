import { CatalogBrowser } from "@/components/store/catalog-browser";
import { CATALOG_TOTAL_ESTIMATE, VERIFIED_SEEDED } from "@/lib/catalog/seed";

export const metadata = { title: "Skill Store — Selom" };

export default function StorePage() {
  const pct = Math.round((VERIFIED_SEEDED / CATALOG_TOTAL_ESTIMATE) * 100);

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

        {/* honest coverage meter (design §6.4) */}
        <div className="w-56 shrink-0 rounded-lg border border-border bg-card/50 p-3">
          <div className="flex items-baseline justify-between">
            <span className="tabular text-sm font-semibold text-foreground">
              {VERIFIED_SEEDED}
              <span className="text-muted-foreground"> / ~{CATALOG_TOTAL_ESTIMATE}</span>
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wider text-primary/80">
              runnable
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.max(2, pct)}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
            Coverage grows via the Skill Foundry — browsable ≠ runnable, shown honestly.
          </p>
        </div>
      </div>

      <div className="mt-7">
        <CatalogBrowser />
      </div>
    </div>
  );
}

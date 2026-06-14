import { GeneSetBrowser } from "@/components/gene-sets/gene-set-browser";

export const metadata = { title: "Gene Sets — Selom" };

export default function GeneSetsPage() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-12 lg:px-10 lg:py-14">
      <div className="max-w-2xl">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">Gene Sets</p>
        <h1 className="text-display mt-3 text-3xl text-foreground sm:text-4xl">
          Find a gene list, <span className="accent-keyword">apply it</span> to your data
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          A license-clean, provenance-stamped corpus — Gene Ontology, WikiPathways, and Selom&apos;s own
          curated panels. Search a topic, then highlight the panel on your volcano or score your DE result
          against the whole library. No MSigDB licence friction.
        </p>
      </div>

      <div className="mt-10">
        <GeneSetBrowser />
      </div>
    </div>
  );
}

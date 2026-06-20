import { SkillMatch } from "@/components/skill-match/skill-match";

export const metadata = { title: "Skill Match — Selom" };

/**
 * Skill Match — the Skill Keyword Index surface. Drop a paper PDF, see which Selom skill each figure
 * needs (deterministic, no LLM) plus the paper's skill inventory and the open-core Pro-AI upsell.
 */
export default function SkillMatchPage() {
  return (
    <div className="mx-auto max-w-[100rem] px-6 py-12 lg:px-10 lg:py-14">
      <div className="max-w-2xl">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">
          Skill Keyword Index
        </p>
        <h1 className="text-display mt-3 text-3xl text-foreground sm:text-4xl">
          Which Selom skills does this <span className="accent-keyword">paper</span> need?
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Drop a paper PDF. A deterministic keyword index — no LLM on the path — reads its methods and
          figure captions, then matches each figure to a Selom skill or flags its modality as out of
          scope. The optional <span className="text-foreground">Pro AI</span> tier verifies the
          figures that routed with low confidence.
        </p>
      </div>

      <div className="mt-10">
        <SkillMatch />
      </div>
    </div>
  );
}

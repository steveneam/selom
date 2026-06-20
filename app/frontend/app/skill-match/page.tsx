import { SkillMatch } from "@/components/skill-match/skill-match";

export const metadata = { title: "Skill Match — Selom" };

/**
 * Skill Match — the Skill Keyword Index surface. Drop a paper PDF, see which Selom skill each figure
 * needs (deterministic, no LLM) plus the paper's skill inventory and the open-core Pro-AI upsell.
 */
export default function SkillMatchPage() {
  return (
    <div className="mx-auto max-w-[100rem] px-6 py-12 lg:px-10 lg:py-14">
      <SkillMatch />
    </div>
  );
}

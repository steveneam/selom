"use client";

import Link from "next/link";
import { Boxes, Play } from "lucide-react";
import { ProposalPlan } from "@/components/intake/proposal-plan";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";
import type { SkillInstall } from "@/lib/projects/types";

/**
 * The Workbench: the project's installed skills + (when present) the LLM's proposed
 * pipeline. Either path produces a figure via the same run flow (design §2.3).
 */
export function WorkbenchPanel({
  installs,
  proposal,
  running,
  onRun,
}: {
  installs: SkillInstall[];
  proposal: IntakeProposal | null;
  running: string | null;
  onRun: (step: ProposedStep) => void;
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
      {/* proposal (or guidance to get one) */}
      <Card className="p-5">
        {proposal ? (
          <ProposalPlan proposal={proposal} running={running} onRun={onRun} />
        ) : (
          <div className="grid place-items-center py-10 text-center">
            <div className="max-w-sm space-y-1.5">
              <p className="text-sm font-medium text-foreground">No proposed pipeline yet</p>
              <p className="text-xs text-muted-foreground">
                Drop a dataset in the <span className="text-foreground">Data</span> tab and answer a few
                questions, or run one of your installed skills directly.
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* installed skills */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Installed skills
          </p>
          <Link href="/store" className="text-[11px] font-medium text-primary hover:underline">
            + Store
          </Link>
        </div>
        {installs.length === 0 ? (
          <Card className="grid place-items-center gap-2 p-6 text-center">
            <Boxes className="size-5 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">
              No skills installed. Add some from the Skill Store.
            </p>
            <Button asChild variant="outline" size="sm" className="mt-1">
              <Link href="/store">Browse Store</Link>
            </Button>
          </Card>
        ) : (
          installs.map((inst) => {
            const skill = getSkill(inst.skillId);
            const busy = running === inst.skillId;
            const verified = skill?.tier === "verified";
            return (
              <Card key={inst.id} className="flex items-center gap-2.5 p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <p className="truncate text-sm font-medium text-foreground">
                      {skill?.name ?? inst.skillId}
                    </p>
                    {verified ? (
                      <Badge variant="verified">Verified</Badge>
                    ) : (
                      <Badge variant="community">Queued</Badge>
                    )}
                  </div>
                  {skill && <p className="truncate text-[11px] text-muted-foreground">{skill.category}</p>}
                </div>
                <Button
                  size="sm"
                  variant={verified ? "default" : "secondary"}
                  className="h-7 px-2.5 text-xs"
                  disabled={busy || !verified}
                  title={verified ? "Run skill" : "Community skill — runs in a future sandbox"}
                  onClick={() =>
                    onRun({ skillId: inst.skillId, rationale: "", params: {}, confidence: 0 })
                  }
                >
                  <Play /> {busy ? "Running…" : "Run"}
                </Button>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}

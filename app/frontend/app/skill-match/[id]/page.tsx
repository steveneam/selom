import { SavedSkillMatch } from "@/components/skill-match/saved-skill-match";

export const metadata = { title: "Skill Match — Selom" };

export default async function SavedSkillMatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SavedSkillMatch id={id} />;
}

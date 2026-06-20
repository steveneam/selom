import { redirect } from "next/navigation";

// The per-paper Skill-Match surface folded into the unified Paper shell (umbrella-shell.md §4).
// Kept as a redirect so any saved pill/bookmark still resolves; the Skill Match stage is the default.
export default async function SavedSkillMatchRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/paper/${id}`);
}

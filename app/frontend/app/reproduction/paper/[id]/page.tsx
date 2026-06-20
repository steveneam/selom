import { redirect } from "next/navigation";

// The per-paper Reproduction workspace folded into the unified Paper shell (umbrella-shell.md §4).
// Kept as a redirect so existing links/bookmarks resolve; this route always meant the Reproduce stage.
export default async function ReproductionPaperRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/paper/${id}?stage=reproduce`);
}

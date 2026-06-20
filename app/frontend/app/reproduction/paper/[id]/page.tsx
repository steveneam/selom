import { PaperWorkspace } from "@/components/reproduction/paper-workspace";

export const metadata = { title: "Reproduction — Selom" };

export default async function ReproductionPaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PaperWorkspace id={id} />;
}

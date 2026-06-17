import { PaperDetail } from "@/components/reproduction/paper-detail";

export const metadata = { title: "Reproduction — Selom" };

export default async function ReproductionDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <PaperDetail slug={slug} />;
}

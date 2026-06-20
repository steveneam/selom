import * as React from "react";

import { PaperShell } from "@/components/paper/paper-shell";

export const metadata = { title: "Paper — Selom" };

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  // PaperShell reads `?stage` via useSearchParams — wrap in Suspense per the Next 16 App Router.
  return (
    <React.Suspense fallback={null}>
      <PaperShell id={id} />
    </React.Suspense>
  );
}

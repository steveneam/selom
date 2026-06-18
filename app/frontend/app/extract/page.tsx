import { ChartExtractor, type DigitizeOrigin } from "@/components/extract/chart-extractor";
import type { ChartForm } from "@/lib/extract/calibrate";

export const metadata = { title: "Recover data — Selom" };

const TRACEABLE_FORMS = new Set<ChartForm>(["bar", "line", "scatter"]);

/**
 * The data-extractor surface. With no query it's the standalone "drop a figure" picker; opened
 * from a Reproduction panel ("Digitize this panel") it carries `?img=<lift>&panel=<slug:key>&form=`
 * and pre-loads the lifted panel — digitizing is vision-grade and never part of the score.
 */
export default async function ExtractPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const img = typeof sp.img === "string" ? sp.img : "";
  const panel = typeof sp.panel === "string" ? sp.panel : "";
  const formRaw = typeof sp.form === "string" ? sp.form : "";

  let origin: DigitizeOrigin | undefined;
  if (img && panel.includes(":")) {
    const [slug, panelKey] = panel.split(":");
    const form = (TRACEABLE_FORMS.has(formRaw as ChartForm) ? formRaw : "scatter") as ChartForm;
    origin = { imageUrl: `/api${img}`, slug, panelKey, form };
  }

  return <ChartExtractor origin={origin} />;
}

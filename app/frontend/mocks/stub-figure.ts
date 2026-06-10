// Faithful TS port of app/backend/skills/umap_scrna/run.py (the offline stub):
// three deterministic clusters, ~10 points each, no RNG. Keeping the math identical
// means the MSW mock returns the SAME wire shape the live backend stub will, so the
// upload->render path is proven 1:1 before :8000 is up. Swap to live by flipping
// NEXT_PUBLIC_API_MOCKING off; nothing else changes.

export type PlotlySpec = {
  data: Array<Record<string, unknown>>;
  layout: Record<string, unknown>;
};

export function stubUmapFigure(): PlotlySpec {
  const centers: Array<[number, number]> = [
    [0.0, 0.0],
    [5.0, 1.0],
    [2.5, 4.5],
  ];
  const names = ["Cluster 0", "Cluster 1", "Cluster 2"];
  const pointsPerCluster = 10;
  const round4 = (n: number) => Math.round(n * 1e4) / 1e4;

  const data = centers.map(([centerX, centerY], clusterIndex) => {
    const x: number[] = [];
    const y: number[] = [];
    for (let j = 0; j < pointsPerCluster; j++) {
      const angle = clusterIndex * 2.39996 + j * 0.7;
      const radius = 0.6 + 0.4 * ((j % 5) / 4.0);
      x.push(round4(centerX + radius * Math.cos(angle)));
      y.push(round4(centerY + radius * Math.sin(angle)));
    }
    return {
      type: "scatter",
      mode: "markers",
      name: names[clusterIndex],
      x,
      y,
    };
  });

  // Title is tagged so it's visually obvious in-browser that the figure came from
  // the mock, not a live :8000. The live backend stub uses "scRNA UMAP (stub)".
  return { data, layout: { title: { text: "scRNA UMAP (stub · MSW mock)" } } };
}

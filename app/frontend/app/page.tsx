"use client";

import { useState } from "react";
import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function Home() {
  const [fig, setFig] = useState<any>(null);

  async function run(file: File) {
    const fd = new FormData();
    fd.append("matrix", file);
    const r = await fetch("/api/skills/umap_scrna/run", {
      method: "POST",
      body: fd,
    });
    setFig((await r.json()).figure); // {data, layout} = the editable spec
  }

  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold">
        Selom — no-code multi-omics figures
      </h1>
      <input
        type="file"
        accept=".h5ad,.csv"
        className="mt-4 block"
        onChange={(e) => e.target.files && run(e.target.files[0])}
      />
      {fig && <Plot data={fig.data} layout={fig.layout} />}
    </main>
  );
}

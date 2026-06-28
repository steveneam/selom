"use client";

import { Section, SelectField, SliderField, SwitchField, TextField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { FONT_FAMILIES } from "@/lib/figure/figure-spec";
import { getAt, remove, set } from "@/lib/figure/patch";

export function PagePanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const title = getAt<string>(spec, "/layout/title/text", "")!;
  const titleSize = getAt<number>(spec, "/layout/title/font/size", 17)!;
  const fontFamily = getAt<string>(spec, "/layout/font/family", FONT_FAMILIES[0].value)!;
  const fontSize = getAt<number>(spec, "/layout/font/size", 12)!;

  const width = getAt<number>(spec, "/layout/width", undefined);
  const height = getAt<number>(spec, "/layout/height", undefined);
  const fixedSize = typeof width === "number";

  return (
    <div className="space-y-6">
      <Section title="Title">
        <TextField
          label="Figure title"
          value={title}
          placeholder="Untitled figure"
          onCommit={(v) => store.commit([set("/layout/title/text", v)])}
        />
        <SliderField
          label="Title size"
          value={titleSize}
          min={10}
          max={36}
          unit="px"
          store={store}
          build={(v) => [set("/layout/title/font/size", v)]}
        />
      </Section>

      <Section title="Typography">
        <SelectField
          label="Font family"
          value={fontFamily}
          options={FONT_FAMILIES}
          onChange={(v) => store.commit([set("/layout/font/family", v)])}
        />
        <SliderField
          label="Base font size"
          value={fontSize}
          min={7}
          max={22}
          unit="px"
          store={store}
          build={(v) => [set("/layout/font/size", v)]}
        />
      </Section>

      <Section title="Canvas">
        <SwitchField
          label="Fixed export size"
          checked={fixedSize}
          onChange={(on) =>
            store.commit(
              on
                ? [set("/layout/width", 960), set("/layout/height", 640)]
                : [remove("/layout/width"), remove("/layout/height")],
            )
          }
        />
        {fixedSize && (
          <>
            <SliderField
              label="Width"
              value={width!}
              min={320}
              max={2000}
              step={10}
              unit="px"
              store={store}
              build={(v) => [set("/layout/width", v)]}
            />
            <SliderField
              label="Height"
              value={height ?? 640}
              min={240}
              max={1600}
              step={10}
              unit="px"
              store={store}
              build={(v) => [set("/layout/height", v)]}
            />
          </>
        )}
        {!fixedSize && (
          <p className="text-[11px] leading-relaxed text-muted-foreground/80">
            The figure fits the window. Turn on a fixed size to pin exact export dimensions.
          </p>
        )}
      </Section>
    </div>
  );
}

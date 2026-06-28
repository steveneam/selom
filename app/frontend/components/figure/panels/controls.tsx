"use client";

import * as React from "react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { Operation } from "@/lib/figure/patch";
import { cn } from "@/lib/ui/cn";

/** A panel section: small caps heading + grouped controls. */
export function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {title}
      </h3>
      <div className="space-y-3.5">{children}</div>
    </section>
  );
}

function FieldShell({
  label,
  value,
  children,
}: {
  label: string;
  value?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label>{label}</Label>
        {value != null && <span className="tabular text-xs text-foreground/90">{value}</span>}
      </div>
      {children}
    </div>
  );
}

/**
 * Live slider: `onValueChange` previews (store.set, no history), `onValueCommit`
 * records ONE history entry (store.flush). The displayed value is read from the
 * spec, so it tracks the drag in real time.
 */
export function SliderField({
  label,
  value,
  min,
  max,
  step = 1,
  unit = "",
  store,
  build,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  store: FigureStore;
  build: (v: number) => Operation[];
}) {
  return (
    <FieldShell label={label} value={`${value}${unit}`}>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([v]) => store.set(build(v))}
        onValueCommit={() => store.flush()}
        aria-label={label}
      />
    </FieldShell>
  );
}

export function SelectField({
  label,
  value,
  options,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  options: { label: string; value: string }[];
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <FieldShell label={label}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FieldShell>
  );
}

export function SwitchField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  const id = React.useId();
  return (
    <div className="flex items-center justify-between gap-2 py-0.5">
      <Label htmlFor={id} className="cursor-pointer">
        {label}
      </Label>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

/** Text field that commits on blur / Enter (so typing doesn't spam history). */
export function TextField({
  label,
  value,
  onCommit,
  placeholder,
  mono,
}: {
  label: string;
  value: string;
  onCommit: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  const [draft, setDraft] = React.useState(value);
  React.useEffect(() => setDraft(value), [value]);
  const commit = () => {
    if (draft !== value) onCommit(draft);
  };
  return (
    <FieldShell label={label}>
      <Input
        value={draft}
        placeholder={placeholder}
        className={cn(mono && "tabular")}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
      />
    </FieldShell>
  );
}

export function ColorField({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: string;
  onCommit: (v: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 py-0.5">
      <Label>{label}</Label>
      <div className="flex items-center gap-2">
        <span className="tabular text-[11px] uppercase text-muted-foreground">{value}</span>
        <input
          type="color"
          value={value}
          onChange={(e) => onCommit(e.target.value)}
          aria-label={label}
          className="size-7 cursor-pointer rounded-md border border-input bg-transparent p-0.5"
        />
      </div>
    </div>
  );
}

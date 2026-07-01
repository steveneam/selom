"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Shared empty-state card for the workspace views (no figure / nothing to compare / no stats …). */
export function EmptyState({
  title,
  body,
  action,
  onAction,
}: {
  title: string;
  body: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <Card className="grid h-full min-h-[320px] place-items-center p-10 text-center">
      <div className="max-w-sm space-y-2">
        <Sparkles className="mx-auto size-6 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{body}</p>
        <Button variant="outline" size="sm" onClick={onAction}>
          {action}
        </Button>
      </div>
    </Card>
  );
}

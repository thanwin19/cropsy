import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function SampleTag({ kind = "sample" }: { kind?: string }) {
  return <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">{kind}</span>;
}

export function StatusChip({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "good" | "warn" | "bad" }) {
  return <span className={cn("inline-flex min-h-6 items-center rounded-full border px-2 font-mono text-[11px]", tone === "good" && "border-success/40 bg-success/10 text-success", tone === "warn" && "border-warning/40 bg-warning/10 text-warning", tone === "bad" && "border-destructive/40 bg-destructive/10 text-destructive", tone === "default" && "border-border bg-muted text-muted-foreground")}>{children}</span>;
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("rounded-xl border border-border bg-card", className)}>{children}</section>;
}

export function SectionStrip({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return <div className="flex min-h-14 items-center justify-between gap-3 border-b border-border px-4 md:px-6"><div className="flex min-w-0 items-center gap-1 overflow-x-auto">{children}</div>{action}</div>;
}

export function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="min-w-0"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-mono text-sm text-foreground">{value}</p>{detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}</div>;
}

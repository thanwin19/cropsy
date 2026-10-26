import type { ReactNode } from 'react';
import { CircleHelp } from 'lucide-react';

/**
 * Small page-level helpers shared by the Flagged cases, Execution runs and Settings pages.
 * The app frame (icon rail, mobile tab bar, alerts and settings sheets) now lives in features/cropsy/app-shell.tsx,
 * so CropsyShell is only a pass-through that keeps those pages' markup unchanged.
 */
export function CropsyShell({ children }: { children: ReactNode }) {
  return <div className="min-h-full">{children}</div>;
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <p className="mono text-[10px] font-medium uppercase tracking-[.16em] text-muted-foreground">{children}</p>;
}

export function StatusPill({ status, children }: { status: string; children?: ReactNode }) {
  const tone =
    status === 'needs_retry'
      ? 'border-red-500/35 bg-red-500/10 text-red-300'
      : status === 'flagged'
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
        : status === 'fallback'
          ? 'border-slate-400/30 bg-slate-400/10 text-slate-300'
          : status === 'running'
            ? 'border-primary/25 bg-primary/10 text-primary'
            : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300';
  const dot =
    status === 'needs_retry'
      ? 'bg-red-500'
      : status === 'flagged'
        ? 'bg-amber-400'
        : status === 'running'
          ? 'animate-pulse bg-primary'
          : status === 'fallback'
            ? 'bg-slate-400'
            : 'bg-emerald-400';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[.08em] ${tone}`}>
      <span className={`size-1.5 rounded-full ${dot}`} />
      {children ?? status}
    </span>
  );
}

export function HelpLink() {
  return (
    <button className="focus-ring inline-flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground hover:text-foreground" onClick={() => window.alert('Cropsy traces every source, model choice, fallback, and verification step.')} data-testid="button-help-inline">
      <CircleHelp size={14} />How traces work
    </button>
  );
}

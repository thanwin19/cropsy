import React from "react";
import { ArrowLeft } from "lucide-react";

/**
 * Shared building blocks for the detail pages. One look everywhere:
 * deep-teal surfaces with a soft top glow, hairline borders, serif headings, mono eyebrows, and tones that always mean the same thing
 * (green = fine / real data, amber = watch / dummy or modelled, red = act, blue = our own definition).
 */

export const PageShell: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = "" }) => (
  <div className="w-full min-h-[calc(100vh-3.5rem)] bg-[radial-gradient(1100px_520px_at_8%_-8%,color-mix(in_oklab,var(--primary)_7%,var(--background))_0%,var(--background)_58%)] text-foreground">
    <div className={`mx-auto w-full max-w-[1480px] p-4 lg:p-7 flex flex-col gap-5 ${className}`}>{children}</div>
  </div>
);

export const PageHeader: React.FC<{ onBack: () => void; crumb: string; right?: React.ReactNode }> = ({ onBack, crumb, right }) => (
  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.07]">
    <div className="flex items-center gap-3 min-w-0">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary/80 cursor-pointer group shrink-0">
        <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
        <span>Advisory Chat</span>
      </button>
      <span className="text-white/15">/</span>
      <span className="text-xs font-mono text-muted-foreground truncate">{crumb}</span>
    </div>
    {right}
  </div>
);

export const Card: React.FC<{
  title: string;
  eyebrow?: string;
  icon?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}> = ({ title, eyebrow, icon, right, children, className = "" }) => (
  <section
    className={`rounded-xl border border-border bg-card p-4 sm:p-5 flex flex-col gap-3
                shadow-[0_10px_30px_-14px_rgba(0,0,0,0.7)] ${className}`}
  >
    <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
      <div className="flex items-center gap-2.5 min-w-0">
        {icon && <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/[0.05] text-primary">{icon}</span>}
        <div className="min-w-0">
          {eyebrow && <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground/70">{eyebrow}</div>}
          <h3 className="font-serif text-[15px] font-semibold leading-tight text-foreground">{title}</h3>
        </div>
      </div>
      {right}
    </div>
    {children}
  </section>
);

export const Kv: React.FC<{ k: string; v: React.ReactNode }> = ({ k, v }) => (
  <div className="flex items-baseline justify-between gap-3 text-xs border-b border-white/[0.05] py-1.5 last:border-0">
    <span className="text-muted-foreground">{k}</span>
    <span className="font-mono text-foreground text-right">{v}</span>
  </div>
);

export type Tone = "ok" | "warn" | "bad" | "dummy" | "real" | "info" | "mute";
const TONES: Record<Tone, string> = {
  ok: "border-success/30 bg-success/10 text-success",
  real: "border-success/30 bg-success/10 text-success",
  warn: "border-warning/35 bg-warning/10 text-warning",
  dummy: "border-warning/35 bg-warning/10 text-warning",
  bad: "border-destructive/35 bg-destructive/10 text-destructive",
  info: "border-[#7aa7f7]/35 bg-[#7aa7f7]/10 text-[#9bbcf9]",
  mute: "border-white/10 bg-white/[0.04] text-muted-foreground",
};
export const Badge: React.FC<{ tone?: Tone; children: React.ReactNode }> = ({ tone = "ok", children }) => (
  <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] ${TONES[tone]}`}>{children}</span>
);

export const DummyBadge: React.FC = () => <Badge tone="dummy">SAMPLE DATA · dummy</Badge>;

export const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center text-sm text-muted-foreground">{children}</div>
);

/** Big number with a caption, for headline figures. */
export const Stat: React.FC<{ label: string; value: React.ReactNode; hint?: string; tone?: Tone }> = ({ label, value, hint, tone }) => (
  <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5 min-w-0">
    <div className="font-mono text-[9.5px] uppercase tracking-wider text-muted-foreground/70">{label}</div>
    <div className={`font-serif text-xl leading-tight ${tone === "bad" ? "text-destructive" : tone === "warn" ? "text-warning" : "text-foreground"}`}>{value}</div>
    {hint && <div className="text-[10.5px] text-muted-foreground/70 truncate">{hint}</div>}
  </div>
);

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-white/10 bg-black/20 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${value === o.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Donut chart. `slices` shares are fractions (0..1). */
export const Donut: React.FC<{ slices: { name: string; share: number; color: string }[]; center?: React.ReactNode; size?: number }> = ({ slices, center, size = 150 }) => {
  const r = 52, c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox="0 0 130 130" className="h-full w-full -rotate-90">
        <circle cx="65" cy="65" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="16" />
        {slices.filter((s) => s.share > 0.002).map((s) => {
          const len = s.share * c;
          const el = <circle key={s.name} cx="65" cy="65" r={r} fill="none" stroke={s.color} strokeWidth="16" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset}><title>{`${s.name}: ${Math.round(s.share * 100)}%`}</title></circle>;
          offset += len;
          return el;
        })}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{center}</div>
    </div>
  );
};

export const SourceNote: React.FC<{ children: React.ReactNode }> = ({ children }) => <p className="text-[10.5px] leading-relaxed text-muted-foreground/70">{children}</p>;

export const money = (n?: number | null) => (n == null ? "n/a" : `$${n.toFixed(5)}`);
export const ms = (n?: number | null) => (n == null ? "n/a" : n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${Math.round(n)} ms`);

import React, { useState } from "react";
import { Bug, ChevronDown } from "lucide-react";
import type { Cited, FieldReport, WatchItem } from "@/lib/cropsy-api";
import { Badge, Card, SourceNote } from "../stitch/ui";

const SEV = { mild: "ok", moderate: "warn", severe: "bad" } as const;

const Col: React.FC<{ title: string; tone: string; items: Cited[]; empty: string }> = ({ title, tone, items, empty }) => (
  <div className="rounded-xl border border-white/[0.06] bg-black/20 p-2.5">
    <div className={`mb-1.5 font-mono text-[9.5px] uppercase tracking-wider ${tone}`}>{title}</div>
    {items.length === 0 ? (
      <p className="text-[11px] text-muted-foreground/60">{empty}</p>
    ) : (
      <ul className="space-y-2">
        {items.map((c, i) => (
          <li key={i} className="text-[11.5px] leading-relaxed text-foreground/90">
            {c.text}
            <span className="ml-1 whitespace-nowrap font-mono text-[10px] text-muted-foreground/70">{c.source.replace("Crop Production Guide: ", "").replace(" 2020", "")}</span>
          </li>
        ))}
      </ul>
    )}
  </div>
);

const Item: React.FC<{ it: WatchItem; open: boolean; onToggle: () => void }> = ({ it, open, onToggle }) => (
  <div className={`rounded-xl border ${it.recorded_on_parcel ? "border-warning/40 bg-warning/[0.05]" : "border-white/[0.07] bg-white/[0.02]"}`}>
    <button onClick={onToggle} className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-serif text-sm font-semibold text-white">{it.name}</span>
          <Badge tone={SEV[it.severity as keyof typeof SEV] || "mute"}>{it.kind} · {it.severity}</Badge>
          {it.recorded_on_parcel && <Badge tone="warn">recorded on this parcel</Badge>}
        </div>
        <div className="truncate text-[11px] text-muted-foreground">{it.symptoms.join(" · ")}</div>
      </div>
      <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
    {open && (
      <div className="space-y-2 px-3 pb-3">
        {it.closest && <p className="rounded-lg bg-[#7aa7f7]/10 px-2.5 py-1.5 text-[11px] text-[#9bbcf9]">{it.closest}</p>}
        <div className="grid gap-2 md:grid-cols-3">
          <Col title="Cultural" tone="text-[#9bbcf9]" items={it.cultural} empty="None listed" />
          <Col title="Organic / biological" tone="text-primary" items={it.organic} empty="None listed in the guide" />
          <Col title="Chemical" tone="text-destructive" items={it.chemical} empty="None listed" />
        </div>
      </div>
    )}
  </div>
);

export const WatchCard: React.FC<{ report: FieldReport; onAsk?: (q: string) => void }> = ({ report, onAsk }) => {
  const w = report.watch;
  const [open, setOpen] = useState<string | null>(w.watchlist[0]?.code ?? null);
  const sig = w.weather_signal;
  return (
    <Card title="Pest, disease & weed management" eyebrow="Watch-list · no invented probabilities" icon={<Bug size={16} />}
      right={sig && <Badge tone={sig.favours_fungal ? "warn" : "ok"}>{sig.favours_fungal ? "humid spell: fungal risk up" : "weather not favouring fungus"}</Badge>}>
      {w.recorded_without_advice && (
        <p className="rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning">
          The recorded problem on this parcel ({w.recorded_without_advice}) has no verified control in the TNAU guides, so none is shown. Ask Cropsy or take it to your KVK.
        </p>
      )}
      <div className="space-y-2">
        {w.watchlist.map((it) => <Item key={it.code} it={it} open={open === it.code} onToggle={() => setOpen(open === it.code ? null : it.code)} />)}
        {w.watchlist.length === 0 && <p className="text-xs text-muted-foreground">No curated controls for this crop's listed problems.</p>}
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-wider text-muted-foreground">Weeds</div>
        <div className="grid gap-2 md:grid-cols-2">
          <Col title="Organic / mechanical" tone="text-primary" items={w.weeds.organic} empty="None found" />
          <Col title="Herbicide" tone="text-destructive" items={w.weeds.chemical} empty="None found" />
        </div>
        {w.weeds_note && <p className="mt-1.5 text-[10.5px] text-warning">{w.weeds_note}</p>}
      </div>

      {onAsk && (
        <button onClick={() => onAsk(`What pests or diseases should I watch for at ${report.parcel_id} now?`)}
          className="self-start rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-primary hover:border-primary/50">
          Ask Cropsy for a grounded check
        </button>
      )}
      <SourceNote>{w.note} {sig?.basis}</SourceNote>
    </Card>
  );
};

export default WatchCard;

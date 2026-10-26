import React from "react";
import { Sprout } from "lucide-react";
import type { FieldReport } from "@/lib/cropsy-api";
import { Badge, Card, SourceNote, Stat } from "../stitch/ui";

const fmt = (n: number | undefined | null) => (n == null ? "n/a" : n.toLocaleString());

export const GrowthYieldCard: React.FC<{ report: FieldReport }> = ({ report }) => {
  const y = report.yield_outlook;
  const h = report.harvest;
  const pl = report.plants;
  const max = y ? Math.max(...y.last_seasons.map((s) => s.yield), y.expected_high, 1) : 1;
  return (
    <Card title="Growth & yield" eyebrow="Stage · harvest · outlook" icon={<Sprout size={16} />} right={<Badge tone="dummy">sample history</Badge>}>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Growth stage" value={report.crop.stage.split(" - ")[0]} hint={`${report.crop.days_after_planting} days after planting`} />
        <Stat label="Expected harvest" value={h.available ? new Date(h.window_start!).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "Perennial"}
          hint={h.available ? `to ${new Date(h.window_end!).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} · in ${h.days_to_start} days` : "no single harvest date"} />
      </div>

      {y && (
        <div>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-xs text-muted-foreground">Yield outlook ({y.unit})</span>
            <span className="font-serif text-lg text-white">{y.expected_low}–{y.expected_high} <span className="text-xs text-muted-foreground">mid {y.expected_mid}</span></span>
          </div>
          <div className="flex h-[72px] items-end gap-2">
            {y.last_seasons.map((s) => (
              <div key={s.year} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${s.year}: ${s.yield} ${y.unit}${s.issue !== "none" ? ` · ${s.issue}` : ""}`}>
                <div className={`w-full rounded-t ${s.issue !== "none" ? "bg-warning/70" : "bg-primary/70"}`} style={{ height: `${Math.max((s.yield / max) * 52, 3)}px` }} />
                <span className="font-mono text-[9.5px] text-muted-foreground/70">{s.year.slice(2)}</span>
              </div>
            ))}
          </div>
          {y.expected_total != null && <p className="mt-1 text-[11.5px] text-foreground">About {y.expected_total.toLocaleString()} t from the whole parcel at the middle of that range.</p>}
        </div>
      )}

      {pl.available && (
        <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-muted-foreground">Plant count (estimate)</span>
            <span className="font-serif text-lg text-white">{pl.plants_usable != null ? `${fmt(pl.plants_usable)} ${pl.unit}` : `${fmt(pl.row_length_m)} m of rows`}</span>
          </div>
          <p className="text-[11px] text-muted-foreground">{pl.spacing}</p>
          <p className="text-[11px] text-muted-foreground/70">{pl.note}</p>
        </div>
      )}
      <SourceNote>{y?.basis} {h.basis}</SourceNote>
    </Card>
  );
};

export default GrowthYieldCard;

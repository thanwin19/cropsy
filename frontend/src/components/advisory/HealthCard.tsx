import React from "react";
import { Activity } from "lucide-react";
import type { FieldReport } from "@/lib/cropsy-api";
import { Badge, Card, Donut, Segmented, SourceNote } from "../stitch/ui";

export type AreaUnit = "ha" | "acre";
const ACRE = 2.47105;
const STATUS_TEXT: Record<string, { text: string; tone: "ok" | "warn" | "bad" }> = {
  normal: { text: "Steady", tone: "ok" }, watch: { text: "Slight dip", tone: "warn" },
  stress: { text: "Early stress signal", tone: "bad" }, insufficient: { text: "Too few clear views", tone: "warn" },
};

export const HealthCard: React.FC<{ report: FieldReport; unit: AreaUnit; onUnit: (u: AreaUnit) => void }> = ({ report, unit, onUnit }) => {
  const v = report.vigour;
  const h = report.health;
  const st = STATUS_TEXT[h.status] || STATUS_TEXT.insufficient;
  const area = report.area_ha * (unit === "acre" ? ACRE : 1);
  const lc = report.soil_panel.land_cover_under_parcel;
  const top = lc ? Object.entries(lc).sort((a, b) => b[1] - a[1])[0] : null;
  return (
    <Card
      title="Crop health" eyebrow="Analysis scale" icon={<Activity size={16} />}
      right={<div className="flex items-center gap-2"><Badge tone={st.tone}>{st.text}</Badge><Segmented<AreaUnit> value={unit} onChange={onUnit} options={[{ value: "ha", label: "ha" }, { value: "acre", label: "acres" }]} /></div>}
    >
      {v ? (
        <div className="flex flex-wrap items-center gap-5">
          <Donut slices={v.classes} size={150} center={<div><div className="font-serif text-3xl leading-none text-white">{Math.round((v.good_share ?? 0) * 100)}<span className="text-base">%</span></div><div className="mt-0.5 font-mono text-[9.5px] leading-tight text-muted-foreground">in good<br />shape</div></div>} />
          <ul className="flex-1 min-w-[190px] space-y-1.5">
            {v.classes.filter((c) => c.share > 0.001 || c.name !== "No clear view").map((c) => (
              <li key={c.name} className="flex items-center gap-2 text-xs">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: c.color }} />
                <span className="flex-1 leading-tight text-foreground">{c.name}</span>
                <span className="font-mono text-muted-foreground">{(c.share * area).toFixed(2)} {unit === "acre" ? "ac" : "ha"}</span>
                <span className="w-10 text-right font-mono text-white">{Math.round(c.share * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No clear satellite composite covers this parcel yet.</p>
      )}
      {h.latest_ndvi != null && (
        <div className="grid grid-cols-3 gap-2 text-center">
          {[["Latest NDVI", h.latest_ndvi?.toFixed(2)], ["Own baseline", h.baseline_ndvi != null ? h.baseline_ndvi.toFixed(2) : "n/a"], ["Change", h.change != null ? (h.change > 0 ? "+" : "") + h.change.toFixed(2) : "n/a"]].map(([k, val]) => (
            <div key={k} className="rounded-lg bg-white/[0.04] py-1.5"><div className="font-mono text-[9px] uppercase text-muted-foreground/70">{k}</div><div className="font-mono text-sm text-white">{val}</div></div>
          ))}
        </div>
      )}
      {top && (
        <p className="text-[11.5px] text-foreground">
          <span className="text-muted-foreground/70">What the satellite sees under this parcel: </span>
          {Math.round(top[1] * 100)}% {top[0].toLowerCase()}
          {top[0] !== "Cropland" && <span className="text-warning"> (the crop label here is dummy)</span>}
        </p>
      )}
      <SourceNote>{v?.basis} Real Sentinel-2 data; a falling index is a signal to inspect, not a diagnosis.</SourceNote>
    </Card>
  );
};

export default HealthCard;

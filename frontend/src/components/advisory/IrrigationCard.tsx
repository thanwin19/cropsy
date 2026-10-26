import React from "react";
import { Droplets } from "lucide-react";
import type { FieldReport } from "@/lib/cropsy-api";
import { Badge, Card, Segmented, SourceNote, Stat } from "../stitch/ui";

type Method = "drip" | "sprinkler" | "flood";
const hrs = (h: number) => (h <= 0 ? "-" : h < 1 ? `${Math.round(h * 60)} min` : `${h.toFixed(1)} h`);

export const IrrigationCard: React.FC<{
  report: FieldReport; method: Method; pump: number; onMethod: (m: Method) => void; onPump: (v: number) => void;
}> = ({ report, method, pump, onMethod, onPump }) => {
  const ir = report.irrigation;
  const paddy = report.crop.name === "Rice";
  const max = Math.max(...ir.days.map((d) => d.gross_mm), 1);
  return (
    <Card title="Irrigation" eyebrow="Next 7 days" icon={<Droplets size={16} />} right={<Badge tone={report.forecast_source === "live" ? "ok" : "warn"}>{report.forecast_source} forecast</Badge>}>
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Water to apply" value={`${ir.total_gross_mm} mm`} hint={`${ir.irrigation_days} irrigation days`} />
        <Stat label="Whole parcel" value={`${ir.total_volume_m3.toLocaleString()} m³`} hint="gross, after losses" />
        <Stat label="Pump running" value={hrs(ir.total_pump_hours)} hint={`at ${ir.pump_lps} L/s`} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          Method
          {paddy ? <Badge tone="info">Flooded paddy</Badge> : (
            <Segmented<Method> value={method} onChange={onMethod} options={[{ value: "drip", label: "Drip" }, { value: "sprinkler", label: "Sprinkler" }, { value: "flood", label: "Surface" }]} />
          )}
        </div>
        <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
          Pump
          <input type="number" min={0.5} max={200} step={0.5} defaultValue={pump} key={pump}
            onBlur={(e) => { const v = Number(e.target.value); if (v >= 0.5 && v <= 200 && v !== pump) onPump(v); }}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="w-16 rounded-md border border-white/10 bg-black/25 px-2 py-1 font-mono text-xs text-white" />
          L/s
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-[11.5px]">
          <thead>
            <tr className="border-b border-white/10 text-left font-mono text-[9.5px] uppercase text-muted-foreground/70">
              <th className="py-1.5 pr-2">Day</th><th className="pr-2">Water</th><th className="pr-2 text-right">Rain</th><th className="pr-2 text-right">Chance</th><th className="pr-2 text-right">Volume</th><th className="text-right">Pump</th>
            </tr>
          </thead>
          <tbody>
            {ir.days.map((d) => (
              <tr key={d.date} className="border-b border-white/[0.05]">
                <td className="py-1.5 pr-2 font-mono text-foreground">{new Date(d.date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })}</td>
                <td className="pr-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full rounded-full bg-[#38bdf8]" style={{ width: `${(d.gross_mm / max) * 100}%` }} /></div>
                    <span className={`font-mono ${d.irrigate ? "text-white" : "text-muted-foreground/70"}`}>{d.gross_mm} mm</span>
                  </div>
                </td>
                <td className="pr-2 text-right font-mono text-muted-foreground">{d.rain_mm} mm</td>
                <td className="pr-2 text-right font-mono text-muted-foreground">{d.rain_probability_pct != null ? `${d.rain_probability_pct}%` : "n/a"}</td>
                <td className="pr-2 text-right font-mono text-foreground">{d.volume_m3.toLocaleString()} m³</td>
                <td className="text-right font-mono text-white">{hrs(d.pump_hours)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-foreground"><span className="text-muted-foreground/70">Best time window: </span>{ir.best_window}</p>
      <SourceNote>{ir.basis} {report.water.note}</SourceNote>
    </Card>
  );
};

export default IrrigationCard;

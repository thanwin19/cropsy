import { useEffect, useState } from "react";
import { Droplets, FlaskConical, Leaf, TriangleAlert } from "lucide-react";
import { fetchFieldReport, type FieldReport, type WatchItem } from "@/lib/cropsy-api";
import { Metric, Panel, SampleTag, StatusChip } from "./ui";

const STATUS_TONE = { normal: "good", watch: "warn", stress: "bad", insufficient: "default" } as const;
const SEV_TONE = { high: "bad", medium: "warn", low: "good" } as const;
const weekday = (iso: string) => new Date(iso + "T12:00:00").toLocaleDateString("en-GB", { weekday: "short" });
const first = <T,>(xs?: T[]) => (xs && xs.length ? xs[0] : undefined);

/**
 * The at-a-glance "Today" cards for one parcel: crop and health, area, yield outlook, soil, 7-day water balance, early-stress signal,
 * irrigation with a pump window, the N-P-K plan and the pest and disease watch. Every figure comes from the live field report;
 * the detailed cards below this block hold the same data with its sources.
 */
export function TodaySummary({ parcelId }: { parcelId: string }) {
  const [r, setR] = useState<FieldReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setR(null);
    setErr(null);
    fetchFieldReport(parcelId)
      .then((x) => live && setR(x))
      .catch((e) => live && setErr(e?.message || "Could not load the field report"));
    return () => {
      live = false;
    };
  }, [parcelId]);

  if (err) return <p className="mb-5 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">{err}. Start the backend (port 8000).</p>;
  if (!r) return <div className="mb-5 h-48 animate-pulse rounded-xl border border-border bg-muted/30" />;

  const status = (r.health.status || "insufficient") as keyof typeof STATUS_TONE;
  const stage = r.crop.stage.split(" - ")[0];
  const ir = r.irrigation;
  const plan = first(r.fertilizer.options);
  const organic = first(r.fertilizer.organic);
  const yo = r.yield_outlook;
  const stressAlert = r.alerts.find((a) => a.type === "crop_stress");
  const watch: WatchItem[] = r.watch.watchlist.slice(0, 4);

  return (
    <section className="mb-6" aria-label={`Today at a glance for ${r.parcel_id}`}>
      <div className="grid gap-3 md:grid-cols-4">
        <Panel className="p-4">
          <div className="flex items-center justify-between">
            <Leaf className="size-4 text-success" />
            <StatusChip tone={STATUS_TONE[status] ?? "default"}>{status}</StatusChip>
          </div>
          <p className="mt-5 text-xl font-semibold">{r.crop.name}</p>
          <p className="text-xs text-muted-foreground">
            {stage} · day {r.crop.days_after_planting} · <SampleTag kind="dummy label" />
          </p>
        </Panel>
        <Panel className="p-4">
          <Metric label="Area" value={`${r.area_ha} ha`} detail={`${r.crop.variety} · planted ${r.crop.planting_date}`} />
        </Panel>
        <Panel className="p-4">
          <Metric
            label="Yield outlook"
            value={yo ? `${yo.expected_low}–${yo.expected_high} ${yo.unit}` : "n/a"}
            detail={yo ? "From this parcel's last three seasons · sample" : "No yield history"}
          />
        </Panel>
        <Panel className="p-4">
          <Metric
            label="Soil"
            value={`${r.soil_panel.record_ph != null ? `pH ${r.soil_panel.record_ph}` : "pH n/a"} · ${r.soil_panel.texture}`}
            detail={`${r.soil_panel.drainage.replace(/_/g, " ")} · record is dummy`}
          />
        </Panel>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[1.2fr_.8fr]">
        <Panel className="p-4">
          <h2 className="text-sm font-semibold">7-day water balance</h2>
          <div className="mt-4 grid grid-cols-7 gap-1">
            {ir.days.slice(0, 7).map((d) => (
              <div key={d.date} className="min-w-0 border-r border-border text-center last:border-0">
                <p className="text-[10px] text-muted-foreground">{weekday(d.date)}</p>
                <p className="mt-2 font-mono text-sm">{d.etc_mm}</p>
                <p className="text-[9px] text-muted-foreground">mm use</p>
                <p className={`mt-1 text-[9px] ${d.rain_mm > 0 ? "text-primary" : "text-muted-foreground"}`}>{d.rain_mm > 0 ? `Rain ${d.rain_mm} mm` : "Dry"}</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[10px] text-muted-foreground">Crop water use against forecast rain · {r.forecast_source}</p>
        </Panel>

        <Panel className="p-4">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <TriangleAlert className="size-4 text-warning" />
            Early stress
          </p>
          <p className="mt-3 text-sm">{stressAlert ? stressAlert.title : r.health.status === "stress" ? "Greenness is falling." : "No active stress detected."}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            {r.health.latest_ndvi != null
              ? `NDVI ${r.health.latest_ndvi} on ${r.health.latest_date}${r.health.change != null ? ` · change ${r.health.change > 0 ? "+" : ""}${r.health.change}` : ""}`
              : "No clear satellite view yet"}{" "}
            · <SampleTag kind="real satellite data" />
          </p>
        </Panel>

        <Panel className="p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Droplets className="size-4 text-primary" />
            Irrigation
          </h2>
          <p className="mt-3 font-mono text-2xl">{ir.irrigation_days ? `${ir.total_gross_mm} mm` : "None needed"}</p>
          <p className="text-xs text-muted-foreground">
            {ir.irrigation_days ? `Over ${ir.irrigation_days} day${ir.irrigation_days > 1 ? "s" : ""} this week · ${ir.method}` : "Forecast rain and soil water cover the crop's use"}
          </p>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <Metric label="Pump window" value={ir.best_window} />
            <Metric label="Pump hours" value={`${ir.total_pump_hours} h at ${ir.pump_lps} L/s`} />
          </div>
        </Panel>

        <Panel className="p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <FlaskConical className="size-4 text-primary" />
            N–P–K plan
          </h2>
          {plan ? (
            <>
              <div className="mt-4 grid grid-cols-3 gap-3">
                <Metric label="N" value={`${plan.N_kg} kg`} />
                <Metric label="P₂O₅" value={`${plan.P2O5_kg} kg`} />
                <Metric label="K₂O" value={`${plan.K2O_kg} kg`} />
              </div>
              <p className="mt-4 text-xs text-muted-foreground">
                Whole parcel ({r.fertilizer.area_ha} ha) · urea {plan.urea_kg} kg, DAP {plan.dap_kg} kg, MOP {plan.mop_kg} kg · {plan.source}
                {organic ? ` · organic: ${organic.text}` : ""}
              </p>
            </>
          ) : (
            <p className="mt-3 text-xs text-muted-foreground">{r.fertilizer.note}</p>
          )}
        </Panel>
      </div>

      <Panel className="mt-3 p-4">
        <h2 className="text-sm font-semibold">Pest & disease watch</h2>
        {watch.length === 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">{r.watch.note}</p>
        ) : (
          <div className="mt-3 divide-y divide-border">
            {watch.map((w) => {
              const chem = first(w.chemical);
              const org = first(w.organic) ?? first(w.cultural);
              return (
                <div key={w.code} className="grid gap-2 py-3 sm:grid-cols-3">
                  <span className="flex items-start gap-2 text-sm">
                    {w.name} <StatusChip tone={SEV_TONE[w.severity as keyof typeof SEV_TONE] ?? "default"}>{w.recorded_on_parcel ? "recorded" : w.severity}</StatusChip>
                  </span>
                  <span className="text-xs">{chem ? `Chemical: ${chem.text}` : "Chemical: no verified TNAU control"}</span>
                  <span className="text-xs">{org ? `Organic / cultural: ${org.text}` : "Organic: no verified TNAU control"}</span>
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-2 text-[10px] text-muted-foreground">Controls quoted from TNAU's 2020 guides; check current product registration and follow the label.</p>
      </Panel>
    </section>
  );
}

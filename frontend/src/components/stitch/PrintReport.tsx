import React from "react";
import type { Cited, FieldReport } from "@/lib/cropsy-api";

interface Props {
  report: FieldReport;
  onClose?: () => void;
}

/** Print rules: hide the whole app, show only the report on white paper. window.print() then "Save as PDF" gives the document. */
const PRINT_CSS = `
@media print {
  body * { visibility: hidden !important; }
  #print-report, #print-report * { visibility: visible !important; }
  #print-report { position: absolute !important; inset: 0 auto auto 0 !important; width: 100% !important; max-width: none !important;
                  margin: 0 !important; border-radius: 0 !important; box-shadow: none !important; padding: 0 !important; background: #fff !important; }
  .no-print { display: none !important; }
  .keep { break-inside: avoid; }
  @page { size: A4; margin: 12mm; }
}`;

const H: React.FC<{ n: string; children: React.ReactNode }> = ({ n, children }) => (
  <h2 className="mb-1.5 mt-5 border-b border-[#cfdad7] pb-1 font-serif text-[15px] font-semibold text-[#0d2a26]">
    <span className="mr-2 font-mono text-[11px] text-[#5b7873]">{n}</span>{children}
  </h2>
);
const Row: React.FC<{ k: string; v: React.ReactNode }> = ({ k, v }) => (
  <div className="flex justify-between gap-4 border-b border-[#e6eeec] py-1 text-[12px]">
    <span className="text-[#4d6662]">{k}</span><span className="text-right font-mono text-[#14211f]">{v}</span>
  </div>
);
const Note: React.FC<{ children: React.ReactNode }> = ({ children }) => <p className="mt-1 text-[10.5px] leading-snug text-[#5b7873]">{children}</p>;
const Cites: React.FC<{ label: string; items?: Cited[] }> = ({ label, items }) =>
  items && items.length ? (
    <div className="mt-1">
      <div className="text-[10.5px] font-semibold uppercase tracking-wide text-[#4d6662]">{label}</div>
      <ul className="list-disc pl-4 text-[11.5px] text-[#14211f]">
        {items.map((c, i) => <li key={i}>{c.text} <span className="font-mono text-[10px] text-[#5b7873]">({c.source})</span></li>)}
      </ul>
    </div>
  ) : null;

export const PrintReport: React.FC<Props> = ({ report: r, onClose }) => {
  const today = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const ir = r.irrigation;
  const sp = r.soil_panel;
  const yo = r.yield_outlook;
  const pl = r.plants;

  return (
    <div className="flex flex-col items-center gap-3 p-3">
      <style>{PRINT_CSS}</style>
      <div className="no-print flex w-full max-w-[820px] items-center justify-between">
        <span className="text-xs text-muted-foreground">Print preview. Choose "Save as PDF" in the print dialog to keep a copy.</span>
        <div className="flex gap-2">
          <button onClick={() => window.print()} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90">Print / Save as PDF</button>
          {onClose && <button onClick={onClose} className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-foreground hover:border-white/30">Close</button>}
        </div>
      </div>

      <article id="print-report" className="w-full max-w-[820px] rounded-xl bg-white p-8 text-[#14211f] shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b-2 border-[#0d2a26] pb-3">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-widest text-[#5b7873]">Then Malai · Field advisory report</div>
            <h1 className="font-serif text-2xl font-semibold text-[#0d2a26]">Parcel {r.parcel_id}</h1>
            <p className="text-[12.5px] text-[#2c4440]">
              {r.crop.name} ({r.crop.variety}) · {r.crop.stage.split(" - ")[0]} · {r.crop.days_after_planting} days after planting · {r.area_ha} ha · planted {r.crop.planting_date}
            </p>
          </div>
          <div className="text-right text-[11px] text-[#4d6662]">
            <div>{today}</div>
            <div className="mt-1 inline-block rounded border border-[#d4a73a] bg-[#fff6dd] px-2 py-0.5 font-mono text-[10px] text-[#7a5a05]">SAMPLE DATA · crop labels are dummy</div>
          </div>
        </header>

        <section className="keep mt-4 rounded-lg border border-[#0f8f72] bg-[#e9f8f3] p-3">
          <div className="font-mono text-[10px] uppercase tracking-wider text-[#0f6b57]">What to do now</div>
          <div className="font-serif text-[16px] font-semibold text-[#0d2a26]">{r.instruction.headline}</div>
          <ol className="mt-1 list-decimal pl-5 text-[12.5px]">{r.instruction.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <Note>{r.instruction.basis}</Note>
        </section>

        <H n="1">How is the crop doing?</H>
        <div className="keep">
          {r.vigour?.classes?.length ? (
            <>
              <div className="flex h-3.5 w-full overflow-hidden rounded">
                {r.vigour.classes.filter((c) => c.share > 0).map((c) => <div key={c.name} title={`${c.name} ${Math.round(c.share * 100)}%`} style={{ width: `${c.share * 100}%`, background: c.color }} />)}
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px]">
                {r.vigour.classes.filter((c) => c.share > 0).map((c) => <span key={c.name}><i className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: c.color }} />{c.name} {Math.round(c.share * 100)}%</span>)}
              </div>
              <Note>{r.vigour.basis} (month {r.vigour.month})</Note>
            </>
          ) : null}
          {r.health.latest_ndvi != null && (
            <>
              <Row k="Latest greenness (NDVI)" v={`${r.health.latest_ndvi} on ${r.health.latest_date}`} />
              <Row k="Its own recent baseline" v={r.health.baseline_ndvi ?? "not enough clear views"} />
              <Row k="Change" v={r.health.change != null ? `${r.health.change > 0 ? "+" : ""}${r.health.change}` : "n/a"} />
            </>
          )}
          {r.field_directions && <Row k="Where to look first" v={r.field_directions.note} />}
          <Note>{r.health.label || "Real Sentinel-2 satellite data at this location. A falling index is a signal to inspect the field, not a diagnosis."}</Note>
        </div>

        <H n="2">How much water, and when?</H>
        <div className="keep">
          <Row k="Method · efficiency" v={`${ir.method} · ${Math.round(ir.efficiency * 100)}%`} />
          <Row k="Irrigation days · gross water" v={`${ir.irrigation_days} days · ${ir.total_gross_mm} mm`} />
          <Row k="Volume · pump hours" v={`${Math.round(ir.total_volume_m3).toLocaleString()} m³ · ${ir.total_pump_hours} h at ${ir.pump_lps} L/s`} />
          <Row k="Best window" v={ir.best_window} />
          <table className="mt-2 w-full text-[11px]">
            <thead><tr className="border-b border-[#cfdad7] text-left text-[#4d6662]"><th className="py-1">Date</th><th>Crop use (mm)</th><th>Rain (mm)</th><th>Apply (mm)</th><th>Pump (h)</th></tr></thead>
            <tbody>
              {ir.days.map((d) => (
                <tr key={d.date} className="border-b border-[#e6eeec]">
                  <td className="py-0.5 font-mono">{d.date.slice(5)}</td><td>{d.etc_mm}</td><td>{d.rain_mm}</td>
                  <td className={d.irrigate ? "font-semibold" : "text-[#8aa19e]"}>{d.irrigate ? d.gross_mm : "none"}</td><td>{d.irrigate ? d.pump_hours : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Note>{ir.basis}</Note>
        </div>

        <H n="3">What is the soil like?</H>
        <div className="keep">
          <Row k="pH (parcel record, dummy)" v={sp.record_ph != null ? `${sp.record_ph}${sp.record_ph_rating ? ` · ${sp.record_ph_rating.class}` : ""}` : "n/a"} />
          <Row k="pH (SoilGrids model, 250 m)" v={sp.soilgrids_ph ?? "n/a"} />
          <Row k="Organic carbon (SoilGrids)" v={sp.organic_carbon_g_per_kg != null ? `${sp.organic_carbon_g_per_kg} g/kg` : "n/a"} />
          <Row k="Texture · drainage" v={`${sp.texture} · ${sp.drainage.replace(/_/g, " ")}`} />
          <Row k="Land cover under the parcel" v={sp.dominant_land_cover ?? "n/a"} />
          <Row k="Salinity" v={sp.salinity.status} />
          {sp.record_ph_rating && <Note>{sp.record_ph_rating.advice}</Note>}
          <Note>{sp.salinity.note} {sp.basis}</Note>
        </div>

        <H n="4">Growth, yield and plants</H>
        <div className="keep">
          {r.harvest.available ? (
            <Row k="Expected harvest" v={`${r.harvest.window_start} to ${r.harvest.window_end} (in ${r.harvest.days_to_start} days)`} />
          ) : <Row k="Harvest" v={r.harvest.note ?? "n/a"} />}
          {yo && (
            <>
              <Row k="Sample yield outlook (not a forecast)" v={`${yo.expected_low} to ${yo.expected_high} ${yo.unit} (mid ${yo.expected_mid})`} />
              {yo.expected_total != null && <Row k="Expected total" v={yo.expected_total.toLocaleString()} />}
              <Note>{yo.basis}</Note>
            </>
          )}
          {pl.available ? (
            <>
              <Row k="Expected plant stand" v={`${(pl.plants ?? pl.plants_usable ?? pl.plants_at_spacing ?? 0).toLocaleString()} ${pl.unit ?? "plants"} at ${pl.spacing}`} />
              <Note>{pl.note}</Note>
            </>
          ) : <Note>{pl.note}</Note>}
        </div>

        <H n="5">Pests, diseases and weeds to watch</H>
        <div>
          {r.watch.weather_signal && (
            <p className="text-[11.5px]"><b>Weather signal:</b> {r.watch.weather_signal.favours_fungal ? "humid, wet days favour fungal disease." : "not an especially disease-favouring week."} <span className="text-[#5b7873]">({r.watch.weather_signal.basis})</span></p>
          )}
          {r.watch.watchlist.map((w) => (
            <div key={w.code} className="keep mt-2 rounded border border-[#cfdad7] p-2">
              <div className="flex items-center justify-between text-[12px] font-semibold">
                <span>{w.name}{w.recorded_on_parcel ? " (recorded on this parcel)" : ""}</span>
                <span className="font-mono text-[10.5px] font-normal text-[#5b7873]">{w.kind} · {w.severity}</span>
              </div>
              {w.symptoms.length > 0 && <p className="text-[11px] text-[#4d6662]">Look for: {w.symptoms.join("; ")}.</p>}
              <Cites label="Cultural" items={w.cultural} />
              <Cites label="Organic / biological" items={w.organic} />
              <Cites label="Chemical" items={w.chemical} />
            </div>
          ))}
          {r.watch.recorded_without_advice && <Note>{r.watch.recorded_without_advice}</Note>}
          <div className="keep mt-2 rounded border border-[#cfdad7] p-2">
            <div className="text-[12px] font-semibold">Weeds</div>
            <Cites label="Chemical" items={r.watch.weeds.chemical} />
            <Cites label="Organic / cultural" items={r.watch.weeds.organic} />
          </div>
          <Note>{r.watch.note}</Note>
        </div>

        <H n="6">What fertiliser is needed?</H>
        <div className="keep">
          {r.fertilizer.options.length ? (
            <table className="w-full text-[11px]">
              <thead><tr className="border-b border-[#cfdad7] text-left text-[#4d6662]"><th className="py-1">TNAU recommendation</th><th>N</th><th>P2O5</th><th>K2O</th><th>Urea</th><th>DAP</th><th>MOP</th></tr></thead>
              <tbody>
                {r.fertilizer.options.map((o) => (
                  <tr key={o.recommendation} className="border-b border-[#e6eeec] align-top">
                    <td className="py-1"><div className="font-mono">{o.recommendation}</div><div className="text-[10px] text-[#5b7873]">{o.source}</div></td>
                    <td>{o.N_kg}</td><td>{o.P2O5_kg}</td><td>{o.K2O_kg}</td><td>{o.urea_kg}</td><td>{o.dap_kg}</td><td>{o.mop_kg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="text-[11.5px]">{r.fertilizer.note}</p>}
          <Note>Whole-parcel quantities in kg for {r.fertilizer.area_ha} ha. {r.fertilizer.note} {r.fertilizer.assumptions}.</Note>
          <Cites label="Organic and bio-fertiliser options (TNAU)" items={r.fertilizer.organic} />
          <Cites label="Timing and splits (TNAU)" items={r.fertilizer.schedule} />
        </div>

        {r.alerts.length > 0 && (
          <>
            <H n="!">Alerts for this parcel</H>
            <ul className="list-disc pl-5 text-[12px]">
              {r.alerts.map((a, i) => <li key={i}><b>{a.title}</b> ({a.severity}). {a.detail} {a.action}</li>)}
            </ul>
          </>
        )}

        <footer className="keep mt-6 rounded border border-[#d4a73a] bg-[#fff9e8] p-3 text-[10.5px] leading-relaxed text-[#5a4506]">
          <b>Please read.</b> This is an AI-assisted advisory for a demonstration village. Crop names, stages, issues, owners, inputs and yield history are
          dummy data. Satellite values (Sentinel-1 and Sentinel-2), elevation, land cover and soil model values are real and taken at the parcel's coordinates.
          Doses and controls are quoted from TNAU's 2020 guides; check that a product is currently registered (CIB&amp;RC) and follow its label. Water,
          alerts and instructions come from fixed rules, not from a trained model. Verify with an agricultural officer before acting.
        </footer>
      </article>
    </div>
  );
};

export default PrintReport;

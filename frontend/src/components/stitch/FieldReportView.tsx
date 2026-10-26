import React, { useCallback, useEffect, useRef, useState } from "react";
import { BellRing, ShieldAlert } from "lucide-react";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import {
  fetchAlerts, fetchFieldReport, fetchVillageBrief, postSoilTest,
  type AlertsResponse, type FieldAlert, type FieldReport, type SoilTestResult, type VillageBrief,
} from "@/lib/cropsy-api";
import { clientLazy } from "../client-lazy";
import { WildlifeSection } from "../ParcelFactsCard";
// Leaflet needs the browser, so the mini map is loaded on the client only
const ParcelMiniMap = clientLazy(() => import("../advisory/ParcelMiniMap").then((m) => ({ default: m.ParcelMiniMap })), <div className="h-full min-h-[300px] animate-pulse rounded-xl border border-border bg-muted/30" />);
import { HealthCard, type AreaUnit } from "../advisory/HealthCard";
import { IrrigationCard } from "../advisory/IrrigationCard";
import { SoilCard, EMPTY_SOIL, type SoilValues } from "../advisory/SoilCard";
import { GrowthYieldCard } from "../advisory/GrowthYieldCard";
import { WatchCard } from "../advisory/WatchCard";
import { FertilizerCard } from "../advisory/FertilizerCard";
import { Badge, Card, DummyBadge, Empty, PageHeader, PageShell } from "./ui";

interface FieldReportViewProps {
  selectedParcelId: string;
  onBackToChat: () => void;
  onSelectParcel: (id: string) => void;
  onAskQuestion?: (q: string) => void;
}

type Method = "drip" | "sprinkler" | "flood";
const SEV_TONE = { high: "bad", medium: "warn", low: "ok" } as const;
const SOIL_KEY = (id: string) => `cropsy-soil-test-${id}`;

const AlertRow: React.FC<{ a: FieldAlert; onOpen?: () => void; showParcel?: boolean }> = ({ a, onOpen, showParcel }) => (
  <div className="flex flex-col gap-1 rounded-xl border border-white/[0.07] bg-black/20 p-3">
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs font-semibold text-foreground">{showParcel ? `${a.parcel_id} · ` : ""}{a.title}</span>
      <Badge tone={SEV_TONE[a.severity]}>{a.severity}</Badge>
    </div>
    <p className="text-[11.5px] leading-relaxed text-muted-foreground">{a.detail}</p>
    <p className="text-[11.5px] text-foreground">{a.action}</p>
    <div className="flex items-center justify-between">
      <span className="font-mono text-[10px] text-muted-foreground/70">basis: {a.basis}</span>
      {onOpen && <button onClick={onOpen} className="text-[11px] text-primary hover:underline">Open {a.parcel_id}</button>}
    </div>
  </div>
);

export const FieldReportView: React.FC<FieldReportViewProps> = ({ selectedParcelId, onBackToChat, onSelectParcel, onAskQuestion }) => {
  const p = THEN_MALAI_PARCELS.find((x) => x.id === selectedParcelId) || THEN_MALAI_PARCELS[0];
  const [report, setReport] = useState<FieldReport | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [brief, setBrief] = useState<VillageBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloading, setReloading] = useState(false);
  const [filter, setFilter] = useState<"all" | "crop_stress" | "heavy_rain" | "irrigation_due" | "recorded_issue">("all");
  const [method, setMethod] = useState<Method>("sprinkler");
  const [pump, setPump] = useState(8);
  const [unit, setUnit] = useState<AreaUnit>("ha");
  const [soilValues, setSoilValues] = useState<SoilValues>(EMPTY_SOIL);
  const [soilResult, setSoilResult] = useState<SoilTestResult | null>(null);
  const [soilBusy, setSoilBusy] = useState(false);
  const [soilError, setSoilError] = useState<string | null>(null);
  const firstLoad = useRef(true);

  // report (reloads when the parcel, irrigation method or pump rate change; the old report stays visible meanwhile)
  useEffect(() => {
    let live = true;
    if (firstLoad.current) setReport(null); else setReloading(true);
    setError(null);
    fetchFieldReport(p.id, method, pump)
      .then((r) => { if (live) { setReport(r); firstLoad.current = false; } })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setReloading(false));
    return () => { live = false; };
  }, [p.id, method, pump]);

  // a different parcel: restart cleanly and restore that parcel's saved soil test
  const evaluate = useCallback(async (id: string, values: SoilValues) => {
    const nums: Record<string, number> = {};
    (Object.keys(values) as (keyof SoilValues)[]).forEach((k) => { if (values[k].trim() !== "" && !Number.isNaN(Number(values[k]))) nums[k] = Number(values[k]); });
    if (!Object.keys(nums).length) { setSoilResult(null); return; }
    setSoilBusy(true); setSoilError(null);
    try { setSoilResult(await postSoilTest(id, nums)); localStorage.setItem(SOIL_KEY(id), JSON.stringify(values)); }
    catch (e: any) { setSoilError(e.message || "Could not rate the soil test"); }
    finally { setSoilBusy(false); }
  }, []);

  useEffect(() => {
    firstLoad.current = true;
    setSoilResult(null); setSoilError(null);
    let saved = EMPTY_SOIL;
    try { const raw = localStorage.getItem(SOIL_KEY(p.id)); if (raw) saved = { ...EMPTY_SOIL, ...JSON.parse(raw) }; } catch { /* private window: ignore */ }
    setSoilValues(saved);
    if (Object.values(saved).some((v) => v !== "")) evaluate(p.id, saved);
  }, [p.id, evaluate]);

  useEffect(() => { fetchVillageBrief().then(setBrief).catch(() => undefined); fetchAlerts("low").then(setAlerts).catch(() => undefined); }, []);

  const clearSoil = () => { setSoilValues(EMPTY_SOIL); setSoilResult(null); try { localStorage.removeItem(SOIL_KEY(p.id)); } catch { /* ignore */ } };
  const shown = (alerts?.alerts || []).filter((a) => filter === "all" || a.type === filter).slice(0, 60);

  return (
    <PageShell>
      <PageHeader onBack={onBackToChat} crumb={`Farm advisory · ${p.id} · ${p.crop}`} right={<div className="flex items-center gap-2">{reloading && <Badge tone="mute">updating…</Badge>}<DummyBadge /></div>} />
      <p className="max-w-4xl text-[12px] leading-relaxed text-muted-foreground">
        A plain-language advisory for one field, built from real satellite, weather and soil-model data and from TNAU's own wording. Where a number needs data we do not have
        (salinity, soil nutrients), you enter it; nothing is guessed. The crop names, stages, issues and inputs of this demo village are dummy.
      </p>

      {brief && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-warning/35 bg-gradient-to-b from-warning/[0.10] to-transparent p-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-warning">Then Malai today · all {brief.counts.fields} fields</span>
            <h2 className="mt-1 font-serif text-xl font-semibold text-white">{brief.headline}</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-foreground">{brief.steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </section>
          {report && (
            <section className="rounded-2xl border border-primary/35 bg-gradient-to-b from-primary/[0.10] to-transparent p-4">
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-primary">What to do now · {p.id}</span>
              <h2 className="mt-1 font-serif text-xl font-semibold text-white">{report.instruction.headline}</h2>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-[13px] text-foreground">{report.instruction.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              {report.field_directions && <p className="mt-2 text-xs text-foreground"><span className="text-muted-foreground/70">Where to look first: </span>{report.field_directions.note}</p>}
            </section>
          )}
        </div>
      )}

      {error && <Empty>{error}. Start the backend (port 8000).</Empty>}
      {!error && !report && <Empty>Preparing the advisory for {p.id}…</Empty>}

      {report && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="xl:col-span-5"><ParcelMiniMap parcelId={p.id} lastVisit={report.health.latest_date ?? null} /></div>
          <div className="xl:col-span-4"><HealthCard report={report} unit={unit} onUnit={setUnit} /></div>
          <div className="xl:col-span-3">
            <Card title={`Alerts for ${p.id}`} eyebrow="This field" icon={<ShieldAlert size={16} />} className="h-full">
              {report.alerts.length === 0 ? <p className="text-xs text-muted-foreground">Nothing needs attention on this parcel right now.</p> : report.alerts.map((a, i) => <AlertRow key={i} a={a} />)}
            </Card>
          </div>

          <div className="xl:col-span-7"><IrrigationCard report={report} method={method} pump={pump} onMethod={setMethod} onPump={setPump} /></div>
          <div className="xl:col-span-5">
            <SoilCard report={report} values={soilValues} onValues={setSoilValues} result={soilResult} busy={soilBusy} error={soilError}
              onEvaluate={() => evaluate(p.id, soilValues)} onClear={clearSoil} />
          </div>

          <div className="xl:col-span-4"><GrowthYieldCard report={report} /></div>
          <div className="xl:col-span-8"><WatchCard report={report} onAsk={onAskQuestion} /></div>
          {report.wildlife && <div className="xl:col-span-12"><WildlifeSection w={report.wildlife} /></div>}

          <div className="xl:col-span-8"><FertilizerCard report={report} soil={soilResult} unit={unit} /></div>
          <div className="xl:col-span-4">
            <Card title={`Village alerts${alerts ? ` (${alerts.count})` : ""}`} eyebrow="All 120 fields" icon={<BellRing size={16} />} className="h-full">
              {alerts && (
                <div className="flex flex-wrap gap-1.5">
                  {(["all", "crop_stress", "heavy_rain", "irrigation_due", "recorded_issue"] as const).map((f) => (
                    <button key={f} onClick={() => setFilter(f)}
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] ${filter === f ? "border-primary bg-primary/10 text-primary" : "border-white/10 text-muted-foreground hover:text-white"}`}>
                      {f === "all" ? `All ${alerts.count}` : `${f.replace(/_/g, " ")} ${alerts.by_type[f] ?? 0}`}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex max-h-[52vh] flex-col gap-2 overflow-y-auto pr-1">
                {!alerts && <p className="text-xs text-muted-foreground">Loading alerts…</p>}
                {shown.map((a, i) => <AlertRow key={`${a.parcel_id}-${a.type}-${i}`} a={a} showParcel onOpen={() => onSelectParcel(a.parcel_id)} />)}
              </div>
              {alerts && <p className="text-[10.5px] text-muted-foreground/70">Forecast: {alerts.forecast_source}. "Recorded issue" alerts come from dummy parcel records and rank lowest.</p>}
            </Card>
          </div>
        </div>
      )}

      <footer className="mt-2 rounded-xl border border-white/[0.06] bg-black/20 px-4 py-3 text-[11px] leading-relaxed text-muted-foreground/70">
        This advisory is generated from data and fixed rules and quotes TNAU guidance; it is a general guide. Verify recommendations with your agricultural officer or KVK
        and adapt them to local conditions, especially before using any chemical.
      </footer>
    </PageShell>
  );
};

export default FieldReportView;

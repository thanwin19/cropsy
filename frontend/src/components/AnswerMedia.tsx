import { useEffect, useState } from "react";
import { getApiSettings, type Phase7AdvisoryResult } from "@/lib/cropsy-api";

/**
 * Pictures that help the text answer, shown small under the explanation and only when they fit the question:
 *  - reference photos of the problem the answer is about (public-dataset photos chosen by the backend, never the farmer's own field);
 *  - a simple diagram for a process or a number (soil pH, a compost bed, plant spacing), drawn here, so nothing has to load;
 *  - a YouTube SEARCH link for how-to and pest or disease questions. It is labelled as a search: Cropsy does not claim a specific video it has not checked.
 * Text stays the main answer.
 */

const SCALE = ["#d9534f", "#e8873a", "#e9b83a", "#c9d44a", "#7dc667", "#4aa86a", "#3b9a8c"];

export function PhScale({ value }: { value: number | null }) {
  const v = value != null ? Math.min(10, Math.max(4, value)) : null;
  const x = (ph: number) => 14 + ((ph - 4) / 6) * 292;
  const label = value == null ? "" : value < 6 ? "acidic" : value <= 7.5 ? "about neutral" : value <= 8.5 ? "alkaline" : "strongly alkaline";
  const seg = 292 / 7;
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Soil pH scale">
      <svg viewBox="0 0 320 78" className="w-full" role="img" aria-label={value != null ? `Soil pH scale with ${value} marked, ${label}` : "Soil pH scale from 4 acidic to 10 alkaline"}>
        {["#d9534f", "#e8873a", "#e9b83a", "#7dc667", "#3b9a8c", "#3b7fb0", "#6a4fb0"].map((c, i) => <rect key={i} x={14 + i * seg} y="26" width={seg + 0.5} height="16" fill={c} />)}
        {[4, 5, 6, 7, 8, 9, 10].map((n) => <text key={n} x={x(n)} y="58" textAnchor="middle" fontSize="9" fill="currentColor">{n}</text>)}
        <text x="14" y="72" fontSize="8" fill="currentColor" opacity="0.7">acidic</text>
        <text x={x(7)} y="72" fontSize="8" textAnchor="middle" fill="currentColor" opacity="0.7">neutral</text>
        <text x="306" y="72" fontSize="8" textAnchor="end" fill="currentColor" opacity="0.7">alkaline</text>
        {v != null && (
          <g>
            <path d={`M${x(v)} 24 l-5 -10 h10 z`} fill="currentColor" />
            <text x={x(v)} y="10" textAnchor="middle" fontSize="10" fontWeight="700" fill="currentColor">pH {value}</text>
          </g>
        )}
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Soil pH scale (4 to 10){label ? `: ${value} is ${label}` : ""}. Most field crops do best near the middle of the scale.</figcaption>
    </figure>
  );
}

export function CompostBed() {
  const layers: [string, string][] = [["#8a7a4a", "Dry leaves and straw (bedding)"], ["#6b4a2e", "Partly decomposed cow dung + farm waste"], ["#4a3220", "Damp and shaded: worms work here"], ["#9b8f78", "Drainage at the base"]];
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Vermicompost bed">
      <svg viewBox="0 0 320 130" className="w-full" role="img" aria-label="Cross-section of a shaded vermicompost bed with bedding, dung layer and drainage">
        <path d="M8 12 L50 0 L270 0 L312 12 L312 18 L8 18 Z" fill="#7a9a5a" opacity="0.85" />
        <text x="160" y="13" textAnchor="middle" fontSize="8" fill="#fff">shade roof</text>
        {layers.map(([c, t], i) => (
          <g key={i}>
            <rect x="24" y={26 + i * 24} width="272" height="22" fill={c} rx="2" />
            <text x="34" y={41 + i * 24} fontSize="9" fill="#fff">{t}</text>
          </g>
        ))}
        <rect x="18" y="22" width="6" height="100" fill="currentColor" opacity="0.5" />
        <rect x="296" y="22" width="6" height="100" fill="currentColor" opacity="0.5" />
        <path d="M230 62 q8 -7 16 0 q8 7 16 0" stroke="#e9a0a0" strokeWidth="3" fill="none" />
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Simple vermicompost bed (illustration): bedding on top, dung and farm waste in the middle, drainage below. Keep it damp like a squeezed sponge and shaded.</figcaption>
    </figure>
  );
}

export function SpacingDiagram({ rows, plants }: { rows: number | null; plants: number | null }) {
  const dots = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 6; c++) dots.push(<circle key={`${r}-${c}`} cx={50 + c * 40} cy={24 + r * 30} r="6" fill="#4aa86a" />);
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Plant spacing">
      <svg viewBox="0 0 320 112" className="w-full" role="img" aria-label="Plants in rows with the distance between rows and between plants marked">
        {dots}
        <line x1="50" y1="88" x2="90" y2="88" stroke="currentColor" />
        <text x="70" y="102" textAnchor="middle" fontSize="9" fill="currentColor">{plants ? `${plants} cm between plants` : "between plants"}</text>
        <line x1="272" y1="24" x2="272" y2="54" stroke="currentColor" />
        <text x="276" y="42" fontSize="9" fill="currentColor">{rows ? `${rows} cm` : "rows"}</text>
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Plant spacing (illustration). Use the spacing named in the answer for your crop.</figcaption>
    </figure>
  );
}

export function DripDiagram() {
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Drip irrigation">
      <svg viewBox="0 0 320 120" className="w-full" role="img" aria-label="Drip irrigation: tank and pump, filter, main line, lateral lines with emitters at each plant">
        <rect x="8" y="30" width="34" height="40" rx="3" fill="#3b7fb0" /><text x="25" y="54" textAnchor="middle" fontSize="8" fill="#fff">tank</text>
        <rect x="52" y="42" width="26" height="16" rx="2" fill="#6a6a6a" /><text x="65" y="53" textAnchor="middle" fontSize="7" fill="#fff">filter</text>
        <line x1="42" y1="50" x2="52" y2="50" stroke="#3b7fb0" strokeWidth="3" /><line x1="78" y1="50" x2="100" y2="50" stroke="#3b7fb0" strokeWidth="3" />
        <line x1="100" y1="20" x2="100" y2="100" stroke="#3b7fb0" strokeWidth="3" />
        {[24, 60, 96].map((y) => (<g key={y}><line x1="100" y1={y} x2="300" y2={y} stroke="#5aa0d0" strokeWidth="1.5" />{[130, 170, 210, 250, 290].map((x) => (<g key={x}><circle cx={x} cy={y + 5} r="1.8" fill="#3b7fb0" /><circle cx={x} cy={y - 7} r="5" fill="#4aa86a" /></g>))}</g>))}
        <text x="104" y="114" fontSize="8" fill="currentColor">main line · lateral lines · one emitter at each plant's roots</text>
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Drip irrigation layout (illustration): water is filtered and sent along lateral lines to the root zone of each plant. Flush the lines and clean the filter regularly.</figcaption>
    </figure>
  );
}

export function CompostHeap() {
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Compost heap">
      <svg viewBox="0 0 320 120" className="w-full" role="img" aria-label="A covered compost heap in layers of straw, dung and soil in a shaded pit">
        <rect x="30" y="80" width="260" height="30" fill="#6b4a2e" rx="3" /><text x="160" y="99" textAnchor="middle" fontSize="9" fill="#fff">pit or ground level (keep rain out)</text>
        <path d="M60 80 L100 30 L220 30 L260 80 Z" fill="#8a7a4a" /><path d="M80 80 L110 45 L210 45 L240 80 Z" fill="#5b4028" /><path d="M105 80 L125 60 L195 60 L215 80 Z" fill="#8a7a4a" />
        <text x="160" y="25" textAnchor="middle" fontSize="9" fill="currentColor">cover with straw or sheet · turn now and then</text>
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Compost or farmyard-manure heap (illustration): layers of straw, dung and crop residue, covered so rain does not wash the nutrients out.</figcaption>
    </figure>
  );
}

export function GrowthStages() {
  const stages = ["Seed / sowing", "Seedling", "Vegetative growth", "Flowering", "Grain or fruit filling", "Harvest"];
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Crop growth stages">
      <svg viewBox="0 0 320 96" className="w-full" role="img" aria-label="Six crop growth stages from sowing to harvest">
        <line x1="20" y1="70" x2="300" y2="70" stroke="#6b4a2e" strokeWidth="3" />
        {stages.map((s, i) => {
          const x = 30 + i * 52;
          const h = 6 + i * 7 - (i === 5 ? 6 : 0);
          return (
            <g key={s}>
              <line x1={x} y1="70" x2={x} y2={70 - h} stroke="#4aa86a" strokeWidth="3" />
              {i >= 1 && <ellipse cx={x - 6} cy={70 - h * 0.6} rx="6" ry="3" fill="#4aa86a" />}
              {i >= 2 && <ellipse cx={x + 6} cy={70 - h * 0.85} rx="6" ry="3" fill="#4aa86a" />}
              {i === 3 && <circle cx={x} cy={70 - h - 3} r="4" fill="#e9b83a" />}
              {i >= 4 && <circle cx={x} cy={70 - h - 3} r="5" fill={i === 5 ? "#c9a23a" : "#8ab04a"} />}
              <text x={x} y="86" textAnchor="middle" fontSize="6.5" fill="currentColor">{s}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Generic growth stages (illustration). The number of days for each stage depends on the crop and variety: use the dates in the answer.</figcaption>
    </figure>
  );
}

export function NpkDiagram() {
  const rows: [string, string, string][] = [["N", "#4aa86a", "Nitrogen: leaf and shoot growth, green colour"], ["P", "#e8873a", "Phosphorus: roots, early growth, flowering"], ["K", "#6a4fb0", "Potassium: grain or fruit filling, strength, water balance"]];
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="What N, P and K do">
      <svg viewBox="0 0 320 92" className="w-full" role="img" aria-label="Nitrogen, phosphorus and potassium and what each does for a plant">
        {rows.map(([k, c, t], i) => (
          <g key={k}>
            <circle cx="24" cy={20 + i * 28} r="11" fill={c} />
            <text x="24" y={24 + i * 28} textAnchor="middle" fontSize="12" fontWeight="700" fill="#fff">{k}</text>
            <text x="44" y={24 + i * 28} fontSize="9.5" fill="currentColor">{t}</text>
          </g>
        ))}
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">The three main plant nutrients (illustration). The amounts for your crop are in the answer.</figcaption>
    </figure>
  );
}

const RATING_TONE: Record<string, string> = { low: "var(--warning)", "very low": "var(--destructive)", deficient: "var(--destructive)", high: "var(--warning)", "very high": "var(--destructive)", acidic: "var(--warning)", alkaline: "var(--warning)", saline: "var(--destructive)", medium: "var(--success)", moderate: "var(--success)", normal: "var(--success)", adequate: "var(--success)", sufficient: "var(--success)", neutral: "var(--success)" };

/** 'name value unit rating' rows read from the document, exactly as written there (the backend adds or converts nothing). */
export function DocValues({ rows }: { rows: NonNullable<Phase7AdvisoryResult["doc_values"]> }) {
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-border" data-testid="doc-values" aria-label="Values read from your document">
      <p className="bg-muted/40 px-3 py-1.5 text-xs font-semibold">Values read from your document</p>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border/60">
              <td className="px-3 py-1.5">{r.name}</td>
              <td className="px-2 py-1.5 text-right font-mono font-semibold">{r.value}{r.unit ? ` ${r.unit}` : ""}</td>
              <td className="px-3 py-1.5 text-right text-xs">{r.rating && <span className="rounded-full px-2 py-0.5" style={{ border: `1px solid ${RATING_TONE[r.rating] ?? "var(--border)"}`, color: RATING_TONE[r.rating] ?? "inherit" }}>{r.rating}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-1 text-[10.5px] text-muted-foreground">Read automatically; check the numbers against your original.</p>
    </div>
  );
}

export type WeatherRow = { date: string; rain_mm: number; tmax_c?: number | null; tmin_c?: number | null };

export function WeatherChart({ rows }: { rows: WeatherRow[] }) {
  const max = Math.max(10, ...rows.map((r) => r.rain_mm || 0));
  const bw = 280 / rows.length;
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Rain forecast">
      <svg viewBox="0 -6 320 126" className="w-full" role="img" aria-label={`Daily rain forecast: ${rows.map((r) => `${r.date} ${r.rain_mm} mm`).join(", ")}`}>
        {rows.map((r, i) => {
          const h = ((r.rain_mm || 0) / max) * 52;
          const x = 20 + i * bw;
          return (
            <g key={r.date}>
              <rect x={x + 4} y={78 - h} width={bw - 8} height={Math.max(h, 1)} fill="#3b7fb0" rx="2" />
              <text x={x + bw / 2} y={74 - h} textAnchor="middle" fontSize="8" fill="currentColor">{r.rain_mm}</text>
              <text x={x + bw / 2} y="92" textAnchor="middle" fontSize="7.5" fill="currentColor">{r.date.slice(5)}</text>
              {r.tmax_c != null && <text x={x + bw / 2} y="106" textAnchor="middle" fontSize="7.5" fill="currentColor" opacity="0.7">{Math.round(r.tmax_c)}°</text>}
            </g>
          );
        })}
        <text x="20" y="9" fontSize="8" fill="currentColor" opacity="0.7">rain (mm) per day · max temperature below</text>
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">7-day forecast for this parcel (Open-Meteo or the stored demo weather file). A forecast can change.</figcaption>
    </figure>
  );
}

/** Nutrient-deficiency symptoms as the TNAU Crop Production Guide (Agriculture 2020) describes them for maize, p.119. Shortened from that passage; nothing added. */
export function NutrientTable() {
  const rows: [string, string][] = [
    ["Nitrogen", "Leaves turn yellow; older leaves dry at the tips, along the mid-vein; stalks slender"],
    ["Phosphorus", "Leaves purplish green early on; spindly growth; slow maturity; irregular ears"],
    ["Potassium", "Yellow or yellowish-green streaks; leaves corrugated; tip and margin scorch; weak stalks"],
    ["Magnesium", "Older leaves turn pale at the margins and between veins; streaked leaves; spots"],
    ["Zinc", "Older leaves with yellow streaks or striping between veins; young leaves may be white or yellow"],
    ["Iron", "Yellowing between the veins; the whole crop may look bleached"],
  ];
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-border" data-testid="nutrient-table">
      <p className="bg-muted/40 px-3 py-1.5 text-xs font-semibold">Nutrient deficiency symptoms on leaves</p>
      <table className="w-full text-xs">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-t border-border/60 align-top">
              <th className="w-24 px-3 py-1.5 text-left font-semibold">{k}</th>
              <td className="px-2 py-1.5">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-1 text-[10.5px] text-muted-foreground">As described for maize in the TNAU Crop Production Guide: Agriculture 2020, p.119. Symptoms on other crops can differ; a soil or leaf test confirms the cause.</p>
    </div>
  );
}

export function PlantParts() {
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Parts of a plant">
      <svg viewBox="0 0 320 150" className="w-full" role="img" aria-label="A plant with flower, leaf, stem and roots labelled">
        <line x1="160" y1="60" x2="160" y2="105" stroke="#4aa86a" strokeWidth="5" />
        <ellipse cx="135" cy="80" rx="22" ry="9" fill="#4aa86a" transform="rotate(-25 135 80)" />
        <ellipse cx="185" cy="72" rx="22" ry="9" fill="#4aa86a" transform="rotate(25 185 72)" />
        <circle cx="160" cy="48" r="11" fill="#e9b83a" /><circle cx="160" cy="48" r="4" fill="#c9722a" />
        <rect x="20" y="105" width="280" height="8" fill="#6b4a2e" />
        {[[160, 113, 140, 140], [160, 113, 160, 146], [160, 113, 182, 140], [150, 120, 120, 135], [170, 120, 200, 135]].map(([x1, y1, x2, y2], i) => <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#8a6a4a" strokeWidth="2" />)}
        {[["Flower", 175, 46, 225, 36], ["Leaf", 200, 70, 240, 66], ["Stem", 163, 95, 240, 96], ["Roots", 200, 135, 240, 134]].map(([t, x1, y1, x2, y2]) => (
          <g key={String(t)}><line x1={Number(x1)} y1={Number(y1)} x2={Number(x2) - 4} y2={Number(y2)} stroke="currentColor" strokeWidth="0.8" /><text x={Number(x2)} y={Number(y2) + 3} fontSize="10" fill="currentColor">{t}</text></g>
        ))}
        <text x="24" y="100" fontSize="8" fill="currentColor" opacity="0.7">soil level</text>
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Main parts of a flowering plant (illustration): roots take up water and nutrients, the stem carries them, leaves make food from sunlight, the flower makes seed and fruit.</figcaption>
    </figure>
  );
}

export function InsectCycle() {
  const st = [["Egg", "#e9d9a0"], ["Larva (caterpillar)", "#8ab04a"], ["Pupa", "#8a6a4a"], ["Adult (moth)", "#b0a080"]];
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-2" aria-label="Insect life cycle">
      <svg viewBox="0 0 320 90" className="w-full" role="img" aria-label="Life cycle: egg, larva, pupa, adult, and back to egg">
        {st.map(([t, c], i) => (
          <g key={t}>
            <circle cx={40 + i * 80} cy="38" r="22" fill={c} />
            <text x={40 + i * 80} y="75" textAnchor="middle" fontSize="8.5" fill="currentColor">{t}</text>
            {i < 3 && <path d={`M${64 + i * 80} 38 h30 m-6 -5 l6 5 l-6 5`} stroke="currentColor" strokeWidth="1.5" fill="none" />}
          </g>
        ))}
        <path d="M260 20 q20 -22 -200 -18" stroke="currentColor" strokeWidth="1" fill="none" strokeDasharray="3 3" opacity="0.6" />
      </svg>
      <figcaption className="text-[10.5px] text-muted-foreground">Generic moth or beetle life cycle (illustration). Timing differs by pest and weather. The damaging stage is usually the larva.</figcaption>
    </figure>
  );
}

/** The numbered steps of a how-to answer as a left-to-right (wrapping) flow. The wording is the answer's own; steps are only shortened. */
export function ProcessFlow({ steps }: { steps: string[] }) {
  return (
    <div className="mt-3 rounded-lg bg-muted/30 p-2" data-testid="process-flow" aria-label="Process flow of the steps">
      <p className="mb-1 text-xs font-semibold">The steps at a glance</p>
      <ol className="flex flex-wrap items-center gap-1.5 text-[11px]">
        {steps.map((s, i) => (
          <li key={i} className="flex items-center gap-1.5">
            <span className="rounded-full border border-border bg-card px-2.5 py-1"><b className="mr-1 text-primary">{i + 1}</b>{s}</span>
            {i < steps.length - 1 && <span aria-hidden="true" className="text-muted-foreground">→</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

function shortStep(t: string): string {
  const x = t.replace(/\*\*/g, "").replace(/\(.*?\)/g, "").replace(/^[\d.\s-]+/, "").split(/(?<!\d)[.;:](?!\d)| and then | then /)[0].trim();
  const w = x.split(/\s+/);
  return w.length > 7 ? w.slice(0, 7).join(" ") + "…" : x;
}

type SatData = { evidence: any; zones: any };

/** Real Sentinel-2 values for the parcel from the existing /api/field-health endpoint: latest scene vs monthly composite vs recent baseline, and the 3x3 zone grid. No value is made up;
 * if the data are not available nothing is shown. */
export function SatellitePanel({ parcelId }: { parcelId: string }) {
  const [d, setD] = useState<SatData | null>(null);
  useEffect(() => {
    let live = true;
    const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
    fetch(`${base}/api/field-health/${encodeURIComponent(parcelId)}`).then((r) => (r.ok ? r.json() : null)).then((j) => live && setD(j)).catch(() => undefined);
    return () => { live = false; };
  }, [parcelId]);
  const ev = d?.evidence;
  const sc = ev?.latest_scene;
  if (!ev || !sc || sc.indices?.ndvi == null) return null;
  const bars: [string, number | null | undefined, string][] = [
    [`Latest scene ${sc.date}`, sc.indices.ndvi, "#4aa86a"],
    [`Month ${ev.monthly_composite?.month ?? ""} (median of clear passes)`, ev.monthly_composite?.mean, "#3b9a8c"],
    ["Baseline (recent scenes)", ev.baseline?.ndvi, "#8a8a8a"],
  ];
  const cells: any[] = d?.zones?.available ? d.zones.cells ?? [] : [];
  const grid = ["north-west", "north", "north-east", "west", "centre", "east", "south-west", "south", "south-east"];
  const tone: Record<string, string> = { lower: "#d9534f", higher: "#4aa86a", typical: "#8a8a8a" };
  return (
    <figure className="mt-3 rounded-lg bg-muted/30 p-3" data-testid="satellite-panel" aria-label="Satellite field health">
      <p className="mb-2 text-xs font-semibold">Satellite field health (NDVI) · {parcelId}</p>
      <div className="flex flex-wrap gap-4">
        <div className="min-w-48 flex-1 space-y-1.5">
          {bars.map(([label, v, c]) => (v == null ? null : (
            <div key={label} className="text-[11px]">
              <div className="flex justify-between"><span>{label}</span><b className="font-mono">{v.toFixed(3)}</b></div>
              <div className="h-2 rounded bg-border/60"><div className="h-2 rounded" style={{ width: `${Math.max(2, Math.min(100, v * 100))}%`, background: c }} /></div>
            </div>
          )))}
          <p className="text-[10.5px] text-muted-foreground">Status: <b>{ev.status}</b> (change vs baseline {ev.change_vs_baseline}). Scene cloud {sc.scene_cloud_pct}%.</p>
        </div>
        {cells.length > 0 && (
          <div>
            <div className="grid grid-cols-3 gap-0.5" aria-label="Zones of the parcel, north at the top">
              {grid.map((n) => { const c = cells.find((x) => x.name === n); return (
                <div key={n} title={c ? `${n}: ${c.class} (${c.vs_parcel >= 0 ? "+" : ""}${c.vs_parcel} vs parcel mean)` : `${n}: not enough clear pixels`} className="size-9 rounded-sm text-center text-[8px] leading-9 text-white" style={{ background: c ? tone[c.class] ?? "#8a8a8a" : "transparent", border: c ? "none" : "1px dashed var(--border)" }}>{c ? (c.class === "typical" ? "" : c.class) : "–"}</div>
              ); })}
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground">Zones, north up</p>
          </div>
        )}
      </div>
      <figcaption className="mt-2 text-[10.5px] text-muted-foreground">Sentinel-2 satellite data. {d?.zones?.caution ?? "A lower zone is a place to inspect on foot, not a diagnosis."}</figcaption>
    </figure>
  );
}

type Plan = {
  diagram: "ph_scale" | "compost_bed" | "compost_heap" | "drip" | "spacing" | "growth_stages" | "npk" | "deficiency_table" | "plant_parts" | "insect_cycle" | null;
  photo: { id: string; url: string; label: string; credit: string; page?: string | null } | null;
  weather_chart: boolean;
  weather?: WeatherRow[] | null;
  video: boolean;
  video_query: string;
  photos?: { id: string; url: string; label: string; credit: string; page?: string | null }[];
  external?: { url: string; label: string; credit: string; page?: string | null; note: string } | null;
  videos?: { id: string; title: string; url: string; channel: string }[];
};

// one planner call per answer, kept for the session (re-rendering or scrolling never asks again)
const PLANS = new Map<string, Promise<Plan | null>>();

function fetchPlan(result: Phase7AdvisoryResult): Promise<Plan | null> {
  const key = `${result.query}|${(result.answer || "").slice(0, 80)}|${result.parcel_id || ""}`;
  const hit = PLANS.get(key);
  if (hit) return hit;
  const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
  const p = fetch(`${base}/api/media`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: result.query, answer: result.answer, crop: result.crop, parcel_id: result.parcel_id }),
  })
    .then((r) => (r.ok ? (r.json() as Promise<Plan>) : null))
    .catch(() => null);
  PLANS.set(key, p);
  return p;
}

export function AnswerMedia({ result }: { result: Phase7AdvisoryResult }) {
  const [bad, setBad] = useState<Record<string, boolean>>({});
  const [plan, setPlan] = useState<Plan | null>(null);
  useEffect(() => {
    let live = true;
    // not for fixed safety cards or "could not find" answers: nothing to illustrate
    if (!result.answer || result.confidence?.label === "I need more detail") return;
    void fetchPlan(result).then((p) => live && setPlan(p));
    return () => { live = false; };
  }, [result]);

  const q = result.query || "";
  const answer = result.answer || "";
  const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
  const photos = (result.reference_photos ?? []).filter((p) => !bad[p.url]);
  const hasGuideVideos = (result.fertilizer_guides ?? []).some((g: any) => (g.videos ?? []).length > 0);
  const kind = plan?.diagram ?? null;
  const verified = plan?.videos ?? [];
  const showVideo = !!plan?.video && !hasGuideVideos && verified.length === 0;       // a search link only when there is no verified video
  const havePhotos = photos.length > 0;                      // the disease reference photos already answer "what does it look like": no second set under them
  const weatherShown = !!(plan?.weather_chart && plan.weather && plan.weather.length > 1);
  const libPhotos = havePhotos || weatherShown ? [] : (plan?.photos ?? []).filter((p) => !bad[p.url]);       // a forecast chart needs no stock picture beside it
  const ext = !havePhotos && plan?.external && !bad[plan.external.url] ? plan.external : null;
  let ph: number | null = null;
  if (kind === "ph_scale") {
    const m = /ph\s*(?:of|is|=|:)?\s*(\d{1,2}(?:\.\d+)?)/i.exec(`${q} ${answer}`);
    const v = m ? Number(m[1]) : null;
    ph = v != null && v >= 3 && v <= 11 ? v : null;
  }
  const sp = kind === "spacing" ? /(\d+)\s*(?:x|×)\s*(\d+)\s*cm/i.exec(answer + " " + (result.recommendations ?? []).join(" ")) : null;
  const stock = !havePhotos && !(plan?.photos ?? []).length && plan?.photo && !bad[plan.photo.url] ? plan.photo : null;
  const weather = plan?.weather_chart && plan.weather && plan.weather.length > 1 ? plan.weather : null;
  const raw = (result.recommendations ?? []).length >= 3 ? result.recommendations ?? [] : answer.split(/\n+/).filter((l) => /^\s*\d+[.)]\s+/.test(l));
  const flowSteps = /how to|how do i|steps|procedure|process of|prepare|make |setup|set up/i.test(q) && raw.length >= 3 ? raw.slice(0, 7).map(shortStep).filter(Boolean) : null;
  const satellite = !!result.parcel_id && /ndvi|satellite|field health|vegetation|stress|zone|sentinel/i.test(q);
  const docRows = result.doc_values && result.doc_values.length > 1 ? result.doc_values : null;
  if (!photos.length && !kind && !showVideo && !stock && !weather && !docRows && !libPhotos.length && !ext && !verified.length && !flowSteps && !satellite) return null;
  const short = (plan?.video_query || q).replace(/[?.!]/g, "").trim().toLowerCase();
  return (
    <div className="mt-2" data-testid="answer-media">
      {photos.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold">What it looks like · {photos[0]?.condition}</p>
          <div className="flex gap-2 overflow-x-auto">
            {photos.map((p) => (
              <a key={p.url} href={`${base}${p.url}`} target="_blank" rel="noreferrer" title="Open the photo" className="shrink-0">
                <img src={`${base}${p.url}`} alt={p.label} loading="lazy" onError={() => setBad((b) => ({ ...b, [p.url]: true }))} className="size-24 rounded-lg border border-border object-cover" />
              </a>
            ))}
          </div>
          <p className="mt-1 text-[10.5px] text-muted-foreground">Reference photos from public datasets ({photos[0]?.source}), not your field. Compare the symptoms; this is not a diagnosis.</p>
        </div>
      )}
      {docRows && <DocValues rows={docRows} />}
      {kind === "ph_scale" && <PhScale value={ph} />}
      {kind === "compost_bed" && <CompostBed />}
      {kind === "compost_heap" && <CompostHeap />}
      {kind === "drip" && <DripDiagram />}
      {kind === "spacing" && <SpacingDiagram rows={sp ? Number(sp[1]) : null} plants={sp ? Number(sp[2]) : null} />}
      {kind === "growth_stages" && <GrowthStages />}
      {kind === "npk" && <NpkDiagram />}
      {kind === "deficiency_table" && <NutrientTable />}
      {kind === "plant_parts" && <PlantParts />}
      {kind === "insect_cycle" && <InsectCycle />}
      {flowSteps && <ProcessFlow steps={flowSteps} />}
      {satellite && result.parcel_id && <SatellitePanel parcelId={result.parcel_id} />}
      {weather && <WeatherChart rows={weather} />}
      {libPhotos.length > 0 && (
        <div className="mt-3">
          <div className="flex gap-2 overflow-x-auto">
            {libPhotos.map((p) => (
              <figure key={p.id} className="shrink-0">
                <a href={`${base}${p.url}`} target="_blank" rel="noreferrer" title="Open the photo">
                  <img src={`${base}${p.url}`} alt={p.label} loading="lazy" onError={() => setBad((b) => ({ ...b, [p.url]: true }))} className="h-28 w-36 rounded-lg border border-border object-cover" />
                </a>
                <figcaption className="mt-1 max-w-36 text-[10px] leading-tight text-muted-foreground">{p.label}. {p.credit}</figcaption>
              </figure>
            ))}
          </div>
          <p className="mt-1 text-[10.5px] text-muted-foreground">Example photos, not your field and not a diagnosis.</p>
        </div>
      )}
      {ext && (
        <figure className="mt-3">
          <a href={`${base}${ext.url}`} target="_blank" rel="noreferrer" title="Open the photo">
            <img src={`${base}${ext.url}`} alt={ext.label} loading="lazy" onError={() => setBad((b) => ({ ...b, [ext.url]: true }))} className="h-28 w-auto max-w-full rounded-lg border border-border object-cover" />
          </a>
          <figcaption className="mt-1 text-[10.5px] text-muted-foreground">{ext.label}. {ext.credit}. {ext.note} Example photo, not your field.</figcaption>
        </figure>
      )}
      {verified.length > 0 && (
        <div className="mt-2 flex flex-col items-start gap-1.5 text-xs">
          {verified.map((v) => (
            <a key={v.id} href={v.url} target="_blank" rel="noreferrer" title={`${v.title} (${v.channel})`}
               className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border px-3 py-1 hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
              <span>▶</span><span className="truncate">{v.title}</span><span className="shrink-0 text-muted-foreground">· {v.channel}</span>
            </a>
          ))}
        </div>
      )}
      {stock && (
        <figure className="mt-3">
          <a href={`${base}${stock.url}`} target="_blank" rel="noreferrer" title="Open the photo">
            <img src={`${base}${stock.url}`} alt={stock.label} loading="lazy" onError={() => setBad((b) => ({ ...b, [stock.url]: true }))} className="h-28 w-auto max-w-full rounded-lg border border-border object-cover" />
          </a>
          <figcaption className="mt-1 text-[10.5px] text-muted-foreground">{stock.label} (an example photo, not your field). {stock.credit}.</figcaption>
        </figure>
      )}
      {showVideo && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <a
            href={`https://www.youtube.com/@tnautv2557/search?query=${encodeURIComponent(short.replace(/^(how to|how do i)\s+/, "").slice(0, 60))}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            ▶ Search TNAU TV for this <span className="text-muted-foreground">(official channel, opens a search)</span>
          </a>
          <a
            href={`https://www.youtube.com/results?search_query=${encodeURIComponent(`${short} TNAU`)}`}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground underline hover:text-foreground"
          >
            all of YouTube
          </a>
        </div>
      )}
    </div>
  );
}

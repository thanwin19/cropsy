/**
 * Regenerate public/data/then_malai/horizon_profiles.json from the DEM in public/data/then_malai/dem.
 * Run this after replacing the DEM (e.g. with scripts/build_dem_glo30.py output).
 *
 *   npx tsx scripts/regenerate-horizons.ts            # dry run: prints agreement vs existing file
 *   npx tsx scripts/regenerate-horizons.ts --write    # overwrite (backup saved as .bak.json)
 *   npx tsx scripts/regenerate-horizons.ts --write --date=2026-12-21
 */
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { resolve } from "node:path";
import { buildDemSet, computeHorizonAngles, sampleElevation } from "../src/lib/terrainShadow";
import { computeParcelSunSummary } from "../src/lib/solarGeometry";
import { VILLAGE_PARCELS } from "../src/data/villageParcels.generated";

const DATA = resolve(import.meta.dirname, "../public/data/then_malai");
const write = process.argv.includes("--write");
const dateArg = process.argv.find((a) => a.startsWith("--date="))?.slice(7);

const meta = JSON.parse(readFileSync(`${DATA}/dem/dem_metadata.json`, "utf-8"));
const i16 = (f: string) => {
  const b = readFileSync(`${DATA}/dem/${f}`);
  return new Int16Array(b.buffer, b.byteOffset, b.byteLength / 2);
};
const dems = buildDemSet(i16("dem_display_30m.bin"), meta.display_grid, i16("dem_full_90m.bin"), meta.full_grid);

const file = JSON.parse(readFileSync(`${DATA}/horizon_profiles.json`, "utf-8"));
const evalDate = dateArg ?? file.evaluation_date;
const date = new Date(`${evalDate}T00:00:00Z`);

// Parcels that exist in the village dataset but not in the file yet get a fresh entry (profile computed from the DEM).
let added = 0;
for (const v of VILLAGE_PARCELS) {
  if (!file.parcels[v.id]) {
    file.parcels[v.id] = {
      id: v.id, name: v.name, survey_no: v.id, lat: v.lat, lon: v.lon, crop: v.crop,
      elevation_csv_m: v.elevM, profile: [], source: "computed_from_dem (no PVGIS comparison)",
    };
    added++;
  }
}
console.log(`village parcels: ${VILLAGE_PARCELS.length}, newly added to file: ${added}`);

let sumSq = 0, n = 0;
for (const [id, p] of Object.entries<any>(file.parcels)) {
  const prof = computeHorizonAngles(dems, p.lat, p.lon, 2);
  const old: Array<{ azimuth_deg: number; horizon_angle_deg: number }> = p.profile ?? [];
  let maxDiff = 0;
  prof.forEach((pt, i) => {
    const o = old[i]?.horizon_angle_deg;
    if (o !== undefined) { const d = pt.horizon_angle_deg - o; sumSq += d * d; n++; maxDiff = Math.max(maxDiff, Math.abs(d)); }
  });
  const max = prof.reduce((a, b) => (b.horizon_angle_deg > a.horizon_angle_deg ? b : a));
  const sum = computeParcelSunSummary(p.lat, p.lon, date, prof, 12 * 60);
  console.log(`${id}: max ${max.horizon_angle_deg}° @ ${max.azimuth_deg}° (was ${p.max_horizon_angle_deg}°), max |Δ| vs old profile ${maxDiff.toFixed(2)}°, direct sun ${sum.directSunHours} h (was ${p.direct_sun_hours})`);

  // Only (re)write parcels computed from the DEM; the original PVGIS-validated anchors stay untouched unless --all.
  if (write && (String(p.source ?? "").startsWith("computed_from_dem") || process.argv.includes("--all"))) {
    p.profile = prof;
    p.max_horizon_angle_deg = max.horizon_angle_deg;
    p.max_horizon_azimuth_deg = max.azimuth_deg;
    p.elevation_dem_m = Math.round(sampleElevation(dems, p.lat, p.lon).z * 10) / 10;
    p.date_evaluated = evalDate;
    p.direct_sun_windows = sum.windows.map((w) => ({ start: w.startStr, end: w.endStr, duration_hours: w.durationHours }));
    p.direct_sun_start = sum.directSunStartStr;
    p.direct_sun_end = sum.directSunEndStr;
    p.direct_sun_hours = sum.directSunHours;
    p.flat_horizon_daylight_hours = sum.flatDaylightHours;
    p.terrain_shade_loss_hours = sum.terrainShadeLossHours;
  }
}
console.log(`RMS difference vs existing profiles: ${Math.sqrt(sumSq / Math.max(n, 1)).toFixed(3)}°`);

if (write) {
  copyFileSync(`${DATA}/horizon_profiles.json`, `${DATA}/horizon_profiles.bak.json`);
  file.generated_at = new Date().toISOString();
  file.evaluation_date = evalDate;
  writeFileSync(`${DATA}/horizon_profiles.json`, JSON.stringify(file, null, 2));
  console.log("written (backup: horizon_profiles.bak.json)");
} else {
  console.log("dry run – pass --write to overwrite");
}

// @vitest-environment node
/**
 * Validation of the sun-position + terrain-shadow stack against independent references:
 *   - suncalc (independent solar position implementation)
 *   - PVGIS horizon values stored in horizon_profiles.json
 *   - internal consistency between the raster shadow engine and per-parcel horizon profiles
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";
const SunCalc = createRequire(import.meta.url)("suncalc") as any; // v3+: degrees, apparent altitude, az clockwise from N
import { calcPos, calcDay, lookupHorizonAngle, atmosphericRefractionDeg } from "../solarGeometry";
import {
  buildDemSet,
  computeShadowMask,
  computeHorizonAngles,
  sampleElevation,
  type DemGridMeta,
} from "../terrainShadow";

const DATA = resolve(__dirname, "../../../public/data/then_malai");
const meta = JSON.parse(readFileSync(`${DATA}/dem/dem_metadata.json`, "utf-8"));
const toI16 = (f: string) => {
  const b = readFileSync(`${DATA}/dem/${f}`);
  return new Int16Array(b.buffer, b.byteOffset, b.byteLength / 2);
};
const horizons = JSON.parse(readFileSync(`${DATA}/horizon_profiles.json`, "utf-8")).parcels;
const dems = buildDemSet(toI16("dem_display_30m.bin"), meta.display_grid, toI16("dem_full_90m.bin"), meta.full_grid);

const LAT = 8.91, LON = 77.32;
// IST minute -> real Date
const istDate = (y: number, m: number, d: number, istMin: number) =>
  new Date(Date.UTC(y, m - 1, d, 0, 0, 0) + (istMin - 330) * 60000);

describe("solar position vs suncalc", () => {
  const cases: Array<[number, number, number, number]> = [
    [2026, 3, 21, 9 * 60], [2026, 3, 21, 12 * 60], [2026, 6, 21, 15 * 60],
    [2026, 9, 28, 8 * 60], [2026, 9, 28, 17 * 60 + 30], [2026, 12, 21, 11 * 60],
  ];
  it.each(cases)("%i-%i-%i %i min IST", (y, mo, d, mins) => {
    const date = new Date(Date.UTC(y, mo - 1, d));
    const mine = calcPos(LAT, LON, date, mins);
    const ref = SunCalc.getPosition(istDate(y, mo, d, mins), LAT, LON);
    // compare apparent (refraction-corrected) altitude and azimuth
    expect(Math.abs(mine.alt - ref.altitude)).toBeLessThan(0.3);
    expect(Math.abs(mine.az - ref.azimuth)).toBeLessThan(0.6);
  });

  it("sunrise / sunset within 3 minutes of suncalc", () => {
    const date = new Date(Date.UTC(2026, 8, 28));
    const mine = calcDay(LAT, LON, date);
    const t = SunCalc.getTimes(istDate(2026, 9, 28, 12 * 60), LAT, LON);
    const toIstMin = (x: Date) => (x.getUTCHours() * 60 + x.getUTCMinutes() + 330) % 1440;
    expect(Math.abs(mine.rise - toIstMin(t.sunrise))).toBeLessThanOrEqual(3);
    expect(Math.abs(mine.set - toIstMin(t.sunset))).toBeLessThanOrEqual(3);
  });

  it("refraction is ~0.5 deg at horizon and negligible overhead", () => {
    expect(atmosphericRefractionDeg(0)).toBeGreaterThan(0.4);
    expect(atmosphericRefractionDeg(0)).toBeLessThan(0.65);
    expect(atmosphericRefractionDeg(45)).toBeLessThan(0.02);
  });
});

describe("terrain shadow engine (synthetic)", () => {
  const m: DemGridMeta = { rows: 101, cols: 101, lat_max: 9.0, lat_min: 8.9, lon_min: 77.0, lon_max: 77.1, d_lat: 0.001, d_lon: 0.001 };
  const flat = new Int16Array(101 * 101).fill(100);

  it("flat terrain casts no shadow", () => {
    const r = computeShadowMask(buildDemSet(flat, m), 20, 270, false);
    expect(r.shadowMask.reduce((a, b) => a + b, 0)).toBe(0);
  });

  it("a ridge to the west shades the land east of it at low sun, not at high sun", () => {
    const dem = flat.slice();
    for (let r = 0; r < 101; r++) for (let c = 10; c < 14; c++) dem[r * 101 + c] = 600; // N-S ridge
    const set = buildDemSet(dem, m);
    const low = computeShadowMask(set, 5, 270, false);   // sun in the west, low
    const high = computeShadowMask(set, 60, 270, false);
    const idx = (r: number, c: number) => r * 101 + c;
    expect(low.shadowMask[idx(50, 30)]).toBe(1);
    expect(low.shadowMask[idx(50, 5)]).toBe(0);           // west of ridge stays sunlit
    expect(high.shadowMask[idx(50, 30)]).toBe(0);
  });

  it("shadow length matches geometry: h / tan(alt)", () => {
    const dem = flat.slice();
    for (let r = 0; r < 101; r++) for (let c = 10; c < 12; c++) dem[r * 101 + c] = 400; // 300 m wall
    const res = computeShadowMask(buildDemSet(dem, m), 10, 270, false);
    let last = 0;
    for (let c = 12; c < 101; c++) if (res.shadowMask[50 * 101 + c]) last = c;
    const metres = (last - 11) * 0.001 * 111139 * Math.cos(8.95 * Math.PI / 180);
    const expected = 300 / Math.tan((10 * Math.PI) / 180); // ~1.7 km
    expect(Math.abs(metres - expected) / expected).toBeLessThan(0.1);
  });
});

describe("real Then Malai DEM", () => {
  it.each(["TM-01", "TM-02", "TM-03", "TM-04", "TM-05", "TM-06"])(
    "%s max horizon matches PVGIS reference within 3 deg",
    (id) => {
      const p = horizons[id];
      const prof = computeHorizonAngles(dems, p.lat, p.lon, 2.5);
      const max = Math.max(...prof.map((x) => x.horizon_angle_deg));
      expect(Math.abs(max - p.pvgis_comparison.pvgis_max_horizon_deg)).toBeLessThan(3);
    },
  );

  it("raster shadow mask agrees with the horizon-profile test at the parcels", () => {
    // compute one fine mask per sun position, then compare the pixel at the parcel
    const dm = meta.display_grid as DemGridMeta;
    let agree = 0, total = 0;
    const p = horizons["TM-01"];
    const prof = computeHorizonAngles(dems, p.lat, p.lon, 1);
    const r = Math.round((dm.lat_max - p.lat) / dm.d_lat);
    const c = Math.round((p.lon - dm.lon_min) / dm.d_lon);
    for (const [alt, az] of [[5, 240], [8, 235], [12, 226], [14, 226], [20, 230], [10, 250], [6, 270], [4, 280]]) {
      const mask = computeShadowMask(dems, alt, az, true);
      const w = mask.outWidth;
      const shaded = mask.shadowMask[Math.floor(r / 2) * w + Math.floor(c / 2)] === 1;
      const hz = lookupHorizonAngle(prof, az);
      const expectShaded = alt <= hz;
      // allow a +-1 deg band near the horizon edge (grid + coarse-pass tolerance)
      if (Math.abs(alt - hz) > 1) { total++; if (shaded === expectShaded) agree++; }
    }
    expect(agree).toBe(total);
  });

  it("DEM elevation at parcels matches stored elevation within 5 m", () => {
    for (const id of ["TM-01", "TM-03", "TM-06"]) {
      const p = horizons[id];
      const z = sampleElevation(dems, p.lat, p.lon).z;
      expect(Math.abs(z - p.elevation_dem_m)).toBeLessThan(5);
    }
  });
});

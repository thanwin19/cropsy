/**
 * terrainShadow.ts
 *
 * Pure (DOM-free) terrain shadow engine shared by the Web Worker and tests.
 *
 * Improvements over the previous worker-only version:
 *  - Bilinear elevation sampling (old code used nearest-neighbour -> blocky/stair-stepped edges)
 *  - Step size never exceeds the cell size of the grid being sampled, so thin ridges are not skipped
 *  - Early exit once the sun ray is above the highest terrain in the DEM (large speed-up at high sun)
 *  - Range limited only by the 90 m grid extent (not a hard 25 km cut-off), so long evening
 *    shadows from distant Western Ghats crests are captured at low sun angles
 *  - Horizon profile helper (for validation against horizon_profiles.json / PVGIS)
 */

export interface DemGridMeta {
  rows: number;
  cols: number;
  lat_max: number;
  lat_min: number;
  lon_min: number;
  lon_max: number;
  d_lat: number;
  d_lon: number;
}

export interface DemSet {
  disp: Int16Array;
  dispMeta: DemGridMeta;
  full?: Int16Array;
  fullMeta?: DemGridMeta;
  /** highest elevation in either grid (metres), computed once */
  maxElev: number;
}

export const D2R = Math.PI / 180;
/** 4/3 Earth radius: curvature + terrestrial refraction */
export const R_EFF = 6371000 * (4 / 3);
const NODATA = -9000;
const M_PER_DEG_LAT = 111139;

export function buildDemSet(
  disp: Int16Array,
  dispMeta: DemGridMeta,
  full?: Int16Array,
  fullMeta?: DemGridMeta,
): DemSet {
  let maxElev = -Infinity;
  for (let i = 0; i < disp.length; i++) if (disp[i] > maxElev) maxElev = disp[i];
  if (full) for (let i = 0; i < full.length; i++) if (full[i] > maxElev) maxElev = full[i];
  return { disp, dispMeta, full, fullMeta, maxElev };
}

/** Bilinear sample. Returns NaN when the point is outside the grid. */
export function sampleBilinear(
  dem: Int16Array,
  m: DemGridMeta,
  lat: number,
  lon: number,
): number {
  const fr = (m.lat_max - lat) / m.d_lat;
  const fc = (lon - m.lon_min) / m.d_lon;
  if (fr < 0 || fc < 0 || fr > m.rows - 1 || fc > m.cols - 1) return NaN;
  const r0 = Math.floor(fr);
  const c0 = Math.floor(fc);
  const r1 = Math.min(r0 + 1, m.rows - 1);
  const c1 = Math.min(c0 + 1, m.cols - 1);
  const tr = fr - r0;
  const tc = fc - c0;
  const a = dem[r0 * m.cols + c0];
  const b = dem[r0 * m.cols + c1];
  const c = dem[r1 * m.cols + c0];
  const d = dem[r1 * m.cols + c1];
  if (a < NODATA || b < NODATA || c < NODATA || d < NODATA) return NaN;
  return a * (1 - tr) * (1 - tc) + b * (1 - tr) * tc + c * tr * (1 - tc) + d * tr * tc;
}

/** Elevation at lat/lon preferring the fine grid, falling back to the coarse grid. */
export function sampleElevation(
  dems: DemSet,
  lat: number,
  lon: number,
): { z: number; fine: boolean; inside: boolean } {
  const z1 = sampleBilinear(dems.disp, dems.dispMeta, lat, lon);
  if (!Number.isNaN(z1)) return { z: z1, fine: true, inside: true };
  if (dems.full && dems.fullMeta) {
    const z2 = sampleBilinear(dems.full, dems.fullMeta, lat, lon);
    if (!Number.isNaN(z2)) return { z: z2, fine: false, inside: true };
  }
  return { z: NaN, fine: false, inside: false };
}

export interface ShadowResult {
  shadowMask: Uint8Array;
  outWidth: number;
  outHeight: number;
}

/**
 * Ray-march from each display-grid pixel toward the sun.
 * sunAlt/sunAz in degrees (az 0 = N, 90 = E). Pass the *apparent* (refracted) altitude.
 */
export function computeShadowMask(
  dems: DemSet,
  sunAlt: number,
  sunAz: number,
  coarse: boolean,
): ShadowResult {
  const { disp, dispMeta } = dems;
  const { rows, cols, lat_max, lon_min, d_lat, d_lon } = dispMeta;
  const step = coarse ? 2 : 1;
  const outWidth = Math.ceil(cols / step);
  const outHeight = Math.ceil(rows / step);
  const shadowMask = new Uint8Array(outWidth * outHeight);

  if (sunAlt <= 0) return { shadowMask, outWidth, outHeight };

  const sunTan = Math.tan(sunAlt * D2R);
  const azRad = sunAz * D2R;
  const dirNorth = Math.cos(azRad);
  const dirEast = Math.sin(azRad);
  const centreLat = (lat_max + dispMeta.lat_min) / 2;
  const m2lat = 1 / M_PER_DEG_LAT;
  const m2lon = 1 / (M_PER_DEG_LAT * Math.cos(centreLat * D2R));
  const MAX_RANGE = 80000;

  let outIdx = 0;
  for (let r = 0; r < rows; r += step) {
    const lat0 = lat_max - r * d_lat;
    for (let c = 0; c < cols; c += step) {
      const lon0 = lon_min + c * d_lon;
      const z0 = disp[r * cols + c];
      let shaded = false;
      let d = 30;
      let leftAllGrids = false;

      while (d <= MAX_RANGE) {
        const zCurv = (d * d) / (2 * R_EFF);
        // ray height above this pixel at distance d is d*sunTan; if even the tallest
        // terrain in the DEM can no longer reach it, this pixel is sunlit.
        if (dems.maxElev - z0 - zCurv < d * sunTan) break;

        const s = sampleElevation(dems, lat0 + d * dirNorth * m2lat, lon0 + d * dirEast * m2lon);
        if (!s.inside) {
          if (leftAllGrids) break;
          leftAllGrids = true;
        } else {
          leftAllGrids = false;
          const eff = s.z - z0 - zCurv;
          if (eff > 0 && eff / d > sunTan) {
            shaded = true;
            break;
          }
        }
        // never step further than one cell of the grid we are sampling
        d += s.fine ? 30 : 90;
      }
      shadowMask[outIdx++] = shaded ? 1 : 0;
    }
  }
  return { shadowMask, outWidth, outHeight };
}

/**
 * Horizon elevation angle (deg) for every azimuth from a point, using the same DEM + curvature model.
 * Used to validate the engine against horizon_profiles.json.
 */
export function computeHorizonAngles(
  dems: DemSet,
  lat: number,
  lon: number,
  azStepDeg = 2.5,
  observerHeightM = 0,
): Array<{ azimuth_deg: number; horizon_angle_deg: number }> {
  const z0e = sampleElevation(dems, lat, lon);
  const z0 = (Number.isNaN(z0e.z) ? 0 : z0e.z) + observerHeightM;
  const m2lat = 1 / M_PER_DEG_LAT;
  const m2lon = 1 / (M_PER_DEG_LAT * Math.cos(lat * D2R));
  const out: Array<{ azimuth_deg: number; horizon_angle_deg: number }> = [];
  for (let az = 0; az < 360; az += azStepDeg) {
    const dn = Math.cos(az * D2R);
    const de = Math.sin(az * D2R);
    let best = 0;
    let d = 30;
    let leftAllGrids = false;
    while (d <= 80000) {
      const s = sampleElevation(dems, lat + d * dn * m2lat, lon + d * de * m2lon);
      if (!s.inside) {
        if (leftAllGrids) break;
        leftAllGrids = true;
      } else {
        leftAllGrids = false;
        const eff = s.z - z0 - (d * d) / (2 * R_EFF);
        const ang = Math.atan2(eff, d) / D2R;
        if (ang > best) best = ang;
      }
      d += s.fine ? 30 : 90;
    }
    out.push({ azimuth_deg: az, horizon_angle_deg: Math.round(best * 100) / 100 });
  }
  return out;
}

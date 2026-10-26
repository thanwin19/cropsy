/**
 * solarGeometry.ts
 *
 * Deterministic NOAA solar position algorithm and terrain horizon calculations.
 * Shared between main thread, Web Worker, and tests.
 */

export const D2R = Math.PI / 180;
export const R2D = 180 / Math.PI;
export const R_EARTH_REFRACT = 6371000 * (4 / 3); // 4/3 Earth radius refraction model

export const jd = (d: Date) => d.getTime() / 86400000 + 2440587.5;
export const jc = (j: number) => (j - 2451545) / 36525;
export const gmls = (t: number) => (((280.46646 + t * (36000.76983 + t * 0.0003032)) % 360) + 360) % 360;
export const gmas = (t: number) => 357.52911 + t * (35999.05029 - 0.0001537 * t);
export const eeo = (t: number) => 0.016708634 - t * (0.000042037 + 1.267e-7 * t);

export const seoc = (t: number) => {
  const m = gmas(t) * D2R;
  return (
    Math.sin(m) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
    Math.sin(2 * m) * (0.019993 - 0.000101 * t) +
    Math.sin(3 * m) * 0.000289
  );
};

export const sal = (t: number) => {
  const o = gmls(t) + seoc(t);
  return o - 0.00569 - 0.00478 * Math.sin((125.04 - 1934.136 * t) * D2R);
};

export const moe = (t: number) => 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60;
export const oc = (t: number) => moe(t) + 0.00256 * Math.cos((125.04 - 1934.136 * t) * D2R);
export const decl = (t: number) => R2D * Math.asin(Math.sin(oc(t) * D2R) * Math.sin(sal(t) * D2R));

export const eot = (t: number) => {
  const e = oc(t) * D2R,
    l = gmls(t) * D2R,
    m = gmas(t) * D2R,
    x = eeo(t),
    y = Math.tan(e / 2) ** 2;
  return (
    R2D *
    4 *
    (y * Math.sin(2 * l) -
      2 * x * Math.sin(m) +
      4 * x * y * Math.sin(m) * Math.cos(2 * l) -
      0.5 * y * y * Math.sin(4 * l) -
      1.25 * x * x * Math.sin(2 * m))
  );
};

export const clampAcos = (v: number) => Math.acos(Math.max(-1, Math.min(1, v)));
export const toIST = (u: number) => ((u + 330) % 1440 + 1440) % 1440;

export interface SolarDay {
  dawn: number;
  rise: number;
  noon: number;
  set: number;
  dusk: number;
  ghStart: number;
  ghEnd: number;
  dayMin: number;
}

export function calcDay(lat: number, lon: number, date: Date): SolarDay {
  const d = new Date(date);
  d.setUTCHours(6, 0, 0, 0);
  const t = jc(jd(d)),
    eq = eot(t),
    dc = decl(t),
    nu = 720 - 4 * lon - eq;
  const HA90 = R2D * clampAcos(Math.cos(90.833 * D2R) / (Math.cos(lat * D2R) * Math.cos(dc * D2R)) - Math.tan(lat * D2R) * Math.tan(dc * D2R));
  const HA96 = R2D * clampAcos(Math.cos(96 * D2R) / (Math.cos(lat * D2R) * Math.cos(dc * D2R)) - Math.tan(lat * D2R) * Math.tan(dc * D2R));
  const HA84 = R2D * clampAcos(Math.cos(84 * D2R) / (Math.cos(lat * D2R) * Math.cos(dc * D2R)) - Math.tan(lat * D2R) * Math.tan(dc * D2R));
  return {
    dawn: toIST(nu - 4 * HA96),
    rise: toIST(nu - 4 * HA90),
    noon: toIST(nu),
    set: toIST(nu + 4 * HA90),
    dusk: toIST(nu + 4 * HA96),
    ghStart: toIST(nu - 4 * HA84),
    ghEnd: toIST(nu + 4 * HA84),
    dayMin: 8 * HA90,
  };
}

export function getCompassDirection(azDeg: number): string {
  const directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const idx = Math.round((((azDeg % 360) + 360) % 360) / 22.5) % 16;
  return directions[idx];
}

/**
 * Atmospheric refraction (degrees) for a geometric solar altitude (Saemundsson formula),
 * scaled for local temperature/pressure. Defaults suit Then Malai (~170 m, tropical).
 * Adds ~0.5 deg at the horizon, <0.05 deg above 15 deg.
 */
export function atmosphericRefractionDeg(altGeomDeg: number, tempC = 28, pressureHPa = 990): number {
  if (altGeomDeg < -1) return 0;
  const h = Math.max(altGeomDeg, -0.5);
  const rArcMin = 1.02 / Math.tan((h + 10.3 / (h + 5.11)) * D2R);
  const scale = (pressureHPa / 1010) * (283 / (273 + tempC));
  return Math.max(0, (rArcMin * scale) / 60);
}

export interface SolarPos {
  /** apparent (refraction-corrected) altitude, degrees. Use this for terrain shading. */
  alt: number;
  /** geometric altitude without refraction, degrees */
  altGeometric: number;
  az: number;
  shadowX: number | null;
  compass: string;
}

export function calcPos(lat: number, lon: number, date: Date, istMin: number): SolarPos {
  const u = istMin - 330,
    d = new Date(date);
  d.setUTCHours(0, 0, 0, 0);
  const t = jc(jd(d) + u / 60 / 24),
    eq = eot(t),
    dc = decl(t);
  const tst = ((u + eq + 4 * lon) % 1440 + 1440) % 1440;
  let ha = tst / 4 - 180;
  if (ha < -180) ha += 360;
  const lr = lat * D2R,
    dr = dc * D2R,
    hr = ha * D2R;
  const cosZ = Math.sin(lr) * Math.sin(dr) + Math.cos(lr) * Math.cos(dr) * Math.cos(hr);
  const zen = R2D * Math.acos(Math.max(-1, Math.min(1, cosZ))),
    alt = 90 - zen;
  const sinZ = Math.sin(zen * D2R);
  let az = 180;
  if (Math.abs(sinZ) > 1e-6) {
    const c = (Math.sin(dr) - Math.sin(lr) * Math.cos(zen * D2R)) / (Math.cos(lr) * sinZ);
    az = R2D * clampAcos(c);
    if (ha > 0) az = 360 - az;
  }
  const altApp = alt + atmosphericRefractionDeg(alt);
  return {
    alt: Math.round(altApp * 100) / 100,
    altGeometric: Math.round(alt * 100) / 100,
    az: Math.round(az * 100) / 100,
    shadowX: altApp > 0.5 ? Math.round(100 / Math.tan(altApp * D2R)) / 100 : null,
    compass: getCompassDirection(az),
  };
}

export interface HorizonPoint {
  azimuth_deg: number;
  horizon_angle_deg: number;
}

export function lookupHorizonAngle(profile: HorizonPoint[], azDeg: number): number {
  const n = profile.length;
  if (n === 0) return 0;
  for (let i = 0; i < n; i++) {
    const a1 = profile[i].azimuth_deg;
    const a2 = profile[(i + 1) % n].azimuth_deg;
    if ((a1 <= azDeg && azDeg < a2) || (a2 < a1 && (azDeg >= a1 || azDeg < a2))) {
      const span = (a2 - a1 + 360) % 360 || 1;
      const frac = ((azDeg - a1 + 360) % 360) / span;
      return profile[i].horizon_angle_deg * (1 - frac) + profile[(i + 1) % n].horizon_angle_deg * frac;
    }
  }
  return profile[0].horizon_angle_deg;
}

export interface DirectSunWindow {
  startMin: number;
  endMin: number;
  startStr: string;
  endStr: string;
  durationHours: number;
}

export interface ShadedInterval {
  startMin: number;
  endMin: number;
  startStr: string;
  endStr: string;
}

export function computeTerrainShadedIntervals(
  lat: number,
  lon: number,
  date: Date,
  profile: HorizonPoint[]
): ShadedInterval[] {
  const shadedMinutes: number[] = [];
  for (let m = 0; m < 1440; m++) {
    const pos = calcPos(lat, lon, date, m);
    if (pos.alt > 0) {
      const horizAng = lookupHorizonAngle(profile, pos.az);
      if (pos.alt <= horizAng) {
        shadedMinutes.push(m);
      }
    }
  }

  const rawIntervals: Array<[number, number]> = [];
  if (shadedMinutes.length > 0) {
    let sStart = shadedMinutes[0];
    let prevM = shadedMinutes[0];
    for (let i = 1; i < shadedMinutes.length; i++) {
      const m = shadedMinutes[i];
      if (m > prevM + 1) {
        rawIntervals.push([sStart, prevM]);
        sStart = m;
      }
      prevM = m;
    }
    rawIntervals.push([sStart, prevM]);
  }

  const fmt = (m: number) => {
    const h = Math.floor(m / 60) % 24;
    const mi = Math.floor(m % 60);
    return `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
  };

  return rawIntervals.map(([s, e]) => ({
    startMin: s,
    endMin: e,
    startStr: fmt(s),
    endStr: fmt(e),
  }));
}

export interface ParcelTerrainSunSummary {
  directSunStartStr: string;
  directSunEndStr: string;
  directSunHours: number;
  flatDaylightHours: number;
  terrainShadeLossHours: number;
  windows: DirectSunWindow[];
  shadedIntervals: ShadedInterval[];
  maxHorizonAngleDeg: number;
  maxHorizonAzimuthDeg: number;
  isCurrentlyShaded: boolean; // at current istMin
}

export function computeParcelSunSummary(
  lat: number,
  lon: number,
  date: Date,
  profile: HorizonPoint[],
  currentIstMin: number
): ParcelTerrainSunSummary {
  const sunlitMinutes: number[] = [];
  const flatMinutes: number[] = [];

  for (let m = 0; m < 1440; m++) {
    const pos = calcPos(lat, lon, date, m);
    if (pos.alt > 0) {
      flatMinutes.push(m);
      const horizAng = lookupHorizonAngle(profile, pos.az);
      if (pos.alt > horizAng) {
        sunlitMinutes.push(m);
      }
    }
  }

  const flatHours = flatMinutes.length / 60;
  const directHours = sunlitMinutes.length / 60;

  const rawWindows: Array<[number, number]> = [];
  if (sunlitMinutes.length > 0) {
    let wStart = sunlitMinutes[0];
    let prevM = sunlitMinutes[0];
    for (let i = 1; i < sunlitMinutes.length; i++) {
      const m = sunlitMinutes[i];
      if (m > prevM + 1) {
        rawWindows.push([wStart, prevM]);
        wStart = m;
      }
      prevM = m;
    }
    rawWindows.push([wStart, prevM]);
  }

  const fmt = (m: number) => {
    const h = Math.floor(m / 60) % 24;
    const mi = Math.floor(m % 60);
    return `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
  };

  const windows: DirectSunWindow[] = rawWindows.map(([s, e]) => ({
    startMin: s,
    endMin: e,
    startStr: fmt(s),
    endStr: fmt(e),
    durationHours: Math.round(((e - s + 1) / 60) * 100) / 100,
  }));

  const shadedIntervals = computeTerrainShadedIntervals(lat, lon, date, profile);

  let maxAngle = -999;
  let maxAz = 0;
  for (const pt of profile) {
    if (pt.horizon_angle_deg > maxAngle) {
      maxAngle = pt.horizon_angle_deg;
      maxAz = pt.azimuth_deg;
    }
  }

  // Current status
  const curPos = calcPos(lat, lon, date, currentIstMin);
  let isCurrentlyShaded = false;
  if (curPos.alt > 0) {
    const hAngle = lookupHorizonAngle(profile, curPos.az);
    isCurrentlyShaded = curPos.alt <= hAngle;
  }

  return {
    directSunStartStr: sunlitMinutes.length > 0 ? fmt(sunlitMinutes[0]) : "N/A",
    directSunEndStr: sunlitMinutes.length > 0 ? fmt(sunlitMinutes[sunlitMinutes.length - 1]) : "N/A",
    directSunHours: Math.round(directHours * 100) / 100,
    flatDaylightHours: Math.round(flatHours * 100) / 100,
    terrainShadeLossHours: Math.round((flatHours - directHours) * 100) / 100,
    windows,
    shadedIntervals,
    maxHorizonAngleDeg: Math.round(maxAngle * 100) / 100,
    maxHorizonAzimuthDeg: Math.round(maxAz * 10) / 10,
    isCurrentlyShaded,
  };
}

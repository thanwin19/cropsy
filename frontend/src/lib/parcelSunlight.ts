/**
 * parcelSunlight.ts
 *
 * Per-parcel direct-sunlight hours (terrain-aware) for any date, plus a GeoJSON export that
 * can be dragged into GeoLibre / QGIS for further GIS analysis.
 */
import { calcPos, lookupHorizonAngle, type HorizonPoint } from "./solarGeometry";

export interface ParcelLike {
  id: string;
  lat: number;
  lon: number;
  crop: string;
  elevM: number;
  coords?: readonly (readonly [number, number])[];
}

export interface ParcelSunlight {
  id: string;
  crop: string;
  flatHours: number;
  directHours: number;
  lossHours: number;
  firstSun: string;
  lastSun: string;
  maxHorizonDeg: number;
}

const fmt = (m: number) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(Math.floor(m % 60)).padStart(2, "0")}`;

/** Direct sun hours using the apparent solar altitude vs the DEM horizon profile (5-min sampling). */
export function sunlightForParcel(
  p: ParcelLike,
  profile: HorizonPoint[] | undefined,
  date: Date,
  stepMin = 5,
): ParcelSunlight {
  let flat = 0, direct = 0, first = -1, last = -1;
  for (let m = 0; m < 1440; m += stepMin) {
    const pos = calcPos(p.lat, p.lon, date, m);
    if (pos.alt <= 0) continue;
    flat += stepMin;
    const hz = profile && profile.length ? lookupHorizonAngle(profile, pos.az) : 0;
    if (pos.alt > hz) {
      direct += stepMin;
      if (first < 0) first = m;
      last = m;
    }
  }
  const maxH = profile && profile.length ? Math.max(...profile.map((x) => x.horizon_angle_deg)) : 0;
  const r2 = (x: number) => Math.round((x / 60) * 100) / 100;
  return {
    id: p.id,
    crop: p.crop,
    flatHours: r2(flat),
    directHours: r2(direct),
    lossHours: r2(flat - direct),
    firstSun: first < 0 ? "N/A" : fmt(first),
    lastSun: last < 0 ? "N/A" : fmt(last + stepMin),
    maxHorizonDeg: Math.round(maxH * 10) / 10,
  };
}

export function sunlightForAllParcels(
  parcels: readonly ParcelLike[],
  horizonProfiles: Record<string, { profile?: HorizonPoint[] }>,
  date: Date,
): ParcelSunlight[] {
  return parcels.map((p) => sunlightForParcel(p, horizonProfiles[p.id]?.profile, date));
}

/** Parcel outline: real coords when present, otherwise the same ~80 m box the map draws. */
export function parcelRing(p: ParcelLike): [number, number][] {
  if (p.coords && p.coords.length) return p.coords.map((c) => [c[0], c[1]] as [number, number]);
  const dLat = 0.0004, dLon = 0.00048;
  return [
    [p.lat + dLat, p.lon - dLon],
    [p.lat + dLat, p.lon + dLon],
    [p.lat - dLat, p.lon + dLon],
    [p.lat - dLat, p.lon - dLon],
  ];
}

/** RFC 7946 GeoJSON (lon,lat order) with sunlight attributes - opens directly in GeoLibre/QGIS. */
export function buildParcelsGeoJSON(
  parcels: readonly ParcelLike[],
  results: ParcelSunlight[],
  dateLabel: string,
) {
  return {
    type: "FeatureCollection",
    name: "then_malai_parcels_sunlight",
    crs: { type: "name", properties: { name: "urn:ogc:def:crs:OGC:1.3:CRS84" } },
    features: parcels.map((p) => {
      const r = results.find((x) => x.id === p.id);
      const ring = parcelRing(p).map(([lat, lon]) => [lon, lat]);
      ring.push(ring[0]);
      return {
        type: "Feature",
        properties: {
          id: p.id,
          crop: p.crop,
          elevation_m: p.elevM,
          date: dateLabel,
          direct_sun_hours: r?.directHours,
          flat_horizon_hours: r?.flatHours,
          terrain_shade_loss_hours: r?.lossHours,
          first_direct_sun_ist: r?.firstSun,
          last_direct_sun_ist: r?.lastSun,
          max_horizon_angle_deg: r?.maxHorizonDeg,
        },
        geometry: { type: "Polygon", coordinates: [ring] },
      };
    }),
  };
}

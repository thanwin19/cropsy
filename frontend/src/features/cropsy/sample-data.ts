import type { ParcelStatus } from "./contracts";

export const parcelIds = Array.from({ length: 120 }, (_, index) => `TM-${String(index + 1).padStart(2, "0")}`);

export type SampleLayer = readonly [id: string, name: string, kind: string, description: string, unit: string, range: string];
export type SampleLayerGroup = { question: string; layers: readonly SampleLayer[] };

export const layerGroups: readonly SampleLayerGroup[] = [
  { question: "Is my crop healthy?", layers: [
    ["ndvi", "NDVI", "real satellite data", "Plant vigour from red and near-infrared light", "index", "0.18–0.84"],
    ["savi", "SAVI", "real satellite data", "Vegetation health with soil brightness correction", "index", "0.12–0.76"],
    ["evi", "EVI", "real satellite data", "Dense canopy health with atmospheric correction", "index", "0.10–0.71"],
    ["ndre", "NDRE", "real satellite data", "Chlorophyll stress in mature crops", "index", "0.08–0.62"],
  ]},
  { question: "Is it wet or dry?", layers: [
    ["ndmi", "NDMI", "real satellite data", "Moisture held in crop canopy", "index", "−0.30–0.68"],
    ["ndwi", "NDWI", "real satellite data", "Open water and surface wetness", "index", "−0.42–0.74"],
    ["rsm", "Relative soil moisture", "real satellite data", "Radar estimate through light cloud", "%", "12–82%"],
    ["rvi", "RVI (radar)", "real satellite data", "Radar vegetation structure", "index", "0.18–0.91"],
  ]},
  { question: "How much water does it use?", layers: [
    ["et", "Evapotranspiration", "modelled", "Estimated crop water use", "mm/day", "1.2–6.8 mm/day"],
  ]},
  { question: "What is the land like?", layers: [
    ["soc", "Soil organic carbon", "dummy", "Long-term soil carbon estimate", "%", "0.3–1.9%"],
    ["dem", "Elevation", "real satellite data", "Terrain height above sea level", "m", "117–193 m"],
    ["landcover", "Land cover", "real satellite data", "Crop, trees, water and built areas", "class", "8 classes"],
  ]},
  { question: "Is anything changing?", layers: [
    ["true", "True colour", "real satellite data", "Natural-colour satellite view", "reflectance", "0–100%"],
    ["enhanced", "Enhanced true colour", "real satellite data", "Contrast-enhanced natural view", "reflectance", "0–100%"],
    ["hybrid", "Hybrid NDVI", "real satellite data", "True colour with crop-health overlay", "index", "0.18–0.84"],
    ["cb-ndvi", "Colour-blind NDVI", "real satellite data", "Accessible crop-health palette", "index", "0.18–0.84"],
  ]},
];

export const alerts = [
  { parcel: "TM-07", severity: "stress" as ParcelStatus, note: "NDMI decline detected", date: "03 Oct 2026" },
  { parcel: "TM-38", severity: "watch" as ParcelStatus, note: "Leaf colour change", date: "03 Oct 2026" },
  { parcel: "TM-91", severity: "watch" as ParcelStatus, note: "Irrigation delay risk", date: "02 Oct 2026" },
];

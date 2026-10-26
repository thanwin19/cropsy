# Satellite layers, index results and field report

Everything here is built offline with free, key-less data, then served by the API. Nothing needs an account.

## Rebuild order
```bash
python backend/scripts/build_satellite.py --as-of 2026-10-03   # per-parcel indices + compass sectors (Sentinel-2)  ~4 min
python backend/scripts/build_layers.py                          # 16 map layers: static + Sentinel-2 + Sentinel-1       ~10 min
python backend/scripts/build_calendar.py                        # satellite-pass calendar
```
Outputs: `data/satellite/` (observations, summary, calendar) and `data/layers/` (PNGs + `layers.json`, `parcel_geo.json`).

## Sources
| Layer | Source | Kind |
|---|---|---|
| NDVI, EVI, SAVI, NDRE, NDWI, NDMI, TCI | Sentinel-2 L2A (AWS Open Data, Earth Search STAC) | real |
| RVI, RSM | Sentinel-1 RTC (Microsoft Planetary Computer, anonymous) | real; RSM is a relative change-detection index |
| LULC | ESA WorldCover 10 m, 2021 | real |
| SOC | ISRIC SoilGrids 2.0, 250 m | real (global model) |
| DEM | Copernicus GLO-30 | real |
| ET | NDVI-based crop coefficient (Kcb = 1.44 NDVI - 0.1) x Open-Meteo ET0 | modelled |
| ETCI, Hybrid, Colour-blind | our display definitions | derived |

## Lessons and checks (read before changing the maths)
* **Reflectance offset: detect it, never trust the metadata.** ESA adds +1000 to the pixel values of newer scenes, and Earth Search's
  `raster:bands offset` / `earthsearch:boa_offset_applied` fields turned out to be unreliable (scenes flagged either way held offset-free
  values). Applying a -0.1 offset to offset-free data makes blue/green/red negative and every index wrong (NDVI median 0.90-0.99,
  NDWI -1.0; this showed up as a broken February 2025). `build_satellite.scene_offset()` therefore decides per scene from its own dark
  pixels: if the 5th percentile of the red band is below DN 900, the offset is not in the data. Check any new month's median NDVI
  (about 0.4 to 0.7 here); 0.9+ means the scaling is wrong.
* **Do not mask dark pixels.** Dense canopy is very dark in red; discarding non-positive reflectance throws away the healthiest pixels.
  Reflectance is floored at 0 and only genuinely degenerate denominators are masked.
* **Independent check.** `layers.json -> sanity` compares the indices with WorldCover: open water has the highest NDWI and ~0 NDVI,
  tree cover the highest NDVI, built-up the lowest vegetation NDVI. A wrong formula or a misaligned grid fails this immediately.
* The build scripts assert every index mean is within -1..1.

## Honest limits
* The crop names, stages and issues are dummy; the satellite sees what really grows at the parcel's coordinates. Only 30% of the village
  window is cropland (WorldCover), so some "dummy crops" sit on grass or tree cover.
* A falling index is a signal to inspect the field, not a diagnosis.
* RSM and RVI respond to canopy structure and wetness, are noisy (speckle), and RSM is weaker under dense canopy.
* SoilGrids is 250 m: indicative only. ET is modelled from one weather point.
* ETCI: we could not verify what other products call ETCI, so ours is simply a contrast-stretched true-colour image.

## API
`/api/layers`, `/layers/<id>/<YYYY-MM|static>.png`, `/api/indices/{parcel}?start&end`, `/api/satellite`, `/api/field-report/{parcel}`,
`/api/alerts`, `/api/village-brief`.

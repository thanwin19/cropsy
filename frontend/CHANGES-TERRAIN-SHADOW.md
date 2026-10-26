# Terrain shadow upgrade – what changed

NEW   src/lib/terrainShadow.ts            shared engine: bilinear DEM sampling, early exit, 80 km range, horizon helper
EDIT  src/workers/terrainShadowWorker.ts  uses shared engine; DEM sent once ("init"), jobs are tiny messages
EDIT  src/lib/solarGeometry.ts            atmospheric refraction (apparent altitude in `alt`, raw in `altGeometric`)
EDIT  src/components/ThenMalaiMapView.tsx init-once DEM, "Relief Hillshade" layer (off by default), sunlight panel
NEW   src/lib/parcelSunlight.ts           per-parcel direct-sun hours + GeoJSON builder
NEW   src/components/ParcelSunlightPanel.tsx  "Sunlight hours" button: all parcels, 4 seasons, GeoJSON export, GeoLibre link
NEW   src/lib/__tests__/terrainValidation.test.ts  19 validation tests (suncalc, PVGIS horizons, synthetic geometry)
NEW   scripts/build_dem_glo30.py          rebuild DEM cache from raw Copernicus GLO-30 (run locally, needs internet)
NEW   scripts/regenerate-horizons.ts      rebuild horizon_profiles.json from the DEM (npm run horizons[:write])

Order after swapping the DEM:
  pip install rasterio numpy requests && python scripts/build_dem_glo30.py
  npm run horizons          # dry run, check agreement
  npm run horizons:write
  npm test

# Cropsy — front-end rebuild prompt (for Lovable / Figma Make / v0)

Paste everything below the line into the tool. Keep the "Data contract" section: it stops the tool from inventing fields.

---

## 1. What you are building

**Cropsy** is an agricultural advisory and intelligence web app for smallholder farmers and extension officers. Demo village: **Then Malai, Tenkasi, Tamil Nadu** (120 parcels, TM-01 to TM-120). A farmer asks a question (text, crop photo, or document); an AI pipeline answers with advice that cites its sources. The app also shows satellite crop-health maps, a daily field report, and a sun/shade view of the land.

Design it as a **calm, professional field tool**: dark theme, warm amber/orange accent, readable outdoors, mobile-first (farmers use phones) but excellent on a laptop. No marketing page, no login, **no top bar**.

Honesty rule for the UI: anything that is dummy data is labelled "dummy" or "sample"; satellite data is labelled "real satellite data". Never show a number without a unit and a date.

## 2. Layout

- **Left icon rail** (desktop) / **bottom tab bar** (mobile), four sections only:
  1. **Ask** (chat + map) — default
  2. **My field** (field report: Today / Latest advisory / History)
  3. **Satellite** (16 layers)
  4. **Trust** (Sources & evidence / Route trace)
  Plus small utilities at the bottom of the rail: Alerts (badge with count), Settings.
- Logo "Cropsy / Then Malai" top of the rail. No other header.
- Each section may have a slim **tab strip** at the top of the content (no big titles). A small **print icon** sits at the right end of the My-field strip.
- Cards use 12px radius, 1px hairline borders, glass/blur on map overlays. Type: Inter for UI, a monospace (DM Mono) for numbers, units and codes. Minimum tap target 40px.

## 3. Screens

### 3.1 Ask (home)
Desktop: map on the left (about 64%), chat on the right (36%). Mobile: chat first, map behind a "Map" toggle.

**Chat panel**
- Header: "Cropsy", status pill (Ready / Thinking), clear-chat button.
- Default mode is **general agricultural advice**; a muted line says "mention a parcel to get field advice".
- A parcel is attached **only** when the user clicks a parcel on the map or types an id (TM-xx). When attached, show a removable chip "TM-01 · Coconut ×".
- Suggested-question chips (Tamil/English mixed, e.g. "rice leaf yellow + rain tomorrow").
- Composer: text box, attach photo, attach document, send. Photo thumbnail preview with remove.
- Answer card: headline answer, numbered steps, a **confidence badge**, a **"Checked" strip** (verifier checks passed/repaired), expandable **Sources** (document + page), and "Limitations" when evidence is thin. A refusal state ("I don't have a verified source for that") must look intentional, not like an error.

**Map (Leaflet-style, satellite basemap)**
- 120 parcel polygons coloured by **Crop** or **Crop health** (toggle in the top-centre row next to the map-style switch Dark / Satellite / Street).
- Clicking a parcel selects it and attaches it to chat.
- Floating, **draggable** overlays (each remembers its position; none may hide another by default):
  - **Solar ephemeris** panel (top-left): parcel, date, sun altitude/azimuth, culmination, daylight, sunrise, sunset, golden hour, direct-sun window, DEM note. Collapsible.
  - **Shadow time** panel (top-right): shadow time, sun altitude, azimuth, terrain horizon, cloud effect, "Observed sunshine" line.
  - **Sunlight hours** button (top-centre): opens per-parcel table of direct-sun hours with GIS export.
  - **16 layers** icon chip (bottom-left): opens the satellite-layer picker and paints the chosen layer on this map (see 3.3). Shows the active layer name.
  - **Legend** chip (bottom-right), collapsed by default.
  - **Map layers** control (toggle cadastral, FMB, survey, ridge, sun arc).
  - **Time scrubber** (bottom): play, now, simulated time, 24-hour bar with sunrise/sunset.

### 3.2 My field
Tabs: **Today**, **Latest advisory**, **History**. One parcel selector at the top of this section.
- **Today**: crop, stage, area, health status chip (normal / watch / stress), early-stress alert if any, 7-day weather strip, irrigation advice in **mm with a pump window** (start–end, litres/sec), N-P-K plan **against target** with named products and an organic alternative, soil pH/salinity, yield forecast with range, pest/disease risk list each with **chemical and organic controls** (verbatim, with source page).
- **Latest advisory**: the most recent chat answer for this parcel, formatted as a printable advisory.
- **History**: 2021–2025 seasons, NDVI trend lines across two seasons, two-index comparison, date window picker, **CSV export**.
- Print: icon button, opens a clean one-page print layout.

### 3.3 Satellite (16 layers)
Left: **"What do you want to know?"** picker, grouped by question (Is my crop healthy? Is it wet or dry? How much water does it use? What is the land like? Is anything changing?). Each option is a radio row with a "real data / modelled / dummy" tag and a one-line explanation.
Right: map with the chosen layer, plus controls: month, **colormap** (incl. a colour-blind-safe palette), **opacity** slider, legend bar with range and unit, **two-date comparison** slider, **timelapse** play, bulk historical export, **KML export**, **coordinate lookup** (type lat/lon → value), **plant-count estimate** for a parcel.
The 16 layers: NDVI, SAVI, EVI, NDRE, NDMI, NDWI, ET (modelled), RVI (radar), RSM (relative soil moisture, radar), SOC, DEM, land cover, true colour, enhanced true colour, hybrid (true colour + NDVI), colour-blind NDVI.

### 3.4 Trust
- **Sources & evidence**: documents used, page numbers, similarity, photo matches.
- **Route trace**: step-by-step pipeline (router → retrieval → image match → model → verifier V1–V8 → repair) with timings and which model ran.

### 3.5 Alerts
Drawer from the rail: list of parcels with early-stress alerts, severity chip, "Ask about this" button that opens Ask with the parcel attached.

## 4. States every screen needs
Loading skeletons, backend-offline banner ("Start the backend"), empty states, error with retry, partial data ("No clear satellite view: cloud"), and an offline-friendly cached last answer.

## 5. Data contract (do not invent fields)
Base URL: same origin, proxied to the API.
- `POST /api/query` (multipart: question, optional parcel_id, optional image, optional document) → answer, steps[], confidence, checks[], sources[{doc,page}], limitations[], route, timings
- `GET /api/parcels` · `GET /api/parcels/{id}` · `GET /api/field-report/{id}` · `GET /api/alerts?min=high`
- `GET /api/layers` (manifest: bounds, layers{id,name,question,units,range,months,kind}) · `GET /layers/{layer}/{YYYY-MM|static}.png` (8-bit grey, decode client-side with a colour LUT)
- `GET /api/point?lat=&lon=` (values of all layers at a point) · indices export and KML endpoints under `/api/…/export`
Parcel status values: `normal | watch | stress | insufficient`.

## 6. Deliverables
React + TypeScript + Tailwind, component per section, a small design-token file (colour, radius, spacing, type), light and dark tokens (dark default), responsive at 375, 768, 1363 px. Keep the map component swappable (Leaflet).

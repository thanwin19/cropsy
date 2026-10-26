# Cropsy

**An AI farming assistant whose numbers you can trace to a source.**
Farmers ask in English, Tamil or Tanglish, by text, voice, photo or PDF. Cropsy answers from TNAU and ICAR guides, checks every figure against the source before showing it, and says "the guides do not have this" instead of guessing.

> Status: release candidate for expert review. Not production. See [Honest status](#honest-status).

## Why it exists

A normal chatbot sounds sure even when it is wrong, and a wrong pesticide dose can damage a crop or hurt a farmer. Cropsy is built so that:

- every number comes from a cited guide page, or from a calculator or data feed;
- a separate verifier rejects any figure that is not in the evidence;
- when there is no evidence, it gives a labelled general answer and asks one follow-up question, with no invented numbers;
- banned or restricted chemicals get a fixed safety card with no dose.

## What it does

| Capability | How |
|---|---|
| Answers from TNAU / ICAR guides | Titan embeddings search over guide passages, with page citations |
| English, Tamil, Tanglish | Understanding step plus rule overrides for crop and topic words |
| Photo of a leaf | Symptom caption, matched against 1,786 reference leaf photos; gives a *possible* issue, never a confirmed diagnosis |
| PDF / soil report | Textract, then answered from the document |
| Voice | Amazon Transcribe streaming (browser microphone path not yet verified) |
| Parcel fertilizer totals | Calculator: per-hectare dose x area (urea 46% N, DAP 18-46-0, MOP 60% K2O) |
| Satellite crop health | 16 map layers per parcel, with status, zones and alerts |
| Terrain shadow and sunlight | NOAA sun position + 30 m DEM horizon profile per parcel |
| Pictures with answers | Code-drawn diagrams, licensed photos, charts from real data, verified TNAU / ICAR videos |

## Architecture

```
Farmer (text | voice | photo | PDF)  ->  React frontend (Vite)  ->  FastAPI backend  ->  AWS Bedrock / Textract / Transcribe
```

### The answer pipeline

1. **Gate**: blocks abuse and empty input.
2. **Understand**: crop, topic, language, parcel id, follow-up (Nova Micro, with rule overrides).
3. **Photo check** (if a photo is sent): caption, then match against reference photos.
4. **Tools**: parcel record, weather (Open-Meteo), satellite indices, sunlight.
5. **Router**: rules choose the model. Easy questions go to Nova Micro; comparisons go to Nova Lite.
6. **Retrieve**: dense search (Titan text embeddings, 256-d) plus keyword scoring and a crop boost.
7. **Calculator**: parcel fertilizer totals; this answer is written from the calculator, not the model.
8. **Write**: Ministral 3B/8B or Nova writes from the evidence only.
9. **Verify (V1 to V14)**: figure must be in the source; right unit and basis; right purpose; each dose tied to its own product. First failure retries; second failure removes the figure.
10. **Confidence and citations**: source page, confidence, conflict notes, region check.
11. **Media** (separate call, so text appears first): diagram, photo, chart, map or video, chosen from a closed menu.

### Routes

| Case | Route |
|---|---|
| Easy question | Nova Micro |
| Compare / difference | Nova Lite |
| Parcel fertilizer | Calculator writes the answer |
| Banned or restricted chemical | Fixed safety card, no dose |
| No evidence in the guides | Labelled general answer, no invented figure |
| Photo or PDF | Photo check or Textract first, then the normal path |

### AI models (AWS Bedrock, `ap-south-1`)

| Model | Job |
|---|---|
| Amazon Nova Micro | understanding, easy answers, picking visuals |
| Amazon Nova Lite | comparison and complex questions |
| Mistral Ministral 3B / 8B | writes answers, including Tamil |
| Amazon Titan Text Embeddings v2 | guide search |
| Amazon Titan Multimodal Embeddings | leaf photo matching |
| Amazon Textract | reads PDFs and photos of reports |
| Amazon Transcribe (streaming) | voice to text |

## The 16 satellite and map layers

Built offline from free, key-less data by `backend/scripts/build_layers.py` and `build_satellite.py`.

| Group | Layers | Source |
|---|---|---|
| Crop health | NDVI, EVI, SAVI, NDRE | Sentinel-2 L2A |
| Water | NDWI, NDMI, ET | Sentinel-2; ET is modelled (NDVI crop coefficient x Open-Meteo ET0) |
| Soil | SOC | ISRIC SoilGrids 2.0 (250 m, indicative) |
| Terrain and land | DEM, LULC | Copernicus GLO-30; ESA WorldCover 10 m |
| Display | TCI, ETCI, Hybrid, Colour-blind NDVI | Sentinel-2 / our definitions |
| Radar | RVI, RSM | Sentinel-1 RTC |

**How they become an answer:** the layers are not fed to a trained prediction model. For each parcel the app takes the mean over every pixel inside the boundary, with its date and basis, and combines evidence by fixed, documented rules:

- NDVI change against baseline gives *stress* (-0.10 or lower), *watch* (-0.05 or lower) or *normal*;
- the parcel is cut into a 3 x 3 grid to show which part is lower than the rest;
- the NDVI status, the 7-day water balance (FAO-56), the 3-day rain total and the parcel record are fused into one instruction and a list of alerts;
- the answer model receives these numbers as evidence, and the verifier rejects any figure that is not in them.

Only NDVI drives status and alerts. The other layers appear in the parcel facts, the map and the explanations. A low index means "go and look", not a diagnosis. See `backend/SATELLITE.md`.

## Terrain shadow

A NOAA solar-position calculation plus a 30 m elevation model gives each parcel a horizon profile; sun below the horizon angle means shade. The map shows direct-sun hours per parcel for four dates and a cloud-forecast toggle (about 10 km weather model). Validation tests (`frontend/src/lib/__tests__/terrainValidation.test.ts`, 19 tests) compare against independent references: sun position within 0.3 degrees in height and 0.6 in direction (suncalc), sunrise and sunset within 3 minutes, hill angles within 3 degrees of PVGIS, shadow length within 10% of geometry, ground height within 5 m. Not yet compared with a light meter in a real field.

## Repository layout

```
backend/
  app/            FastAPI app, pipeline steps (app/steps), verifier, quantities, media, satellite and field reports
  knowledge/      Guide passages (chunks.jsonl) and sources
  scripts/        Build and ingest scripts (layers, satellite, image library, embeddings, video catalog)
  tests/          pytest suite, gold set, live runners
  expert_review/  Review packets for an agronomist and a Tamil-language expert (blank sign-off)
  presentation/   Judge briefing and architecture PDFs
  RELEASE_STATUS.md, STAGING_CHECKLIST.md, SATELLITE.md, reports
frontend/         React + Vite + TanStack app: chat, map, field, satellite, trust pages
design/           Dashboard sample and field test sheet
```

## Run it locally

Needs Python 3.11, Node 20+, and AWS access to Bedrock, Textract and Transcribe in `ap-south-1`.

```bash
# backend
cd backend
pip install -r requirements.txt
aws sso login --profile <your-profile>          # or set AWS_PROFILE; a deployed role also works
python -m uvicorn app.main:app --port 8000

# frontend
cd frontend
npm install
npm run dev                                      # http://localhost:5173, proxies /api to port 8000
```

**Data not in this repository.** To keep the repo small, `backend/data/images/` (licensed Wikimedia photos, pest and fertilizer photos, reference leaf photos) and `backend/data/layers/` (satellite layer PNGs) are not included. Rebuild the layers with `python scripts/build_layers.py` and `python scripts/build_satellite.py`; the photo library with `python scripts/build_image_library.py`. Without them the app runs, but pictures and map layers are missing.

Useful settings (environment variables): `AWS_PROFILE`, `AWS_REGION`, `CROPSY_CORS_ORIGINS`, `CROPSY_IMAGE_BUCKET`, `CROPSY_EXTERNAL_IMAGES`, `CROPSY_DOC_MAX_PAGES`.

## Tests

```bash
cd backend && python -m pytest -q           # 267 offline tests
python tests/run_gold_live.py               # 20-question live gold set (needs AWS login)
python tests/run_universal_live.py          # broader live set (needs AWS login)
cd frontend && npm test && npm run typecheck
```

Latest runs: offline suite 267 passed; gold set 20/20 on numbers, citations and behaviour in 4 of 4 runs; universal live set 67 of 68 (one intermittent Tanglish turmeric question, see `backend/RELEASE_STATUS.md`). The gold set's expected answers were read from the source by the team, not by an agronomist.

## Honest status

- **Not reviewed by experts yet.** Pesticide doses are checked against TNAU text, not current CIB&RC labels. The pesticide-status entries, the paraquat flag and three recommendation conflicts are marked unverified. Review packets are in `backend/expert_review/`.
- **Tamil terminology** needs review by a fluent Tamil-speaking agronomist (an earlier rice-blast answer used the stem-borer term).
- **Photo diagnosis is the least tested part.** Some leaf photos are misread (a rice-blast leaf was read as tungro), and the symptom-caption step can return placeholder wording.
- **Voice** is untested in the browser microphone path and cannot run on Lambda (needs a WebSocket).
- **Outside photos** are matched by title, not by what the picture shows. Comparison answers are sentences, not tables yet.
- **Demo data:** farmer names, crops, stages and management records are dummy. The satellite values and terrain are real.
- **AWS staging** is prepared (`backend/STAGING_CHECKLIST.md`, Lambda handler via Mangum) but not deployed; it waits on IAM permissions.

Production decision: hold until the agronomist and Tamil reviews are complete.

## Data sources and credits

TNAU and ICAR crop production guides (text and page citations); Sentinel-2 and Sentinel-1 (ESA, via AWS Open Data and Microsoft Planetary Computer); Copernicus GLO-30 DEM; ESA WorldCover; ISRIC SoilGrids; Open-Meteo weather; PVGIS horizon data (validation); licensed Wikimedia Commons photos with per-image credits; public leaf-disease datasets for reference photos. Built by Team 36.

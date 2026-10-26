# Build the Cropsy backend (paste this whole file into Antigravity)

You are building the **backend** of Cropsy, a multi-model, multimodal, agentic agriculture advisory system for
the FarmwiseAI Product Challenge, Task 1. Work inside `E:\farm ai\cropsy final\backend`. Do not edit anything in
`E:\farm ai\cropsy final\dataset` or in the two frontend folders. The data you need is already built.

## 1. What the system does
A farmer asks a question in English, Tamil or Tanglish about a parcel in the demo village **Then Malai**, optionally
with a crop photo. The system plans the request, routes each step to the cheapest capable model or tool, gathers
evidence from tools and documents, writes a grounded answer, verifies it, and returns structured JSON plus a full
trace (model, reason, latency, cost per step). Nothing may be hard-coded to a specific query.

## 2. Pipeline (implement exactly this)
```
query (+parcel_id, +image)  ->  load parcel context, open execution record
  -> understand      Nova Micro: normalise Tamil/Tanglish, extract crop/intent/stage (EVERY request)
  -> image attached? yes: Nova Lite extracts visible symptoms
  -> router          rules + confidence (threshold 0.85) -> ROUTINE | ADVISORY | VISUAL | COMPLEX | OUT_OF_SCOPE
        ROUTINE   -> structured tools (parcel lookup, stage calendar, calculators, village query)
        ADVISORY  -> Titan Text V2 retrieval over backend/knowledge/chunks.jsonl
        VISUAL    -> Titan Multimodal similar-image retrieval over backend/data/images (train split only)
  -> parallel tools  parcel data, weather (Open-Meteo live, fall back to backend/data/weather/daily.csv, mark "cached")
  -> evidence sufficient?  no -> ask farmer / refer to expert (never invent)
        yes+routine -> Nova Micro grounded answer ; yes+complex -> Ministral 8B multi-factor synthesis
  -> deterministic validation (crop matches parcel, units, numbers recomputed, every dose appears verbatim in a cited chunk)
        fail -> retry ONCE on Ministral 8B -> still failing -> ask farmer / expert review
  -> response in the farmer's language + sources + trace
```
Models (confirm each with a real test call, ids are config, not constants in code):
Ministral 3B and 8B (open-weight), Nova Micro and Nova Lite (proprietary), Titan Text Embeddings V2 (256-d),
Titan Multimodal Embeddings (`amazon.titan-embed-image-v1`). Old code used ids `mistral.ministral-3-3b-instruct`,
`mistral.ministral-3-8b-instruct`, `amazon.titan-embed-text-v2:0`, `amazon.titan-embed-image-v1`,
`apac.amazon.nova-micro-v1:0`, `apac.amazon.nova-lite-v1:0`. Nova via `apac.*` profiles may be blocked by the event
rules (cross-Region profiles restricted): test it, and if denied, mark the model `unavailable` in config and let the router
degrade (Lite -> human review, Micro -> Ministral 3B) while recording that in the trace.
AWS: region `ap-south-1` only, profile `FAI-TCE-Builder-AI-402365884845`, boto3. Never create IAM roles or users.
Never hard-code credentials. If SSO is expired, stop and tell the user to run `aws sso login`.

## 3. Data already built (read these, do not regenerate)
- `data/parcels.json` 120 parcels: location, soil, terrain, owner, crop {name, variety, planting_date, days_after_planting, stage}, management, observed_issue {code, label, kind, severity, symptoms, photo_class}, wildlife. `data_source: dummy`.
- `data/village_parcels.geojson` + `.csv` polygons and flat rows for the map. `data/village.json`.
- `data/history.csv` 5 seasons per parcel. `data/weather/daily.csv` 90 observed + 7 forecast days per parcel (dummy).
- `data/issue_catalog.json`, `data/crop_stages.json` (stage by days after planting).
- `data/images/manifest.json` + `images/<crop>/<issue>/*.jpg` 1,018 photos. `split`: train | holdout | reference. Retrieve from train and reference only, never holdout. `condition_code: field_scene` photos are wide field shots with UNVERIFIED health and stage (licence unknown): use them only to confirm the crop, never as disease evidence, and never copy their stage onto a parcel.
- `knowledge/chunks.jsonl` 302 chunks (295 from the TNAU Crop Production Guides + 7 from TNAU Agritech portal pages, `document_id: WEB_TNAU_AGRITECH`, with `dose_source` saying whether the dose was read from the PDF or through a summariser, re-check those) {chunk_id, crop, text, section, topics, stages, has_dose, page, title, source_quality}. `knowledge/sources.json`.
- `data/queries.json` 26 test queries with expected route, tools, facts, injected failures. Use it as the test and demo set.
Known gaps: no advice for banana Cordana, banana Pestalotiopsis and maize gray leaf spot; sugarcane mosaic has symptoms and general sett advice but NO chemical dose; no healthy coconut photos.
For these the system must say the evidence is insufficient and refer to an expert, not guess.
Everything marked dummy must stay labelled dummy in responses.

## 4. Layout to create
```
backend/app/{main.py,config.py,schemas.py,pipeline.py}
backend/app/models/{bedrock.py,cost.py}
backend/app/steps/{understand.py,vision.py,router.py,retrieve.py,tools.py,synthesize.py,verify.py}
backend/app/store/{base.py,memory.py}        # same interface; DynamoDB implementation comes later
backend/app/lambda_handler.py                # Mangum wrapper, last step
backend/scripts/{embed_knowledge.py,embed_images.py}   # write caches to backend/cache/, resumable
backend/tests/ ; backend/requirements.txt ; backend/README.md
```
Rules: every step is a small function `step(state) -> state` that appends a trace entry
`{step, tool_or_model, why, status, latency_ms, est_cost_usd, input_summary, output_summary}`. One shared `State`
object holds the plan, intermediate results, sources and decisions. All model calls go through `models/bedrock.py`
(retry, timeout, token/cost accounting, fallback to the next model). Storage goes through `store/base.py`.
No Qwen, no HuggingFace, no local GPU models, no FAISS: keep it Lambda-friendly (numpy cosine over cached vectors is fine).
The old backend in `E:\farm ai\cropsy` may be read for ideas (verifier rules, Titan retrievers); copy only what you understand and clean.

## 5. API (match the existing frontend)
`GET /health`, `POST /api/advisory` {query, parcel_id?, image_bytes? (base64), image_format?, image_name?},
`GET /api/parcels` (GeoJSON), `GET /api/parcels/{id}`, `GET /api/executions`, `GET /api/executions/{id}`,
`POST /api/chat`. Response follows the frontend type `Phase7AdvisoryResult` in
`Cropsy-FarmwiseAI-Frontend-updated/.../src/lib/cropsy-api.ts` (answer, recommendations, actions
{immediate, next_24_hours, next_3_to_7_days, watch_for}, risks, sources, limitations, verification {status, checks},
model, route, tools_called, estimated_cost_usd, observability). Add the trace array. CORS for localhost:5173.

## 6. Quality gates
1. `pytest` passes with Bedrock mocked for unit tests, plus a live smoke test script that runs 5 queries from `data/queries.json`.
2. A runner `python -m backend.tests.run_queries` executes all 26 queries and prints, per query: route taken vs expected, models used, latency, cost, verification result. Failure-injection queries (Q04, Q26) must demonstrate the retry and the cached-weather fallback.
3. The unseen queries (split = unseen) must never be quoted in prompts or used for tuning thresholds.
4. Cost/route comparison: report the cost of the routed pipeline against sending every query to Ministral 8B.
5. Never fabricate a dose: every dose in an answer must appear verbatim in a cited chunk, otherwise strip it and flag it.
6. Report honestly what works, what was mocked and what failed.

Start with: config + `bedrock.py` + a script that test-calls all six models and prints which are usable. Then the steps,
then the pipeline, then the API. Commit nothing; show diffs.

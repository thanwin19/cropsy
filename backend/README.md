# Cropsy Backend
> This is the backend-only note, parts of it are older. The current, full description of Cropsy is in the [top-level README](../README.md).

Multi-model, multimodal, agentic agriculture advisory backend for Then Malai, Tamil Nadu.

## Architecture

```
query (+parcel_id, +image)
  → understand    Nova Micro: normalise Tamil/Tanglish, extract crop/intent/stage
  → vision        Nova Lite:  extract visible symptoms from photo (if image attached)
  → tools         parcel lookup, weather (live Open-Meteo → fallback CSV), village stats
  → router        rule-based classifier → ROUTINE / ADVISORY / VISUAL / COMPLEX / OUT_OF_SCOPE
  → retrieve      Titan Text V2 over chunks.jsonl  +  Titan Multimodal over image embeddings
  → synthesize    Nova Micro (ROUTINE/ADVISORY)  or  Ministral 8B (COMPLEX/VISUAL)
  → verify        5 deterministic checks (crop match, dose verbatim, known-gap disclaimer, dummy label, non-empty)
  → Phase7AdvisoryResult
```

## Layout

```
backend/
  app/
    config.py           All model IDs, paths, thresholds — never hard-coded elsewhere
    schemas.py          Pydantic models (Phase7AdvisoryResult matches cropsy-api.ts)
    pipeline.py         Chains all steps
    main.py             FastAPI app (6 endpoints)
    lambda_handler.py   Mangum wrapper for AWS Lambda
    models/
      bedrock.py        Bedrock client (retry, timeout, cost accounting)
      cost.py           Token → USD helpers
    steps/
      understand.py     Nova Micro (fallback: Ministral 3B)
      vision.py         Nova Lite multimodal
      router.py         Rule-based + crop-mismatch + known-gap detection
      tools.py          Parcel lookup, weather, village query, stage calendar
      retrieve.py       Titan Text V2 + Titan Multimodal + BM25 fallback
      synthesize.py     LLM answer generation
      verify.py         Deterministic 5-check verifier
    store/
      base.py           Abstract store interface
      memory.py         In-memory execution store (thread-safe)
  scripts/
    test_models.py      Probe all 6 models → cache/model_status.json
    embed_knowledge.py  Build Titan Text V2 embeddings for chunks.jsonl
    embed_images.py     Build Titan Multimodal embeddings for train-split images
  tests/
    conftest.py         Mocked Bedrock fixtures (autouse, no AWS needed)
    test_pipeline.py    Unit + integration tests
    run_queries.py      All 25 queries runner
  data/                 Parcels, queries, weather, images (READ ONLY)
  knowledge/            chunks.jsonl, sources.json (READ ONLY)
  cache/                embeddings.npz, image_embeddings.npz, model_status.json
  uploads/              Uploaded images (runtime)
```

## Quick Start

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. AWS credentials

```powershell
aws sso login --profile FAI-TCE-Builder-AI-402365884845
```

### 3. Test models (first time only)

```powershell
python scripts/test_models.py
```

Check `cache/model_status.json` for which models are accessible.

### 4. Build embeddings (first time only — needs AWS)

```powershell
python scripts/embed_knowledge.py    # ~30 min for 295 chunks
python scripts/embed_images.py       # train split only
```

Without embeddings the retriever falls back to BM25 (still functional).

### 5. Run the server

```powershell
# From backend/ directory:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend at `http://localhost:5173` connects automatically via CORS.

### 6. Run tests (offline, no AWS needed)

```powershell
pytest tests/ -v
```

### 7. Run all 25 queries (mock mode)

```powershell
python tests/run_queries.py
```

### 8. Run all 25 queries (live, needs AWS)

```powershell
python tests/run_queries.py --live
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + chunk/parcel counts |
| POST | `/api/advisory` | Main pipeline → Phase7AdvisoryResult |
| POST | `/api/chat` | Chat wrapper (plain reply) |
| POST | `/api/v1/query` | Legacy query endpoint |
| POST | `/api/v1/upload` | Upload image/document (base64 JSON) |
| GET | `/api/v1/executions` | List execution records (filter by status) |
| GET | `/api/v1/executions/{id}` | Single execution record |
| GET | `/api/parcels` | List parcels (filter by crop, zone) |
| GET | `/api/parcels/{id}` | Single parcel |

## Models

| Model | Bedrock ID | Use |
|-------|-----------|-----|
| Nova Micro | `apac.amazon.nova-micro-v1:0` | understand, synthesize (ROUTINE) |
| Nova Lite | `apac.amazon.nova-lite-v1:0` | vision (multimodal) |
| Ministral 3B | `mistral.ministral-3-3b-instruct` | understand fallback |
| Ministral 8B | `mistral.ministral-3-8b-instruct` | synthesize (COMPLEX/VISUAL) |
| Titan Text V2 | `amazon.titan-embed-text-v2:0` | text embeddings (256-d) |
| Titan Multimodal | `amazon.titan-embed-image-v1` (no `:0`; the `:0` ARN is denied) | image embeddings |

If a Nova model is blocked by cross-region rules, the router degrades to Ministral automatically.

## Safety rules

- **No fabricated doses**: every dose in an answer must appear verbatim in a cited chunk; otherwise the verifier strips it.
- **Known gaps**: Cordana, Pestalotiopsis, sugarcane mosaic, maize gray leaf spot, coconut leaf rot → always says "insufficient evidence".
- **Dummy data**: parcel management data is labelled `(dummy data)` in all answers.
- **Dummy weather**: cached weather CSV is also labelled as dummy/cached.

## AWS constraints

- Region: `ap-south-1` only
- Profile: `FAI-TCE-Builder-AI-402365884845`
- No IAM roles or users are created
- No credentials are hard-coded

## Known gaps

See `data/queries.json` field `tests` for per-query notes. Q23 (cotton on rice parcel) and gaps listed in `config.KNOWN_GAPS` always return OUT_OF_SCOPE.

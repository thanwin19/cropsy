"""
schemas.py — Pydantic models for Cropsy backend.
Matches Phase7AdvisoryResult in cropsy-api.ts exactly.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Trace (internal, returned in observability) ───────────────────────────────
class TraceEntry(BaseModel):
    step: str
    tool_or_model: str
    why: str
    status: str                  # ok | error | skipped | fallback
    latency_ms: float
    est_cost_usd: float
    input_summary: str
    output_summary: str


# ── Pipeline state (internal, passed step → step) ─────────────────────────────
class PipelineState(BaseModel):
    # Request
    query: str
    parcel_id: Optional[str] = None
    image_bytes: Optional[str] = None   # base64
    image_format: Optional[str] = None
    image_name: Optional[str] = None
    inject_failure: Optional[str] = None  # for test harness
    context_crop: Optional[str] = None    # crop of the previous answer (follow-up questions)
    safety_card: bool = False             # a fixed answer about a banned or restricted chemical (no dose is ever given)

    # Understand step outputs
    language: Optional[str] = None
    visual_caption: Optional[dict[str, Any]] = None     # structured description of the photo (CPJ step 1)
    caption_judge: Optional[dict[str, Any]] = None      # the judge's verdict on that description (CPJ step 2)
    visual_agreement: Optional[dict[str, Any]] = None   # caption versus nearest reference photos (CPJ check)
    region: Optional[dict[str, Any]] = None           # where the farmer is: country, state, district, zone, and how we know (question, profile, parcel, unknown)
    region_note: Optional[str] = None                 # one honest line about where the advice applies
    doc_text: Optional[str] = None    # text read from an attached document (Textract / PDF text): the answer explains it, no guide cards
    force_guide: bool = False         # how-to-make / how-to-protect question: answered from the fixed guides, no language model
    force_facts: bool = False         # factual parcel question: answered from the data, no language model
    facts: Optional[dict[str, Any]] = None
    force_general: bool = False       # the question is about a plant outside the knowledge base: skip the LLM answer, give general guidance
    general_mode: bool = False        # answer is general guidance (no verified source): figures are model estimates, labelled approx.
    normalized_query: Optional[str] = None
    crop_hint: Optional[str] = None
    intent: Optional[str] = None
    stage_hint: Optional[str] = None

    # Vision step outputs
    visual_observations: Optional[list[str]] = None
    possible_symptom: Optional[str] = None
    diagnosis: Optional[str] = None

    # Router outputs
    route: Optional[str] = None
    route_confidence: float = 0.0
    gap_condition: Optional[str] = None      # photo matched a condition with no verified advice
    retry_count: int = 0
    calc: Optional[dict[str, Any]] = None    # deterministic fertilizer calculation
    image_consensus: Optional[str] = None    # summary of nearest reference photos
    satellite: Optional[dict[str, Any]] = None  # real Sentinel-2 NDVI summary for the parcel

    # Tool outputs
    parcel_context: Optional[dict[str, Any]] = None
    weather_data: Optional[dict[str, Any]] = None
    weather_source: str = "live"      # live | cached

    # Retrieval outputs
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    image_matches: list[dict[str, Any]] = Field(default_factory=list)

    # Evidence quality
    evidence_local_sufficient: bool = False
    evidence_gap_detected: bool = False

    # Synthesis
    raw_answer: Optional[str] = None
    recommendations: list[str] = Field(default_factory=list)
    actions: Optional[dict[str, list[str]]] = None
    risks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    why_this_matters: list[dict[str, Any]] = Field(default_factory=list)

    # Verification
    verification_status: str = "pass"   # pass | flagged | needs_retry
    verification_checks: list[dict[str, Any]] = Field(default_factory=list)
    verification_flags: list[str] = Field(default_factory=list)
    sanitized_recommendations: list[str] = Field(default_factory=list)

    # Model used for synthesis
    synthesis_model_id: Optional[str] = None
    synthesis_model_tier: Optional[str] = None
    synthesis_bedrock_invoked: bool = False
    synthesis_token_count: int = 0

    # Observability
    trace: list[TraceEntry] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0

    model_config = {"arbitrary_types_allowed": True}


# ── Request body for POST /api/advisory ──────────────────────────────────────
class AdvisoryRequest(BaseModel):
    query: str
    parcel_id: Optional[str] = None
    context_crop: Optional[str] = None            # crop of the previous answer in this chat; used only for a short question that names no crop
    region: Optional[dict[str, Any]] = None       # the farmer's saved location (country, state, district), sent only if they chose to save it on their device
    image_bytes: Optional[str] = None
    image_format: Optional[str] = None
    image_name: Optional[str] = None


# ── Phase7Source ──────────────────────────────────────────────────────────────
class Phase7Source(BaseModel):
    document_id: str
    title: str
    page: Optional[str] = None
    domain: Optional[str] = None
    provenance: Optional[str] = "authoritative"


# ── Phase7Model ───────────────────────────────────────────────────────────────
class Phase7ModelInfo(BaseModel):
    model_id: str
    model_name: str
    tier: str
    bedrock_invoked: bool
    token_count: Optional[int] = None
    latency_ms: Optional[float] = None
    model_selected: Optional[str] = None
    agent_model: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    reason: Optional[str] = None
    reason_for_selection: Optional[str] = None


# ── Phase7VerificationCheck ───────────────────────────────────────────────────
class Phase7VerificationCheck(BaseModel):
    check: str
    passed: bool
    flag: Optional[str] = None


# ── Phase7Verification ────────────────────────────────────────────────────────
class Phase7Verification(BaseModel):
    status: str
    success: bool
    checks_passed: int
    total_checks: int
    checks: Optional[list[Phase7VerificationCheck]] = None
    flags: list[str] = Field(default_factory=list)
    sanitized_recommendations: Optional[list[str]] = None


# ── Phase7Actions ─────────────────────────────────────────────────────────────
class Phase7Actions(BaseModel):
    immediate: Optional[list[str]] = None
    next_24_hours: Optional[list[str]] = None
    next_3_to_7_days: Optional[list[str]] = None
    watch_for: Optional[list[str]] = None


# ── WhyThisMattersItem ────────────────────────────────────────────────────────
class WhyThisMattersItem(BaseModel):
    parcel_fact: str
    mechanism: str
    claim: Optional[str] = None
    source: Optional[str] = None
    source_citation: Optional[str] = None
    institution: Optional[str] = None
    verified_status: Optional[str] = None


# ── Phase7Observability ───────────────────────────────────────────────────────
class Phase7Observability(BaseModel):
    route: Optional[str] = None
    agent_model: Optional[str] = None
    model_selected: Optional[str] = None
    model_id: Optional[str] = None
    reason: Optional[str] = None
    model_reason: Optional[str] = None
    cost_mode: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    tools_called: Optional[list[str]] = None
    latency_ms: Optional[float] = None
    verified: Optional[bool] = None
    data_quality: Optional[Any] = None
    sources: Optional[list[str]] = None
    raw_query: Optional[str] = None
    language: Optional[str] = None
    structured_query: Optional[dict[str, Any]] = None
    laya_decision: Optional[dict[str, Any]] = None
    requires_agentic_rag: Optional[bool] = None
    bedrock_invoked: Optional[bool] = None
    fallback_used: Optional[bool] = None
    vision_model: Optional[str] = None
    titan_text_v2_invoked: Optional[bool] = None
    titan_text_chunks_retrieved: Optional[int] = None
    titan_multimodal_invoked: Optional[bool] = None
    titan_multimodal_matches: Optional[int] = None
    evidence_local_sufficient: Optional[bool] = None
    evidence_gap_detected: Optional[bool] = None
    external_retrieval_attempted: Optional[bool] = None
    external_sources_found: Optional[int] = None
    external_sources_accepted: Optional[int] = None
    final_llm_invoked: Optional[bool] = None
    trace: Optional[list[dict[str, Any]]] = None


# ── Phase7AdvisoryResult (main API response) ──────────────────────────────────
class Phase7AdvisoryResult(BaseModel):
    parcel_id: Optional[str] = None
    survey_no: Optional[str] = None
    query: str
    task_type: Optional[str] = None
    answer: Optional[str] = None
    recommendations: Optional[list[str]] = None
    reasons: Optional[list[str]] = None
    why_this_matters: Optional[list[WhyThisMattersItem]] = None
    risks: Optional[list[str]] = None
    actions: Optional[Phase7Actions] = None
    image: Optional[dict[str, Any]] = None
    parcel_context: Optional[dict[str, Any]] = None
    evidence: Optional[list[dict[str, Any]]] = None
    sources: Optional[list[Phase7Source]] = None
    limitations: Optional[list[str]] = None
    data_quality: Optional[Any] = None
    model: Optional[Phase7ModelInfo] = None
    verification: Optional[Phase7Verification] = None
    verified: Optional[bool] = None
    route: Optional[str] = None
    model_selected: Optional[str] = None
    agent_model: Optional[str] = None
    tools_called: Optional[list[str]] = None
    cost_mode: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    observability: Optional[Phase7Observability] = None
    possible_symptom: Optional[str] = None
    visual_observations: Optional[list[str]] = None
    diagnosis: Optional[str] = None
    parcel_facts: Optional[dict[str, Any]] = None
    reference_photos: Optional[list[dict[str, Any]]] = None
    fertilizer_guides: Optional[list[dict[str, Any]]] = None
    region: Optional[dict[str, Any]] = None
    crop: Optional[str] = None
    doc_values: Optional[list[dict[str, Any]]] = None      # 'name value unit rating' rows read from an attached document, shown as a values list
    confidence: Optional[dict[str, Any]] = None
    visual_report: Optional[dict[str, Any]] = None
    cross_check: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


# ── Chat schemas ──────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None
    parcel_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    answer: Optional[str] = None
    recommendations: Optional[list[str]] = None
    model_used: Optional[str] = None


# ── Upload schemas ────────────────────────────────────────────────────────────
class UploadRequest(BaseModel):
    filename: str
    data: str    # base64 data URL


class UploadResponse(BaseModel):
    filename: str
    original_filename: str
    file_path: str
    file_type: str
    url: str

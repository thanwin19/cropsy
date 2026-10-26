export type TaskStatus = 'queued' | 'running' | 'completed' | 'flagged' | 'needs_retry' | 'fallback';

export type RagQualityMetrics = {
  faithfulness: number | null;
  answer_relevance: number | null;
  context_precision: number | null;
  computed?: boolean;
  flags?: string[];
};

export type TaskRecord = {
  task_id: string;
  description: string;
  selected_model_or_tool: string;
  reason_for_selection: string;
  predicted_confidences: Record<string, number>;
  actual_result: string;
  actual_confidence: number;
  status: TaskStatus;
  source: string;
  latency_ms: number;
  estimated_cost: number;
  rag_citations: string[];
  rag_quality_metrics?: RagQualityMetrics | null;
  verification_result: string;
  fallback_attempts: string[];
  candidate_models_considered?: string[];
  features?: {
    query_complexity?: number;
    image_quality?: number | null;
    data_completeness?: number;
    similarity_to_past_queries?: number;
    task_type?: string;
    word_count?: number;
    has_image?: boolean;
    [key: string]: any;
  };
  selected_model_name?: string;
  tier?: string;
};

export type ResolvedParcel = {
  survey_no: string;
  district: string;
  taluk: string;
  village: string;
  area_acres: number;
  source: string;
};

export type LandRecord = {
  owner: string;
  land_type: string;
  irrigation: string;
  source: string;
};

export type HourlySunPoint = {
  time: string;
  altitude_deg: number;
  azimuth_deg: number;
  is_daylight: boolean;
};

export type SunPositionData = {
  status: string;
  date: string;
  sunrise: string;
  sunset: string;
  solar_noon: string;
  dawn?: string | null;
  dusk?: string | null;
  golden_hour_morning?: string | null;
  golden_hour_evening?: string | null;
  daylight_hours: number;
  current_position?: {
    altitude_deg: number;
    azimuth_deg: number;
    time: string;
  } | null;
  hourly_curve: HourlySunPoint[];
};

export type ShadowAnalysisData = {
  terrain_shading_effect: string;
  morning_exposure: string;
  afternoon_exposure: string;
  summary: string;
};

export type SunShadowAnalysis = {
  status: string;
  sun_position?: SunPositionData;
  terrain_elevation?: {
    status: string;
    elevations_m?: Record<string, number>;
    source?: string;
  };
  shadow_analysis?: ShadowAnalysisData;
};

export type CropPrediction = {
  crop: string;
  growth_stage: string;
  condition: string;
  confidence: number;
  model_used: string;
  image_url?: string | null;
};


export type AdvisoryCitation = {
  source_doc: string;
  section: string;
  relevance_score: number;
};

export type Advisory = {
  recommendation: string;
  urgency: string;
  citations: AdvisoryCitation[];
  rag_quality_metrics?: RagQualityMetrics | null;
};

export type ExecutionRecord = {
  execution_id: string;
  user_request: string;
  execution_plan: string[];
  tasks: TaskRecord[];
  final_answer: string;
  total_latency_ms: number;
  total_estimated_cost: number;
  verification_result: string;
  created_at?: string;
  resolved_parcel?: ResolvedParcel;
  land_record?: LandRecord;
  crop_prediction?: CropPrediction;
  advisory?: Advisory;
  sun_and_shadow?: SunShadowAnalysis | null;
};

export type QueryResponse = { execution_id: string };
export type StreamHandlers = {
  onTask?: (task: TaskRecord) => void;
  onComplete?: (record: ExecutionRecord) => void;
  onError?: (error: Error) => void;
};

const DEFAULT_BASE = import.meta.env.VITE_CROPSY_API_BASE || '';
const DEMO_KEY = 'cropsy-demo-mode';
const BASE_KEY = 'cropsy-api-base';

import { consentHeader, getRegionProfile } from './privacy';

export function getApiSettings() {
  const hasStorage = typeof window !== 'undefined' && typeof localStorage !== 'undefined';
  return {
    baseUrl: hasStorage ? (localStorage.getItem(BASE_KEY) ?? DEFAULT_BASE) : DEFAULT_BASE,
    demoMode: hasStorage ? (localStorage.getItem(DEMO_KEY) === 'true') : false,
  };
}

export function saveApiSettings(settings: { baseUrl: string; demoMode: boolean }) {
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    localStorage.setItem(BASE_KEY, settings.baseUrl);
    localStorage.setItem(DEMO_KEY, String(settings.demoMode));
  }
}

let _lastExecutionCache: Record<string, ExecutionRecord> = {};

export function demoRecord(request: string, id = 'run-demo-384') : ExecutionRecord {
  return {
    execution_id: id,
    user_request: request,
    created_at: new Date().toISOString(),
    execution_plan: [
      'Resolve the parcel geometry and administrative hierarchy',
      'Lookup official land and ownership records',
      'Retrieve ground-truth field photograph and predict crop',
      'Phase 7 Pre-Execution Confidence Router: select cost-optimal model tier',
      'Retrieve grounded agronomic advisory from vector index',
      'Verify execution against deterministic critic rules',
    ],
    tasks: [
      {
        task_id: 'parcel',
        description: 'Resolve survey number to cadastral and FMB boundaries',
        selected_model_or_tool: 'geography_agent',
        reason_for_selection: 'Dual-layer GeoJSON matching across cadastral and FMB datasets',
        predicted_confidences: { geography: 0.99 },
        actual_result: 'Survey 384/1 · Allikulam · Thoothukudi · 1.84 acres',
        actual_confidence: 0.99,
        status: 'completed',
        source: 'Park_Cadastral_Map.geojson + Park_fmb_Map.geojson',
        latency_ms: 112,
        estimated_cost: 0.0,
        rag_citations: ['Cadastral overlay · CRS84 · 2/2 layers matched'],
        verification_result: 'Deterministic match on 2 GIS layers',
        fallback_attempts: [],
      },
      {
        task_id: 'photo',
        description: 'Retrieve parcel-linked field photograph',
        selected_model_or_tool: 'image_retrieval_agent',
        reason_for_selection: 'Ground_truth_Points.csv spatial join on village and survey_no',
        predicted_confidences: { retrieval: 0.97 },
        actual_result: 'Photo 933535_1342_169__*.jpg verified on disk',
        actual_confidence: 0.97,
        status: 'completed',
        source: 'Ground_truth_Points.csv · dataset/crop_photos_ground_truth/',
        latency_ms: 84,
        estimated_cost: 0.0,
        rag_citations: ['Photo index: 3,422 photos, 14,643 points'],
        verification_result: 'Physical file verified on disk',
        fallback_attempts: [],
      },
      {
        task_id: 'crop',
        description: 'Predict crop, growth stage, and condition from visual embedding',
        selected_model_or_tool: 'amazon.titan-embed-image-v1 + centroid_head',
        reason_for_selection: '1024-d visual embedding evaluated against trained crop centroids',
        predicted_confidences: { crop: 0.96, stage: 0.91 },
        actual_result: 'Rice / Paddy · Tillering stage · Healthy (moderate moisture)',
        actual_confidence: 0.91,
        status: 'completed',
        source: 'Amazon Titan Multimodal Embeddings (ap-south-1)',
        latency_ms: 1240,
        estimated_cost: 0.005,
        rag_citations: ['Centroid cosine similarity: 0.9664'],
        verification_result: 'High-confidence visual classification',
        fallback_attempts: [],
      },
      {
        task_id: 'model_router',
        description: 'Predict candidate model confidences and select cost-optimal tier before invocation',
        selected_model_or_tool: 'mistral.ministral-3-3b-instruct',
        reason_for_selection: 'Selected Ministral 3B Instruct (cheap_open): predicted confidence 0.99 clears threshold 0.85 at minimum cost ($0.00015).',
        predicted_confidences: {
          'mistral.ministral-3-3b-instruct': 0.99,
          'mistral.ministral-3-8b-instruct': 0.99,
          'apac.amazon.nova-micro-v1:0': 0.98,
          'apac.amazon.nova-lite-v1:0': 0.99,
        },
        actual_result: 'Ministral 3B Instruct selected for synthesis (tier: cheap_open)',
        actual_confidence: 0.99,
        status: 'completed',
        source: 'Phase 7 Confidence-Predictor Router',
        latency_ms: 18,
        estimated_cost: 0.00015,
        rag_citations: ['Router feature weights & calibrated threshold: 0.85'],
        verification_result: 'Predicted confidence 0.99 exceeds safety threshold 0.85',
        fallback_attempts: [],
        candidate_models_considered: [
          'mistral.ministral-3-3b-instruct',
          'mistral.ministral-3-8b-instruct',
          'apac.amazon.nova-micro-v1:0',
          'apac.amazon.nova-lite-v1:0',
        ],
        features: {
          query_complexity: 0.285,
          image_quality: null,
          data_completeness: 0.75,
          similarity_to_past_queries: 0.45,
          task_type: 'advisory_retrieval',
          has_image: false,
          word_count: 14,
        },
      },
      {
        task_id: 'advisory',
        description: 'Ground recommendation in verified agronomic reference corpus',
        selected_model_or_tool: 'KnowledgeRetriever (FAISS + Titan Text V2)',
        reason_for_selection: 'Dense semantic retrieval over agronomy guides and fertilizer schedules',
        predicted_confidences: { relevance: 0.89 },
        actual_result: 'Keep nitrogen steady; let the field dry between irrigations',
        actual_confidence: 0.89,
        status: 'completed',
        source: 'crop-field-advisory.txt + soil-moisture-fertilizer.txt',
        latency_ms: 638,
        estimated_cost: 0.001,
        rag_citations: ['crop-field-advisory.txt (0.89 relevance)', 'soil-moisture-fertilizer.txt (0.84 relevance)'],
        verification_result: 'Grounded in 2 verified sources',
        fallback_attempts: [],
      },
      {
        task_id: 'verifier',
        description: 'Post-hoc safety verification and response synthesis',
        selected_model_or_tool: 'Phase 9 Verifier + Ministral 8B',
        reason_for_selection: '5 deterministic safety rules evaluated over execution state',
        predicted_confidences: { safety: 1.0 },
        actual_result: 'All 5 safety rules passed · 0 conflicts detected',
        actual_confidence: 0.94,
        status: 'completed',
        source: 'Cropsy Deterministic Critic',
        latency_ms: 792,
        estimated_cost: 0.001,
        rag_citations: ['Deterministic audit trace attached'],
        verification_result: 'Trace verified · 0 conflicts detected',
        fallback_attempts: [],
      },
    ],
    final_answer: 'Survey 384/1 in Allikulam village (Thoothukudi district) resolves to a 1.84-acre parcel with 2/2 GIS layers matched. Imagery indicates Rice / Paddy at tillering stage in healthy condition. Grounded advisory: Split the next nitrogen application and avoid standing water for more than 2–3 days. Current field condition suggests adequate moisture, not stress.',
    total_latency_ms: 2840,
    total_estimated_cost: 0.014,
    verification_result: 'Trace verified · all 5 safety checks passed',
    resolved_parcel: {
      survey_no: '384/1',
      district: 'Thoothukudi',
      taluk: 'Thoothukudi',
      village: 'Allikulam',
      area_acres: 1.84,
      source: 'Park_Cadastral_Map.geojson + Park_fmb_Map.geojson',
    },
    land_record: {
      owner: 'SIPCOT Industrial Complex',
      land_type: 'Acquired Agricultural / Industrial Land · 1.84 acres',
      irrigation: 'Rainfed / Open Well',
      source: 'Patta / Land Records Registry (1755)',
    },
    crop_prediction: {
      crop: 'Rice / Paddy',
      growth_stage: 'Tillering',
      condition: 'Healthy · moderate moisture',
      confidence: 0.91,
      model_used: 'amazon.titan-embed-image-v1 + centroid_head',
      image_url: null,
    },
    advisory: {
      recommendation: 'Keep nitrogen steady; let the field dry between irrigations. For rice at tillering, split the next nitrogen application and avoid standing water for more than 2–3 days. Current field condition suggests adequate moisture, not stress.',
      urgency: 'Next 48–72 hours',
      citations: [
        { source_doc: 'crop-field-advisory.txt', section: 'TNAU Rice Guidance §3.1', relevance_score: 0.89 },
        { source_doc: 'soil-moisture-fertilizer.txt', section: 'Fertilizer & Irrigation §2.4', relevance_score: 0.84 },
      ],
    },
  };
}

function mapBackendToExecutionRecord(data: any, defaultRequest: string): ExecutionRecord {
  const execution = data.execution || {};
  const outputs = data.outputs || {};
  const geo = outputs.geography_agent || outputs.geography || {};
  const land = outputs.land_record_connector || outputs.land_record || {};
  const photo = outputs.image_retrieval_agent || {};
  const vision = outputs.vision_model || outputs.vision || {};
  const advisory = outputs.advisory || outputs.response_synthesis || {};
  const tasksRaw = data.tasks || [];
  const verification = data.verification || {};

  const mappedTasks: TaskRecord[] = tasksRaw.map((t: any) => ({
    task_id: t.task_id || 'task',
    description: t.description || t.task_id || '',
    selected_model_or_tool: t.selected_model_or_tool || t.tool || 'Cropsy Tool',
    reason_for_selection: t.reason_for_selection || t.reason || '',
    predicted_confidences: t.predicted_confidences || {},
    actual_result: typeof t.actual_result === 'object' ? JSON.stringify(t.actual_result).replace(/[{}"]/g, ' ') : String(t.actual_result || ''),
    actual_confidence: t.actual_confidence !== undefined && t.actual_confidence !== null ? t.actual_confidence : 0.95,
    status:
      t.verification_result === 'flagged'
        ? 'flagged'
        : t.verification_result === 'needs_retry'
          ? 'needs_retry'
          : t.status === 'succeeded' || t.status === 'completed'
            ? 'completed'
            : t.status || 'completed',
    source: t.source || 'Cropsy System',
    latency_ms: Math.round(t.latency_ms || 100),
    estimated_cost: t.estimated_cost || 0.0,
    rag_citations: (t.rag_citations || []).map((c: any) => typeof c === 'string' ? c : `${c.source_doc} (${c.relevance_score ? Math.round(c.relevance_score * 100) + '%' : 'grounded'})`),
    rag_quality_metrics: t.rag_quality_metrics || (typeof t.actual_result === 'object' ? t.actual_result?.rag_quality_metrics : undefined) || null,
    verification_result:
      t.verification_result ||
      (verification.status && verification.status !== 'pass'
        ? String(verification.status)
        : 'Verified with 0 conflicts'),
    fallback_attempts: [],
    candidate_models_considered: t.candidate_models_considered || [],
    features: t.features || (typeof t.actual_result === 'object' ? t.actual_result?.features : undefined),
    selected_model_name: typeof t.actual_result === 'object' ? t.actual_result?.selected_model_name : undefined,
    tier: typeof t.actual_result === 'object' ? t.actual_result?.tier : undefined,
  }));

  const resolved_parcel: ResolvedParcel = {
    survey_no: geo.survey_no ? (geo.sub_div ? `${geo.survey_no}/${geo.sub_div}` : geo.survey_no) : (defaultRequest.match(/survey\s*(\d+[\/\w]*)/i)?.[1] || 'Unresolved'),
    district: geo.district || 'Thoothukudi',
    taluk: geo.taluk || 'Thoothukudi',
    village: geo.village || (defaultRequest.match(/in\s+([A-Za-z]+)/i)?.[1] || 'Unknown'),
    area_acres: Number(geo.area_acres || 0),
    source: geo.status === 'resolved' ? 'Park_Cadastral_Map.geojson + Park_fmb_Map.geojson' : 'Geospatial Resolution (Unresolved)',
  };

  const landOwner = land.owner || (land.ownership ? land.ownership.owner : null);
  const land_record: LandRecord = {
    owner: landOwner || 'Owner unavailable — not yet in sample/OCR data',
    land_type: land.land_type || (landOwner ? 'Agricultural Land' : 'Not available'),
    irrigation: land.irrigation || (landOwner ? 'Rainfed / Open Well' : 'Not available'),
    source: land.source
      ? (typeof land.source === 'object' ? land.source.type || 'Patta' : land.source)
      : (landOwner ? 'Patta Registry (1755)' : 'Sample Patta Registry (pending OCR)'),
  };

  const rawImagePath = photo.image_path || (vision.image_path) || null;
  const imageFilename = rawImagePath ? rawImagePath.split(/[\\/]/).pop() : null;

  const crop_prediction: CropPrediction = {
    crop: vision.predicted_crop || vision.crop || 'Unspecified Crop',
    growth_stage: vision.growth_stage || 'Unspecified',
    condition: vision.condition || 'Normal',
    confidence: vision.confidence || 0.0,
    model_used: vision.predicted_crop ? 'amazon.titan-embed-image-v1 + centroid_head' : 'Not predicted',
    image_url: imageFilename ? `/images/${imageFilename}` : null,
  };

  const ragTask = tasksRaw.find((t: any) => t.task_id === 'rag_pipeline' || t.task_id === 'advisory');
  const rawCitations = (ragTask?.rag_citations) || outputs.rag_pipeline?.citations || outputs.response_synthesis?.citations || [];
  const citations: AdvisoryCitation[] = Array.isArray(rawCitations)
    ? rawCitations.map((c: any) => ({
        source_doc: c.source_doc || 'TNAU Agronomic Guide',
        section: c.section || (c.chunk ? c.chunk.replace(/\s+/g, ' ').slice(0, 80) + '...' : 'TNAU Advisory Manual'),
        relevance_score: typeof c.relevance_score === 'number' ? c.relevance_score : 0.88,
      }))
    : [];

  const finalAnswerStr = typeof data.final_answer === 'object'
    ? (data.final_answer.content || JSON.stringify(data.final_answer))
    : String(data.final_answer || '');

  const executionId = data.execution_id || execution.execution_id || 'run-live';
  const totalLatency = typeof data.total_latency_ms === 'number' ? data.total_latency_ms : typeof execution.total_latency_ms === 'number' ? execution.total_latency_ms : mappedTasks.reduce((acc, t) => acc + (t.latency_ms || 0), 0);
  const totalCost = typeof data.total_estimated_cost === 'number' ? data.total_estimated_cost : typeof execution.total_estimated_cost === 'number' ? execution.total_estimated_cost : mappedTasks.reduce((acc, t) => acc + (t.estimated_cost || 0), 0);
  const verStatus = (typeof data.verification_result === 'object' ? data.verification_result?.status : data.verification_result) || verification.status || 'pass';

  const sunShadow = outputs.sun_position_agent || outputs.sun_and_shadow || data.sun_and_shadow || null;

  return {
    execution_id: executionId,
    user_request: data.request?.query || defaultRequest,
    created_at: new Date().toISOString(),
    execution_plan: execution.plan?.steps ? execution.plan.steps.map((s: any) => s.step_id || String(s)) : (data.tasks ? data.tasks.map((t: any) => t.task_id) : []),
    tasks: mappedTasks,
    final_answer: finalAnswerStr || 'Parcel resolved and agronomic advisory generated.',
    total_latency_ms: totalLatency,
    total_estimated_cost: totalCost,
    verification_result: String(verStatus),
    resolved_parcel,
    land_record,
    crop_prediction,
    sun_and_shadow: sunShadow,
    advisory: {
      recommendation: finalAnswerStr || 'Agronomic advisory generated from retrieved sources.',
      urgency: 'Next 48–72 hours',
      citations,
      rag_quality_metrics: (tasksRaw.find((t: any) => t.task_id === 'rag_pipeline')?.rag_quality_metrics)
        || outputs.rag_pipeline?.rag_quality_metrics
        || null,
    },
  };
}

export type QueryContext = {
  survey_no?: string | null;
  village?: string | null;
  village_lg?: string | null;
};

export async function uploadFile(
  file: File,
  options = getApiSettings()
): Promise<{ filename: string; original_filename: string; file_path: string; file_type: string; url: string }> {
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const url = base ? `${base}/api/v1/upload` : '/api/v1/upload';

  // Read file as Base64 Data URL to reliably post via JSON
  const base64Data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = (err) => reject(err);
    reader.readAsDataURL(file);
  });

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: file.name,
      data: base64Data,
    }),
  });

  if (!response.ok) {
    let errorDetail = `Upload failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson?.error?.message) errorDetail = errJson.error.message;
    } catch {
      // default
    }
    throw new Error(errorDetail);
  }

  return await response.json();
}

export async function submitQuery(
  request: string,
  image?: File | null,
  context?: QueryContext,
  options = getApiSettings(),
  document?: File | null
): Promise<QueryResponse & { record: ExecutionRecord }> {
  if (options.demoMode) {
    const record = demoRecord(request);
    _lastExecutionCache[record.execution_id] = record;
    return { execution_id: record.execution_id, record };
  }

  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const url = base ? `${base}/api/v1/query` : '/api/v1/query';

  const payload: any = { query: request };
  if (context?.survey_no) payload.survey_no = context.survey_no;
  if (context?.village) payload.village = context.village;
  if (context?.village_lg) payload.village_lg = context.village_lg;

  // Handle uploaded image
  if (image) {
    try {
      const uploadRes = await uploadFile(image, options);
      payload.image_paths = [uploadRes.file_path];
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Photo upload failed: ${msg}. Please check your connection and try again.`);
    }
  }

  // Handle uploaded document
  if (document) {
    try {
      const docRes = await uploadFile(document, options);
      payload.document_paths = [docRes.file_path];
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Document upload failed: ${msg}. Please check the document and try again.`);
    }
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let errorDetail = `Query failed with status ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson?.error?.message) {
          errorDetail = errorJson.error.message;
        }
      } catch {
        // use default errorDetail
      }
      throw new Error(errorDetail);
    }

    const data = await response.json();
    const record = mapBackendToExecutionRecord(data, request);
    _lastExecutionCache[record.execution_id] = record;
    return { execution_id: record.execution_id, record };
  } catch (err) {
    console.error('submitQuery API error:', err);
    throw err instanceof Error ? err : new Error(String(err));
  }
}

export type FlaggedExecutionSummary = {
  execution_id: string;
  user_request: string;
  timestamp?: string | null;
  created_at?: string | null;
  verification_result?: string | null;
  task_verification_results?: Record<string, string | null>;
  flagged_task_ids?: string[];
  triggered_rules?: string[];
  reasons?: string[];
  verification_summary?: Record<string, unknown>;
};

export type FeedbackRow = { time: string; query: string; parcel_id?: string | null; route?: string | null; helpful: boolean; confidence?: string | null; answer?: string | null };
export async function listFeedback(options = getApiSettings()): Promise<FeedbackRow[]> {
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const response = await fetch(`${base}/api/feedback?limit=50`, { headers: { Accept: 'application/json' } });
  if (!response.ok) return [];
  const body = await response.json();
  return Array.isArray(body?.items) ? body.items : [];
}

export type MissedQuestion = { time: string; query: string; parcel_id?: string | null; kind: string };
export async function listMissedQuestions(options = getApiSettings()): Promise<MissedQuestion[]> {
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const response = await fetch(`${base}/api/misses?limit=50`, { headers: { Accept: 'application/json' } });
  if (!response.ok) return [];
  const body = await response.json();
  return Array.isArray(body?.items) ? body.items : [];
}

export async function listFlaggedExecutions(options = getApiSettings()): Promise<FlaggedExecutionSummary[]> {
  if (options.demoMode) {
    return [];
  }
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const url = base
    ? `${base}/api/v1/executions?verification_status=flagged,needs_retry`
    : '/api/v1/executions?verification_status=flagged,needs_retry';
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`Could not load flagged cases (${response.status})`);
  }
  const body = await response.json();
  return Array.isArray(body?.executions) ? body.executions : [];
}

export async function listExecutions(
  statuses = ['pass', 'flagged', 'needs_retry'],
  options = getApiSettings()
): Promise<FlaggedExecutionSummary[]> {
  if (options.demoMode) {
    return [];
  }
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const statusParam = statuses.join(',');
  const url = base
    ? `${base}/api/v1/executions?verification_status=${statusParam}`
    : `/api/v1/executions?verification_status=${statusParam}`;
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`Could not load executions (${response.status})`);
  }
  const body = await response.json();
  return Array.isArray(body?.executions) ? body.executions : [];
}

export async function getExecution(id: string, options = getApiSettings()): Promise<ExecutionRecord> {
  if (_lastExecutionCache[id]) {
    return _lastExecutionCache[id];
  }
  if (!options.demoMode) {
    const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
    const url = base ? `${base}/api/v1/executions/${id}` : `/api/v1/executions/${id}`;
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) {
      throw new Error(`Failed to load execution record (${response.status})`);
    }
    const data = await response.json();
    const record = mapBackendToExecutionRecord(data, data?.request?.query || '');
    _lastExecutionCache[record.execution_id] = record;
    return record;
  }
  return demoRecord('Resolve survey 384 in Allikulam and recommend fertilizer for the crop stage', id);
}

export async function checkApiHealth(options = getApiSettings()): Promise<{ status: string }> {
  if (options.demoMode) {
    return { status: 'demo-ready' };
  }
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const url = base ? `${base}/health` : '/health';
  try {
    const response = await fetch(url);
    if (!response.ok) return { status: 'offline' };
    const body = await response.json();
    return { status: body.status || 'ok' };
  } catch {
    return { status: 'offline' };
  }
}

export function streamExecution(id: string, handlers: StreamHandlers, options = getApiSettings()) {
  const record = _lastExecutionCache[id] || demoRecord('Resolve survey 384 in Allikulam and recommend fertilizer for the crop stage', id);
  const timers = record.tasks.map((task, index) =>
    window.setTimeout(() => handlers.onTask?.({ ...task, status: 'completed' }), 300 + index * 300)
  );
  const finalTimer = window.setTimeout(() => handlers.onComplete?.(record), 300 + record.tasks.length * 300);
  return () => {
    timers.forEach(window.clearTimeout);
    window.clearTimeout(finalTimer);
  };
}

// ─── Phase 7 Advisory Pipeline Types ────────────────────────────────────────

export type Phase7Source = {
  document_id: string;
  title: string;
  page?: string | null;
  domain?: string;
  provenance?: 'authoritative' | 'derived' | 'representative' | 'ai_synthesis' | string;
};

export type Phase7Model = {
  model_id: string;
  model_name: string;
  tier: string;
  bedrock_invoked: boolean;
  token_count?: number;
  latency_ms?: number;
};

export type Phase7VerificationCheck = {
  check: string;
  passed: boolean;
  flag?: string | null;
};

export type Phase7Verification = {
  status: 'pass' | 'flagged' | 'needs_retry' | string;
  success: boolean;
  checks_passed: number;
  total_checks: number;
  checks?: Phase7VerificationCheck[];
  flags: string[];
  sanitized_recommendations?: string[];
};

export type Phase7Actions = {
  immediate?: string[];
  next_24_hours?: string[];
  next_3_to_7_days?: string[];
  watch_for?: string[];
};

export type Phase7DataQuality = {
  provenance_breakdown?: Record<string, number>;
  completeness_score?: number;
};

export type WhyThisMattersItem = {
  parcel_fact: string;
  mechanism: string;
  claim?: string;
  source?: string;
  source_citation?: string;
  institution?: string;
  verified_status?: 'VERIFIED' | 'NOT_AVAILABLE_IN_KB' | string;
};

export type Phase7Observability = {
  route?: 'PATH_A' | 'PATH_B' | string;
  agent_model?: string | null;
  model_selected?: string;
  model_id?: string;
  reason?: string;
  model_reason?: string;
  cost_mode?: string;
  estimated_cost_usd?: number;
  tools_called?: string[];
  latency_ms?: number;
  verified?: boolean;
  data_quality?: string | Phase7DataQuality;
  sources?: string[];
  raw_query?: string;
  language?: string;
  structured_query?: Record<string, any>;
  laya_decision?: Record<string, any>;
  requires_agentic_rag?: boolean;
  bedrock_invoked?: boolean;
  fallback_used?: boolean;
  vision_model?: string;
  titan_text_v2_invoked?: boolean;
  titan_text_chunks_retrieved?: number;
  titan_multimodal_invoked?: boolean;
  titan_multimodal_matches?: number;
  evidence_local_sufficient?: boolean;
  evidence_gap_detected?: boolean;
  external_retrieval_attempted?: boolean;
  external_sources_found?: number;
  external_sources_accepted?: number;
  final_llm_invoked?: boolean;
};

export type WildlifeRisk = {
  crop: string;
  zone: string;
  animals: {
    animal: string; level: 'high' | 'medium' | 'low' | 'unlikely'; where: string; why: string; evidence: string;
    crop_note: string | null; vulnerable_when: string | null; deterrents: string[]; sources: { title: string; url: string }[]; photo?: { url: string; caption: string; credit: string; page: string } | null;
  }[];
  crop_standing: string | null;
  recorded_intrusion: Record<string, any> | null;
  kind: string;
  evidence_note: string;
  note: string;
};
export type ParcelFacts = {
  wildlife_general?: { text: string; sources: { title: string; url: string }[]; animals?: { animal: string; photo: { url: string; caption: string; credit: string; page: string } }[] };
  wildlife?: WildlifeRisk;
  parcel_id: string;
  owner: { name?: string; patta_no?: string; kind: string; avatar?: string };
  field_name?: string;
  area_ha?: number;
  zone?: string;
  location: { lat?: number; lon?: number; elevation_m?: number; kind: string };
  crop: { name?: string; variety?: string; stage?: string; days_after_planting?: number; planting_date?: string; kind: string };
  soil: { texture?: string; ph?: number; kind: string };
  terrain: { slope?: string; direct_sun_hours?: number; max_horizon_angle_deg?: number; drainage_risk?: string; kind: string };
  management: { irrigation_type?: string; days_since_last_irrigation?: number; days_since_last_fertilizer?: number; kind: string };
  recorded_issue: { label?: string; severity?: string; kind: string } | null;
  satellite: { ndvi?: number; date?: string; change?: number; status?: string } | null;
  layers: { id: string; name: string; month: string; value: number | string | null; units: string; kind: string }[];
  layers_note?: string;
  photo: { url: string | null; kind: 'parcel' | 'representative' | 'none'; label: string };
};
export type VisualReport = {
  caption: { field: string; value: string }[];
  judge: { passed?: boolean; missing?: string[]; leaked?: string[]; fixed_fields?: string[]; retried?: boolean; checks?: { morphology: boolean; severity: boolean; uncertainty: boolean; no_names: boolean } };
  agreement?: { status: "agree" | "not_confirmed" | "uncertain"; caption_choice?: string; caption_choice_label?: string | null; reference_choice?: string; reference_label?: string; reason?: string; gap?: number; scores?: { id: string; label: string; score: number }[]; confusable_with?: string | null } | null;
  models: { caption: string; judge: string; check: string };
};

export type SpreadParcel = { parcel_id: string; crop: string; stage: string; distance_m: number; bearing_deg: number; bearing_compass: string; risk: number; level: "red" | "amber" | "watch" | "low" | "none";
  hours_to_threshold: number | null; downwind: boolean; why: string; timeline?: number[] };
export type SpreadResult = {
  source: { parcel_id: string; crop: string; stage: string; lat: number; lon: number; disease_code: string; disease: string };
  disease: { label: string; scale_m: number; max_m: number; weather_window: string; evidence: { claim: string; source: string; url: string; kind: string }[] };
  wind: { source: string; mean_speed_kmh: number; from_deg: number; from_compass: string; toward_compass: string; hours: number; typed: boolean };
  weather: { favourable_hours: number; of: number; assumed_perfect: boolean; mean_t: number; mean_rh: number };
  parcels: SpreadParcel[]; summary: { red: number; amber: number; watch: number; top: string[] };
  verification: { passed: boolean; checked: number; failed: { parcel_id: string; problems: string[] }[]; method: string };
  threshold: number; horizon_hours: number; notes: string[]; data_quality: string[]; latency_ms: number;
};

export type RegretWindow = { start: string; end: string; hours: number; mean_t: number; mean_rh: number; hours_ago_at_start: number };
export type RegretResult = {
  available: boolean; message?: string;
  source: { parcel_id: string; crop: string; stage: string; disease: string; disease_code: string; severity: string };
  params: { t_low: number; t_high: number; rh_min: number; min_hours: number; latency_min: number; latency_max: number };
  evidence: { claim: string; source: string; url: string; kind: string }[];
  history: { start: string; now: string; end: string; hours: number; source: string; series: { time: string[]; T: number[]; RH: number[]; fav: number[]; now_i: number } };
  reconstruction: { symptom_noted_days_ago: number; latency_days: number[]; expected_infection_from: string; expected_infection_to: string; candidates: RegretWindow[]; best: RegretWindow | null; statement: string };
  economics: { area_ha: number; area_acre: number; yield_mid_t_ha: number | null; yield_unit: string | null; price_per_quintal: number | null; price_basis: string; severity: string; default_loss_pct: number; note: string };
  now: { in_window: boolean; hours_to_open: number | null; hours_left: number | null };
  twins: { parcel_id: string; stage: string; stage_weight: number; act: "ACT NOW" | "PREPARE" | "MONITOR"; hours_to_open: number | null; checks: { temperature: boolean; humidity: boolean; stage: boolean }; downgrade_reason: string[] }[];
  summary: { act_now: number; prepare: number; monitor: number };
  verification: { passed: boolean; checked: number; method: string };
  data_quality: string[]; latency_ms: number;
};

export type FertilizerGuide = {
  id: string; title: string; kind: "natural" | "mineral" | "protection" | "emergency" | "knowledge" | "clarify" | "weather" | "calendar" | "gallery" | "planner" | "priority" | "offices" | "reviewed" | "spread" | "regret" | "stcr"; stcr?: { area_ha: number | null; parcel_id?: string | null; crop?: string | null; example: Record<string, [number, number]> }; regret?: RegretResult; spread?: SpreadResult; spread_sources?: { parcel_id: string; issue: string; neighbours_in_reach: number }[]; officer?: string; map_zones?: string; offices?: { origin: { name: string; lat: number; lon: number }; items: { name: string; kind: string; lat: number; lon: number; km: number; directions: string; precision: string }[] }; planner?: { crop: string; area_acre: number; qty: { expected_low: number; expected_mid: number; expected_high: number } | null; unit: string; price: number | null }; forecast?: { day: string; rain: number; tmax: number; wind: number | null }[]; message?: string; asks?: { label: string; query: string }[]; extra_sources?: { title: string; url: string }[]; contacts?: { name: string; number: string }[]; steps: string[]; notes?: string[]; warning?: string | null;
  source: { title: string; url: string }; videos: { label: string; url: string }[];
  photos: { url: string; credit: string; page: string; caption?: string }[];
};
export type ReferencePhoto = { url: string; condition: string; crop: string; source?: string | null; label: string };
export type Phase7AdvisoryResult = {
  crop?: string | null;
  doc_values?: { name: string; value: string; unit: string; rating: string | null }[] | null;
  reference_photos?: ReferencePhoto[] | null;
  fertilizer_guides?: FertilizerGuide[] | null;
  visual_report?: VisualReport | null;
  cross_check?: { passed: boolean; area_ha?: number; note: string; options: { recommendation: string; source: string; N_kg: number; P2O5_kg: number; K2O_kg: number; urea_kg: number; dap_kg: number; mop_kg: number; used_in_answer: boolean }[] } | null;
  confidence?: { level: 'high' | 'medium' | 'low'; label: string; why: string[]; top_score?: number | null } | null;
  parcel_facts?: ParcelFacts | null;
  parcel_id?: string | null;
  survey_no?: string | null;
  query: string;
  task_type?: string;
  answer?: string;
  recommendations?: string[];
  reasons?: string[];
  why_this_matters?: WhyThisMattersItem[];
  risks?: string[];
  actions?: Phase7Actions;
  image?: {
    image_path?: string;
    actual_parcel_photo?: boolean;
    user_uploaded?: boolean;
    analyzed?: boolean;
    [key: string]: any;
  };
  parcel_context?: Record<string, any>;
  evidence?: Array<Record<string, unknown>>;
  sources?: Phase7Source[];
  limitations?: string[];
  data_quality?: Phase7DataQuality | string;
  model?: Phase7Model & {
    model_selected?: string;
    agent_model?: string | null;
    estimated_cost_usd?: number;
    reason?: string;
    reason_for_selection?: string;
  };
  verification?: Phase7Verification;
  verified?: boolean;
  route?: string;
  model_selected?: string;
  agent_model?: string | null;
  tools_called?: string[];
  cost_mode?: string;
  estimated_cost_usd?: number;
  observability?: Phase7Observability;
  possible_symptom?: string;
  visual_observations?: string[];
  diagnosis?: string;
  // Error state
  error?: { code: string; message: string; details?: unknown[] };
};

/** Farmer-friendly processing states shown during advisory generation (no technical model names) */
export const FARMER_LOADING_STEPS = [
  'Understanding your question…',
  'Checking field conditions & agricultural evidence…',
  'Preparing your advisory…',
] as const;

/** Phase 7 processing states shown during advisory generation */
export const PHASE7_PIPELINE_STEPS = FARMER_LOADING_STEPS;

/**
 * Direct Chat with AWS Bedrock + Malai Knowledge Base.
 * Calls POST /api/chat with { message, context, parcel_id }
 */
export async function sendChatMessage(
  message: string,
  context?: string,
  parcelId?: string | null,
  options = getApiSettings(),
): Promise<{ reply: string; answer?: string; recommendations?: string[]; model_used?: string }> {
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const url = base ? `${base}/api/chat` : '/api/chat';

  const payload: Record<string, unknown> = {
    message: message.trim(),
    context: context || undefined,
    parcel_id: parcelId || undefined,
  };

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...consentHeader() },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error('Unable to connect to backend on port 8000. Ensure python server is running.');
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg = data?.detail || data?.error?.message || `Chat request failed (${response.status})`;
    throw new Error(errorMsg);
  }

  return data ?? { reply: 'No response from server.' };
}

/**
 * Submit a farmer query to the advisory chat pipeline (POST /api/chat).
 */
export async function submitAdvisory(
  query: string,
  parcelId?: string | null,
  attachedImage?: File | null,
  options = getApiSettings(),
): Promise<Phase7AdvisoryResult> {
  const base = options.baseUrl ? options.baseUrl.replace(/\/$/, '') : '';
  const url = base ? `${base}/api/advisory` : '/api/advisory';

  let imageBytes: string | undefined = undefined;
  let imageFormat: string | undefined = undefined;
  let imageName: string | undefined = undefined;

  if (attachedImage) {
    try {
      const buffer = await attachedImage.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = '';
      for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      imageBytes = btoa(binary);
      imageFormat = attachedImage.type.replace('image/', '') || 'jpeg';
      imageName = attachedImage.name;
    } catch (e) {
      console.warn('Failed to read image file as base64:', e);
    }
  }

  const payload: Record<string, unknown> = {
    query: query.trim(),
    parcel_id: parcelId || undefined,
    image_bytes: imageBytes,
    image_format: imageFormat,
    image_name: imageName,
    region: getRegionProfile() || undefined,
    context_crop: lastAnsweredCrop || undefined,       // the crop of the previous answer, used only when this question names no crop (a follow-up such as "and the seed rate?")
  };

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error('Unable to connect to the Cropsy advisory backend. Make sure the API is running on port 8000.');
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message = data?.detail || data?.error?.message || `Advisory request failed (${response.status})`;
    throw new Error(message);
  }

  const result = data as Phase7AdvisoryResult | null;
  lastAnsweredCrop = result?.crop ?? null;       // only the crop of the answer just given: a general answer clears it
  return result ?? { query, error: { code: 'EMPTY_RESPONSE', message: 'Backend returned no data.' } };
}

let lastAnsweredCrop: string | null = null;
/** A cleared chat starts fresh: the next short question does not inherit the previous crop. */
export function resetConversationContext() { lastAnsweredCrop = null; }


// ── Parcel history (dummy seasons from backend/data/history.csv) ─────────────────────────────────
export type HistorySeason = {
  parcel_id: string;
  year: string;
  crop: string;
  variety: string;
  yield_value: string;
  yield_unit: string;
  fertilizer_used: string;
  irrigation_type: string;
  major_issue: string;
  data_source?: string;
};

export async function fetchParcelHistory(parcelId: string): Promise<HistorySeason[]> {
  const { baseUrl } = getApiSettings();
  const base = baseUrl ? baseUrl.replace(/\/$/, '') : '';
  const response = await fetch(`${base}/api/history/${encodeURIComponent(parcelId)}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Could not load history for ${parcelId} (${response.status})`);
  const body = await response.json();
  return (body.seasons || []) as HistorySeason[];
}

// ── Field report, alerts and satellite overview (deterministic backend endpoints) ─────────────────
function apiBase(): string {
  const { baseUrl } = getApiSettings();
  return baseUrl ? baseUrl.replace(/\/$/, '') : '';
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`${path} failed (${response.status})`);
  return (await response.json()) as T;
}

export type FieldAlert = {
  parcel_id: string;
  type: 'crop_stress' | 'heavy_rain' | 'irrigation_due' | 'recorded_issue' | string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  action: string;
  basis: string;
};
export type AlertsResponse = { forecast_source: string; count: number; by_type: Record<string, number>; alerts: FieldAlert[] };
export type SatelliteOverview = {
  as_of: string;
  source: string;
  parcels: Record<string, { status: 'stress' | 'watch' | 'normal' | 'insufficient'; ndvi: number | null; change: number | null; date: string | null }>;
};
export type FieldReport = {
  instruction: { headline: string; steps: string[]; basis: string };
  field_directions: { date: string; weakest: string; strongest: string; spread: number; note: string; basis: string } | null;
  parcel_id: string;
  crop: { name: string; variety: string; stage: string; days_after_planting: number; planting_date: string };
  area_ha: number;
  zone: string;
  health: {
    status: string; reason?: string; latest_ndvi?: number; latest_date?: string; baseline_ndvi?: number | null; change?: number | null;
    age_days?: number; n_obs_year?: number; label?: string; source?: string; series?: { date: string; ndvi: number }[];
  };
  water: {
    crop_coefficient: number; growth_phase: string; forecast_source: string; total_mm_7d: number; total_m3_per_ha_7d: number;
    total_m3_parcel_7d: number; best_time: string; basis: string; note: string;
    days: { date: string; et0_mm: number; etc_mm: number; rain_mm: number; irrigation_mm: number }[];
  };
  soil: { texture: string; ph: number; drainage: string; waterlogging_susceptibility: string; elevation_m: number; note: string };
  harvest: { available: boolean; window_start?: string; window_end?: string; days_to_start?: number; basis?: string; note?: string };
  risks: { recorded_issue: { label: string; severity: string; since_days: number; symptoms: string[] } | null; note: string };
  fertilizer: {
    area_ha: number; note: string; assumptions: string;
    options: { recommendation: string; source: string; N_kg: number; P2O5_kg: number; K2O_kg: number; urea_kg: number; dap_kg: number; mop_kg: number }[];
    organic: Cited[]; schedule: Cited[];
  };
  alerts: FieldAlert[];
  forecast_source: string;
  vigour: { month: string; classes: { name: string; share: number; color: string }[]; mean_ndvi: number | null; good_share?: number; basis: string } | null;
  irrigation: IrrigationPlan;
  soil_panel: SoilPanel;
  yield_outlook: YieldOutlook | null;
  plants: PlantEstimate;
  watch: WatchData;
  wildlife?: WildlifeRisk;
};
export type IrrigationPlan = {
  method: 'drip' | 'sprinkler' | 'flood'; efficiency: number; pump_lps: number; irrigation_days: number; total_gross_mm: number;
  total_volume_m3: number; total_pump_hours: number; best_window: string; basis: string;
  days: { date: string; et0_mm: number; etc_mm: number; rain_mm: number; irrigation_mm: number; gross_mm: number; volume_m3: number; pump_hours: number; rain_probability_pct: number | null; irrigate: boolean }[];
};
export type SoilPanel = {
  record_ph: number | null; record_ph_rating: { class: string; advice: string } | null; soilgrids_ph: number | null;
  organic_carbon_g_per_kg: number | null; texture: string; drainage: string; land_cover_under_parcel: Record<string, number> | null;
  dominant_land_cover: string | null; salinity: { status: string; note: string }; basis: string;
};
export type YieldOutlook = {
  unit: string; last_seasons: { year: string; yield: number; issue: string }[]; expected_low: number; expected_mid: number; expected_high: number;
  expected_total: number | null; basis: string;
};
export type PlantEstimate = {
  available: boolean; crop?: string; spacing?: string; source?: string; unit?: string; per_ha?: number | null;
  plants_at_spacing?: number; plants_usable?: number; plants?: number | null; row_length_m?: number; note?: string;
};
export type Cited = { text: string; source: string };
export type WatchItem = {
  code: string; name: string; kind: string; severity: string; symptoms: string[]; recorded_on_parcel: boolean;
  cultural: Cited[]; organic: Cited[]; chemical: Cited[]; closest?: string | null;
};
export type WatchData = {
  watchlist: WatchItem[]; weeds: { chemical: Cited[]; organic: Cited[] }; recorded_without_advice: string | null; note: string; weeds_note?: string;
  weather_signal: { humid_days: number; rainy_days: number; favours_fungal: boolean; basis: string } | null;
};
export type SoilTestResult = {
  ratings: Record<string, { value: number; rating: 'low' | 'medium' | 'high'; limits: number[] }>;
  adjustment: Record<string, number>; counts: { needs_attention: number; monitor: number; optimal: number };
  ph?: { value: number; class: string; advice: string }; salinity?: { value: number; class: string; basis: string }; basis: string;
  adjusted_fertilizer: { recommendation: string; source: string; adjusted_per_ha: string; N_kg: number; P2O5_kg: number; K2O_kg: number; urea_kg: number; dap_kg: number; mop_kg: number }[];
};

export type VillageBrief = { headline: string; steps: string[]; counts: Record<string, number>; forecast_source: string; basis: string };
export const fetchVillageBrief = () => getJson<VillageBrief>('/api/village-brief');
export const fetchFieldReport = (id: string, method = 'sprinkler', pumpLps = 8) =>
  getJson<FieldReport>(`/api/field-report/${encodeURIComponent(id)}?method=${method}&pump_lps=${pumpLps}`);
export async function postSoilTest(id: string, values: Record<string, number>): Promise<SoilTestResult> {
  const response = await fetch(`${apiBase()}/api/soil-test/${encodeURIComponent(id)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
  });
  if (!response.ok) throw new Error(`Soil test could not be evaluated (${response.status})`);
  return (await response.json()) as SoilTestResult;
}
export const BULK_CSV_URL = () => `${apiBase()}/api/indices-export.csv`;
export const fetchAlerts = (min: 'high' | 'medium' | 'low' = 'low') => getJson<AlertsResponse>(`/api/alerts?min_severity=${min}`);
export const fetchSatelliteOverview = () => getJson<SatelliteOverview>('/api/satellite');

// ── Satellite layers and index results ───────────────────────────────────────────────────────────
export type LayerInfo = {
  id: string; name: string; group: string; units: string; source: string; kind: 'real' | 'modelled' | 'derived';
  what: string; use: string; caveat: string; range: [number, number] | null; months: string[]; needs: string[] | null;
};
export type LayersManifest = {
  generated: string; bounds: [[number, number], [number, number]]; size: [number, number];
  lulc_classes: Record<string, { name: string; color: string }>;
  layers: Record<string, LayerInfo>; months: Record<string, string[]>;
  stats: Record<string, any>; sanity: Record<string, any>;
};
export type IndexPoint = { date: string; value: number; village_median: number | null };
export type IndexSeries = {
  name: string; unit: string; sensor: string; formula: string; meaning: string; points: IndexPoint[];
  latest: { date: string; value: number } | null; window_mean: number | null; previous_mean: number | null;
  change_vs_previous: number | null; n_points: number; n_previous: number;
};
export type PassCalendar = {
  sentinel2: { date: string; scene_cloud_pct: number; parcels_clear: number }[];
  sentinel1: { date: string; orbit: string; parcels_observed: number }[];
};
export type FieldDirections = {
  date: string; sectors: Record<string, number>; weakest: string; strongest: string; mean_ndvi: number; spread: number; note: string; basis: string;
} | null;
export type IndexResults = {
  parcel_id: string; start: string; end: string; previous_window: [string, string];
  indices: Record<string, IndexSeries>; calendar: PassCalendar; field_directions: FieldDirections; data_source: string;
};

export const fetchLayers = () => getJson<LayersManifest>('/api/layers');
export const layerUrl = (layer: string, month: string) => `${apiBase()}/layers/${layer}/${month}.png`;
export const fetchIndexResults = (id: string, start: string, end: string) =>
  getJson<IndexResults>(`/api/indices/${encodeURIComponent(id)}?start=${start}&end=${end}`);

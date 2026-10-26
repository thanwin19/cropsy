import { describe, it, expect, vi, beforeEach } from 'vitest';
import { submitAdvisory, type Phase7AdvisoryResult } from './cropsy-api';

describe('Common Advisory Interface (submitAdvisory API client)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('successfully handles a PATH_A response (deterministic / model NONE)', async () => {
    const mockPathAResult: Phase7AdvisoryResult = {
      query: 'nel payirukku urea eppo podanum?',
      answer: 'Apply urea in split doses at tillering stage.',
      recommendations: ['Split urea into 3 equal applications', 'Irrigate before application'],
      actions: {
        immediate: ['Drain excess standing water before urea broadcasting'],
        next_24_hours: ['Apply 25 kg/acre urea evenly'],
        next_3_to_7_days: ['Maintain light irrigation depth of 2-3 cm'],
        watch_for: ['Leaf color chart reading'],
      },
      risks: ['Excessive nitrogen during cloudy weather promotes blast incidence'],
      verified: true,
      route: 'PATH_A',
      model_selected: 'NONE',
      agent_model: null,
      data_quality: 'verified',
      tools_called: ['crop_knowledge', 'soil_knowledge', 'agronomy_nutrient_management'],
      cost_mode: 'budget',
      estimated_cost_usd: 0.0,
      observability: {
        route: 'PATH_A',
        model_selected: 'NONE',
        agent_model: null,
        cost_mode: 'budget',
        estimated_cost_usd: 0.0,
        tools_called: ['crop_knowledge', 'soil_knowledge', 'agronomy_nutrient_management'],
        verified: true,
        data_quality: 'verified',
        latency_ms: 12.5,
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPathAResult,
    });

    const result = await submitAdvisory('nel payirukku urea eppo podanum?');

    expect(fetch).toHaveBeenCalledWith('/api/advisory', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    }));

    const calledBody = JSON.parse((fetch as any).mock.calls[0][1].body);
    expect(calledBody.query).toBe('nel payirukku urea eppo podanum?');
    expect(result.verified).toBe(true);
    expect(result.route).toBe('PATH_A');
    expect(result.model_selected).toBe('NONE');
    expect(result.estimated_cost_usd).toBe(0.0);
    expect(result.actions?.immediate?.length).toBeGreaterThan(0);
  });

  it('successfully handles a PATH_B response (Nova Micro agent + final model)', async () => {
    const mockPathBResult: Phase7AdvisoryResult = {
      parcel_id: 'TM-01',
      query: 'TM-01 rice + blast + soil + rain + spray',
      answer: 'Advisory for TM-01 (Disease Diagnosis): Detected blast risk on registered Rice parcel.',
      recommendations: ['Spray tricyclazole 75 WP at 0.6 g/L', 'Ensure proper spacing'],
      actions: {
        immediate: ['Inspect lower leaf sheaths for spindle-shaped blast lesions'],
        next_24_hours: ['Withhold foliar spray if precipitation forecast exceeds 70%'],
        next_3_to_7_days: ['Apply prophylactic bio-agent Pseudomonas fluorescens at 10 g/L'],
        watch_for: ['Neck blast symptoms at heading stage'],
      },
      risks: ['High relative humidity above 90% accelerates sporulation'],
      verified: true,
      route: 'PATH_B',
      agent_model: 'Nova Micro',
      model_selected: 'Ministral 8B',
      data_quality: 'verified',
      tools_called: ['knowledge_tool', 'weather_tool', 'gis_parcel_tool'],
      cost_mode: 'budget',
      estimated_cost_usd: 0.00045,
      observability: {
        route: 'PATH_B',
        agent_model: 'Nova Micro',
        model_selected: 'Ministral 8B',
        cost_mode: 'budget',
        estimated_cost_usd: 0.00045,
        tools_called: ['knowledge_tool', 'weather_tool', 'gis_parcel_tool'],
        verified: true,
        data_quality: 'verified',
        latency_ms: 380.0,
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPathBResult,
    });

    const result = await submitAdvisory('TM-01 rice + blast + soil + rain + spray', 'TM-01');

    const calledBody = JSON.parse((fetch as any).mock.calls[0][1].body);
    expect(calledBody.query).toBe('TM-01 rice + blast + soil + rain + spray');
    expect(calledBody.parcel_id).toBe('TM-01');
    expect(result.verified).toBe(true);
    expect(result.route).toBe('PATH_B');
    expect(result.agent_model).toBe('Nova Micro');
    expect(result.model_selected).toBe('Ministral 8B');
    expect(result.observability?.tools_called).toContain('weather_tool');
  });

  it('correctly encodes and submits image advisory request', async () => {
    const mockImageResult: Phase7AdvisoryResult = {
      query: 'இந்த இலையில் என்ன பிரச்சனை?',
      answer: 'Leaf blast diagnosis from field photograph.',
      recommendations: ['Apply fungicide spray after rain stops'],
      verified: true,
      route: 'PATH_A',
      model_selected: 'Nova Lite',
      observability: {
        route: 'PATH_A',
        model_selected: 'Nova Lite',
        reason: 'multimodal_image_analysis',
        verified: true,
        data_quality: 'verified',
        estimated_cost_usd: 0.0018,
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockImageResult,
    });

    // Mock File object
    const fakeFile = {
      name: 'leaf_photo.jpg',
      type: 'image/jpeg',
      arrayBuffer: async () => new Uint8Array([255, 216, 255, 224]).buffer,
    } as unknown as File;

    const result = await submitAdvisory('இந்த இலையில் என்ன பிரச்சனை?', null, fakeFile);

    const calledBody = JSON.parse((fetch as any).mock.calls[0][1].body);
    expect(calledBody.query).toBe('இந்த இலையில் என்ன பிரச்சனை?');
    expect(calledBody.image_format).toBe('jpeg');
    expect(calledBody.image_name).toBe('leaf_photo.jpg');
    expect(typeof calledBody.image_bytes).toBe('string');
    expect(result.model_selected).toBe('Nova Lite');
  });

  it('handles backend API errors gracefully with descriptive error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({
        error: {
          code: 'ADVISORY_ERROR',
          message: 'Bedrock converse connection timeout',
        },
      }),
    });

    await expect(submitAdvisory('rice leaf yellow')).rejects.toThrow('Bedrock converse connection timeout');
  });

  it('handles network failure (backend unreachable) gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(submitAdvisory('Should I fertilize?')).rejects.toThrow(/Make sure the API is running on port 8000/);
  });

  it('provides farmer-friendly loading states without exposing raw model names', async () => {
    const { FARMER_LOADING_STEPS } = await import('./cropsy-api');

    expect(FARMER_LOADING_STEPS.length).toBeGreaterThanOrEqual(3);
    expect(FARMER_LOADING_STEPS[0]).toBe('Understanding your question…');
    expect(FARMER_LOADING_STEPS[1]).toBe('Checking field conditions & agricultural evidence…');
    expect(FARMER_LOADING_STEPS[2]).toBe('Preparing your advisory…');

    // Crucial requirement: No technical model names in farmer loading state!
    for (const step of FARMER_LOADING_STEPS) {
      expect(step).not.toContain('Nova');
      expect(step).not.toContain('Ministral');
      expect(step).not.toContain('Qwen');
      expect(step).not.toContain('LAYA');
      expect(step).not.toContain('Bedrock');
    }
  });

  it('validates observability contract for admin/debug panel on PATH_B queries', async () => {
    const mockComplexResult: Phase7AdvisoryResult = {
      parcel_id: 'TM-01',
      query: 'TM-01 rice + blast + soil + rain + spray',
      answer: 'Complex multi-factor synthesis',
      verified: true,
      route: 'PATH_B',
      agent_model: 'Nova Micro',
      model_selected: 'Ministral 8B',
      data_quality: 'verified',
      tools_called: ['knowledge_tool', 'weather_tool', 'gis_parcel_tool'],
      cost_mode: 'budget',
      estimated_cost_usd: 0.00045,
      observability: {
        route: 'PATH_B',
        agent_model: 'Nova Micro',
        model_selected: 'Ministral 8B',
        cost_mode: 'budget',
        estimated_cost_usd: 0.00045,
        tools_called: ['knowledge_tool', 'weather_tool', 'gis_parcel_tool'],
        verified: true,
        data_quality: 'verified',
        latency_ms: 380.0,
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockComplexResult,
    });

    const res = await submitAdvisory('TM-01 rice + blast + soil + rain + spray', 'TM-01');
    const obs = res.observability!;

    expect(obs.route).toBe('PATH_B');
    expect(obs.agent_model).toBe('Nova Micro');
    expect(obs.model_selected).toBe('Ministral 8B');
    expect(obs.verified).toBe(true);
    expect(obs.data_quality).toBe('verified');
    expect(obs.estimated_cost_usd).toBe(0.00045);
    expect(obs.tools_called).toEqual(expect.arrayContaining(['weather_tool', 'knowledge_tool']));
    expect(obs.latency_ms).toBeGreaterThan(0);
  });
});

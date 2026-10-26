/**
 * terrainShadowWorker.ts
 *
 * Web Worker wrapper around the shared engine in ../lib/terrainShadow.ts.
 *
 * Protocol:
 *   1. { type: "init", dispDem, dispMeta, fullDem?, fullMeta? }   -> sent ONCE (DEM is cached here)
 *   2. { type: "job",  jobId, sunAlt, sunAz, coarse }              -> cheap, sent on every slider move
 *
 * Legacy messages that carry dispDem inside the job payload are still accepted.
 */
import {
  buildDemSet,
  computeShadowMask,
  type DemGridMeta,
  type DemSet,
} from "../lib/terrainShadow";

export type WorkerDemGridMeta = DemGridMeta;

export interface ShadowInitPayload {
  type: "init";
  dispDem: Int16Array;
  dispMeta: DemGridMeta;
  fullDem?: Int16Array;
  fullMeta?: DemGridMeta;
}

export interface ShadowJobPayload {
  type?: "job";
  jobId: number;
  sunAlt: number; // apparent (refracted) altitude, degrees
  sunAz: number; // degrees, 0 = N
  coarse: boolean;
  // legacy / optional: include DEM in the job itself
  dispDem?: Int16Array;
  dispMeta?: DemGridMeta;
  fullDem?: Int16Array;
  fullMeta?: DemGridMeta;
}

let dems: DemSet | null = null;

self.onmessage = (e: MessageEvent<ShadowInitPayload | ShadowJobPayload>) => {
  const msg = e.data;

  if (msg.type === "init") {
    dems = buildDemSet(msg.dispDem, msg.dispMeta, msg.fullDem, msg.fullMeta);
    return;
  }

  const job = msg as ShadowJobPayload;
  if (job.dispDem && job.dispMeta) {
    dems = buildDemSet(job.dispDem, job.dispMeta, job.fullDem, job.fullMeta);
  }
  if (!dems) return;

  const { shadowMask, outWidth, outHeight } = computeShadowMask(dems, job.sunAlt, job.sunAz, job.coarse);
  (self as unknown as Worker).postMessage(
    { jobId: job.jobId, shadowMask, outWidth, outHeight, coarse: job.coarse },
    [shadowMask.buffer],
  );
};

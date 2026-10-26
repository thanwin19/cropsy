/** The farmer's privacy choices, kept only in this browser. */
export type Consent = { decided: boolean; photos: boolean; improve: boolean };

const KEY = "cropsy.consent";

export function getConsent(): Consent {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "null");
    if (v && typeof v === "object") return { decided: Boolean(v.decided), photos: Boolean(v.photos), improve: Boolean(v.improve) };
  } catch {
    /* no storage: treat as not decided */
  }
  return { decided: false, photos: false, improve: false };
}

export function setConsent(c: Consent) {
  try {
    localStorage.setItem(KEY, JSON.stringify(c));
  } catch {
    /* private mode: choices last for this page only */
  }
}

/** Sent with every question: the server only logs unclear questions when this is "yes". */
export const consentHeader = () => ({ "X-Cropsy-Consent": getConsent().improve ? "yes" : "no" });

/** "Delete my data": the server's history, uploads and unclear-questions log, plus everything Cropsy keeps in this browser. */
export async function deleteMyData(base = ""): Promise<boolean> {
  let ok = false;
  try {
    const r = await fetch(`${base.replace(/\/$/, "")}/api/my-data`, { method: "DELETE" });
    ok = r.ok;
  } catch {
    ok = false;
  }
  try {
    Object.keys(localStorage).filter((k) => k.startsWith("cropsy")).forEach((k) => localStorage.removeItem(k));
  } catch {
    /* nothing stored */
  }
  return ok;
}

/** The farmer's location. It only goes to the server inside a question, and it is only written to this browser if the farmer ticks "remember on this device". */
export type RegionProfile = { country?: string; state?: string; district?: string };
const REGION_KEY = "cropsy.region";
let sessionRegion: RegionProfile | null = null;

export function getRegionProfile(): RegionProfile | null {
  if (sessionRegion) return sessionRegion;
  try {
    const v = JSON.parse(localStorage.getItem(REGION_KEY) || "null");
    if (v && typeof v === "object" && (v.state || v.district || v.country)) return v as RegionProfile;
  } catch {
    /* nothing saved */
  }
  return null;
}

export function setRegionProfile(r: RegionProfile | null, remember: boolean) {
  sessionRegion = r;
  try {
    if (r && remember) localStorage.setItem(REGION_KEY, JSON.stringify(r));
    else localStorage.removeItem(REGION_KEY);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}

export const regionIsSaved = () => {
  try {
    return localStorage.getItem(REGION_KEY) !== null;
  } catch {
    return false;
  }
};

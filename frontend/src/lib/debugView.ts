/** The development view shows verifier notes, the debug panel, sources and the plain-model comparison. Turn it on once with ?debug=1 (kept on this device); ?debug=0 turns it off. */
export function isDebugView(): boolean {
  try {
    const q = new URLSearchParams(window.location.search).get("debug");
    if (q === "1") localStorage.setItem("cropsy.debug", "1");
    if (q === "0") localStorage.removeItem("cropsy.debug");
    return localStorage.getItem("cropsy.debug") === "1";
  } catch {
    return false;
  }
}

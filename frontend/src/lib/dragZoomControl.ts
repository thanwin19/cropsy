import type L from "leaflet";

/**
 * Make a Leaflet map's zoom buttons draggable. Press and drag the +/- bar anywhere (a plain click still zooms); the position is
 * kept per map in localStorage and clamped inside the map. Call right after the map is created.
 */
export function makeZoomDraggable(map: L.Map, storageKey: string) {
  const bar = map.getContainer().querySelector<HTMLElement>(".leaflet-control-zoom");
  if (!bar) return;
  let dx = 0, dy = 0;
  try {
    const v = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (v && Number.isFinite(v.dx) && Number.isFinite(v.dy)) { dx = v.dx; dy = v.dy; }
  } catch { /* storage unavailable */ }
  const apply = () => { bar.style.transform = dx || dy ? `translate(${dx}px, ${dy}px)` : ""; };
  const clamp = () => {
    const c = map.getContainer().getBoundingClientRect();
    const r = bar.getBoundingClientRect();
    const mx = r.left - dx, my = r.top - dy; // untransformed position
    dx = Math.min(Math.max(dx, c.left + 4 - mx), c.right - 4 - (mx + r.width));
    dy = Math.min(Math.max(dy, c.top + 4 - my), c.bottom - 4 - (my + r.height));
  };
  apply();
  bar.style.cursor = "grab";
  bar.title = "Drag to move";
  let start: { x: number; y: number; ox: number; oy: number; moved: boolean } | null = null;
  let swallow = false;
  bar.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    start = { x: e.clientX, y: e.clientY, ox: dx, oy: dy, moved: false };
    e.stopPropagation();
  });
  bar.addEventListener("pointermove", (e) => {
    if (!start) return;
    const mx = e.clientX - start.x, my = e.clientY - start.y;
    if (!start.moved) {
      if (Math.hypot(mx, my) < 4) return;
      start.moved = true;
      bar.setPointerCapture(e.pointerId);
      bar.style.cursor = "grabbing";
    }
    dx = start.ox + mx; dy = start.oy + my;
    clamp();
    apply();
  });
  const end = (e: PointerEvent) => {
    if (start?.moved) {
      swallow = true;
      setTimeout(() => { swallow = false; }, 0);
      try { localStorage.setItem(storageKey, JSON.stringify({ dx, dy })); } catch { /* ignore */ }
      try { bar.releasePointerCapture(e.pointerId); } catch { /* ignore */ }
    }
    bar.style.cursor = "grab";
    start = null;
  };
  bar.addEventListener("pointerup", end);
  bar.addEventListener("pointercancel", end);
  bar.addEventListener("click", (e) => { if (swallow) { e.stopPropagation(); e.preventDefault(); } }, true);
  bar.addEventListener("dblclick", (e) => e.stopPropagation());
}

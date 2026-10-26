import { useCallback, useEffect, useRef, useState } from "react";
import type React from "react";

/**
 * Make any absolutely-positioned floating element draggable without changing how it is placed.
 *
 * The element keeps its own CSS position (left/right/top/bottom/centering); the drag is added on top through the CSS `transform`
 * property, which composes with the separate `translate` property Tailwind v4 uses for `-translate-x-1/2` centring.
 * A click that ends a drag is swallowed, so buttons keep working when tapped. Offsets are clamped to the offset parent and remembered
 * per `storageKey` in localStorage. Inputs, selects and anything marked data-nodrag never start a drag.
 *
 *   const d = useDraggable<HTMLDivElement>("cropsy.drag.legend");
 *   <div ref={d.ref} {...d.bind} style={d.style} ...>
 */
type Off = { dx: number; dy: number };

const read = (key: string): Off => {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "null");
    if (v && Number.isFinite(v.dx) && Number.isFinite(v.dy)) return { dx: v.dx, dy: v.dy };
  } catch { /* storage unavailable */ }
  return { dx: 0, dy: 0 };
};

export function useDraggable<T extends HTMLElement>(storageKey: string, threshold = 4) {
  const ref = useRef<T>(null);
  const [off, setOff] = useState<Off>(() => read(storageKey));
  const offRef = useRef(off);
  offRef.current = off;
  const drag = useRef<{ x: number; y: number; ox: number; oy: number; moved: boolean } | null>(null);
  const swallowClick = useRef(false);

  /** Keep the element inside its offset parent (4px margin) given a candidate offset. */
  const clamp = useCallback((dx: number, dy: number): Off => {
    const el = ref.current;
    const parent = el?.offsetParent as HTMLElement | null;
    if (!el || !parent) return { dx, dy };
    const r = el.getBoundingClientRect();
    const p = parent.getBoundingClientRect();
    const shiftX = dx - offRef.current.dx;
    const shiftY = dy - offRef.current.dy;
    let nx = dx, ny = dy;
    if (r.left + shiftX < p.left + 4) nx += p.left + 4 - (r.left + shiftX);
    if (r.right + shiftX > p.right - 4) nx -= r.right + shiftX - (p.right - 4);
    if (r.top + shiftY < p.top + 4) ny += p.top + 4 - (r.top + shiftY);
    if (r.bottom + shiftY > p.bottom - 4) ny -= r.bottom + shiftY - (p.bottom - 4);
    return { dx: Math.round(nx), dy: Math.round(ny) };
  }, []);

  // pull a saved position back inside the map if the window is now smaller
  useEffect(() => {
    const fit = () => setOff((o) => {
      const c = clamp(o.dx, o.dy);
      return c.dx === o.dx && c.dy === o.dy ? o : c;
    });
    const t = requestAnimationFrame(fit);
    window.addEventListener("resize", fit);
    return () => { cancelAnimationFrame(t); window.removeEventListener("resize", fit); };
  }, [clamp]);

  const persist = (o: Off) => { try { localStorage.setItem(storageKey, JSON.stringify(o)); } catch { /* ignore */ } };

  const bind = {
    onPointerDown: (e: React.PointerEvent<T>) => {
      if (e.button !== 0) return;
      if ((e.target as HTMLElement).closest("input,select,textarea,a,[data-nodrag]")) return;
      drag.current = { x: e.clientX, y: e.clientY, ox: offRef.current.dx, oy: offRef.current.dy, moved: false };
    },
    onPointerMove: (e: React.PointerEvent<T>) => {
      const d = drag.current;
      if (!d) return;
      const mx = e.clientX - d.x, my = e.clientY - d.y;
      if (!d.moved) {
        if (Math.hypot(mx, my) < threshold) return;
        d.moved = true;
        try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); } catch { /* ignore */ }
      }
      setOff(clamp(d.ox + mx, d.oy + my));
    },
    onPointerUp: (e: React.PointerEvent<T>) => {
      const d = drag.current;
      drag.current = null;
      if (d?.moved) {
        swallowClick.current = true;
        setTimeout(() => { swallowClick.current = false; }, 0);
        persist(offRef.current);
        try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch { /* ignore */ }
      }
    },
    onPointerCancel: () => { drag.current = null; },
    onClickCapture: (e: React.MouseEvent<T>) => {
      if (swallowClick.current) { e.stopPropagation(); e.preventDefault(); }
    },
  };

  // The offset is written with `transform`, so it stacks on top of whatever the element already does with the `translate`
  // property (Tailwind's -translate-x-1/2 centring) instead of replacing it. Nothing is written until the element has moved,
  // so an untouched panel does not become a containing block for fixed-position children.
  const style: React.CSSProperties = {
    ...(off.dx || off.dy ? { transform: `translate(${off.dx}px, ${off.dy}px)` } : {}),
    touchAction: "none",
  };

  const reset = () => { setOff({ dx: 0, dy: 0 }); persist({ dx: 0, dy: 0 }); };
  return { ref, bind, style, reset, moved: off.dx !== 0 || off.dy !== 0 };
}

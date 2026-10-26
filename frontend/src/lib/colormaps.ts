/** Colour palettes as 256-entry lookup tables, interpolated from a few stops (close approximations of the matplotlib/ColorBrewer maps). */

export type Rgb = [number, number, number];
type Stop = [number, string];

const hex = (h: string): Rgb => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];

const STOPS: Record<string, Stop[]> = {
  RdYlGn: [[0, "#a50026"], [0.2, "#f46d43"], [0.4, "#fee08b"], [0.6, "#a6d96a"], [0.8, "#1a9850"], [1, "#006837"]],
  Viridis: [[0, "#440154"], [0.25, "#3b528b"], [0.5, "#21918c"], [0.75, "#5ec962"], [1, "#fde725"]],
  // cividis: designed to look the same to people with red-green colour blindness
  Cividis: [[0, "#00204d"], [0.25, "#414d6b"], [0.5, "#7c7b78"], [0.75, "#bcaf6f"], [1, "#ffea46"]],
  Blues: [[0, "#f7fbff"], [0.25, "#c6dbef"], [0.5, "#6baed6"], [0.75, "#2171b5"], [1, "#08306b"]],
  Greys: [[0, "#f0f0f0"], [1, "#252525"]],
  Terrain: [[0, "#2b6e3e"], [0.25, "#8dbd5a"], [0.5, "#e6dc8c"], [0.75, "#b08968"], [1, "#f5f5f5"]],
  YlOrBr: [[0, "#ffffe5"], [0.25, "#fee391"], [0.5, "#fe9929"], [0.75, "#cc4c02"], [1, "#662506"]],
  // diverging, used for the before/after difference (blue = increase, red = decrease)
  RdBu: [[0, "#b2182b"], [0.25, "#f4a582"], [0.5, "#f7f7f7"], [0.75, "#92c5de"], [1, "#2166ac"]],
};

export const COLORMAP_NAMES = Object.keys(STOPS).filter((k) => k !== "RdBu");

const cache = new Map<string, Rgb[]>();

export function lut(name: string): Rgb[] {
  const hit = cache.get(name);
  if (hit) return hit;
  const stops = (STOPS[name] || STOPS.Viridis).map(([t, c]) => [t, hex(c)] as [number, Rgb]);
  const out: Rgb[] = [];
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    let k = 0;
    while (k < stops.length - 2 && t > stops[k + 1][0]) k++;
    const [t0, c0] = stops[k];
    const [t1, c1] = stops[k + 1];
    const f = Math.min(Math.max((t - t0) / (t1 - t0 || 1), 0), 1);
    out.push([0, 1, 2].map((j) => Math.round(c0[j] + (c1[j] - c0[j]) * f)) as Rgb);
  }
  cache.set(name, out);
  return out;
}

/** A small CSS gradient string for legends. */
export function gradientCss(name: string, steps = 8): string {
  const l = lut(name);
  const parts = Array.from({ length: steps }, (_, i) => {
    const [r, g, b] = l[Math.round((i / (steps - 1)) * 255)];
    return `rgb(${r},${g},${b}) ${Math.round((i / (steps - 1)) * 100)}%`;
  });
  return `linear-gradient(to right, ${parts.join(", ")})`;
}

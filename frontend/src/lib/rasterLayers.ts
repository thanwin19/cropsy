import { lut } from "./colormaps";

/** Decoding and drawing of the 8-bit layer rasters built by backend/scripts/build_layers.py.
 *  Grey layers: value = lo + (q - 1) / 254 * (hi - lo), q = 0 means "no data". RGB layers (true colour, land cover) are drawn as they are. */

export type Decoded = { w: number; h: number; q: Uint8ClampedArray; alpha: Uint8ClampedArray; rgba: Uint8ClampedArray };

const cache = new Map<string, Promise<Decoded>>();

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Could not load ${url}`));
    img.src = url;
  });
}

export function decode(url: string): Promise<Decoded> {
  let p = cache.get(url);
  if (!p) {
    p = loadImage(url).then((img) => {
      const c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const ctx = c.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0);
      const rgba = ctx.getImageData(0, 0, c.width, c.height).data;
      const n = c.width * c.height;
      const q = new Uint8ClampedArray(n);
      const alpha = new Uint8ClampedArray(n);
      for (let i = 0; i < n; i++) {
        q[i] = rgba[i * 4];
        alpha[i] = rgba[i * 4 + 3];
      }
      return { w: c.width, h: c.height, q, alpha, rgba };
    });
    p.catch(() => cache.delete(url));
    cache.set(url, p);
  }
  return p;
}

export const valueAt = (d: Decoded, i: number, range: [number, number]): number | null =>
  d.alpha[i] === 0 || d.q[i] === 0 ? null : range[0] + ((d.q[i] - 1) / 254) * (range[1] - range[0]);

function canvasFrom(d: Decoded, fill: (i: number, out: Uint8ClampedArray) => void): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = d.w;
  c.height = d.h;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(d.w, d.h);
  for (let i = 0; i < d.w * d.h; i++) fill(i, img.data.subarray(i * 4, i * 4 + 4) as unknown as Uint8ClampedArray);
  ctx.putImageData(img, 0, 0);
  return c;
}

/** A grey layer drawn through a colour palette. */
export function colorize(d: Decoded, cmap: string): HTMLCanvasElement {
  const l = lut(cmap);
  return canvasFrom(d, (i, o) => {
    if (d.alpha[i] === 0 || d.q[i] === 0) { o[3] = 0; return; }
    const [r, g, b] = l[Math.round(((d.q[i] - 1) / 254) * 255)];
    o[0] = r; o[1] = g; o[2] = b; o[3] = 255;
  });
}

/** Later month minus earlier month, on a diverging palette; `span` is the full-scale change shown (e.g. 0.3 NDVI). */
export function difference(a: Decoded, b: Decoded, range: [number, number], span: number): HTMLCanvasElement {
  const l = lut("RdBu");
  return canvasFrom(a, (i, o) => {
    const va = valueAt(a, i, range), vb = valueAt(b, i, range);
    if (va == null || vb == null) { o[3] = 0; return; }
    const t = Math.min(Math.max(((vb - va) / span + 1) / 2, 0), 1);
    const [r, g, bl] = l[Math.round(t * 255)];
    o[0] = r; o[1] = g; o[2] = bl; o[3] = 255;
  });
}

/** An RGBA layer (true colour, land cover) exactly as stored. */
export function plain(d: Decoded): HTMLCanvasElement {
  return canvasFrom(d, (i, o) => { o[0] = d.rgba[i * 4]; o[1] = d.rgba[i * 4 + 1]; o[2] = d.rgba[i * 4 + 2]; o[3] = d.rgba[i * 4 + 3]; });
}

/** Hybrid: the real picture with the NDVI colours laid over it at 50%. */
export function blend(base: HTMLCanvasElement, over: HTMLCanvasElement, alpha = 0.5): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = base.width;
  c.height = base.height;
  const ctx = c.getContext("2d")!;
  ctx.drawImage(base, 0, 0);
  ctx.globalAlpha = alpha;
  ctx.drawImage(over, 0, 0);
  return c;
}

/** Contrast-stretch an RGB layer (used only if the stored layer is not already enhanced). */
export const toUrl = (c: HTMLCanvasElement) => c.toDataURL("image/png");

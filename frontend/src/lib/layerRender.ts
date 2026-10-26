import { layerUrl, type LayersManifest } from "./cropsy-api";
import { blend, colorize, decode, plain } from "./rasterLayers";

/** Draw one map layer for one month as a canvas, using a palette for the grey layers. Shared by quick-view controls. */
export async function renderLayer(m: LayersManifest, layerId: string, month: string, cmap: string): Promise<HTMLCanvasElement> {
  const info = m.layers[layerId];
  const staticLayer = info.months[0] === "static";
  switch (layerId) {
    case "lulc":
      return plain(await decode(layerUrl("lulc", "static")));
    case "tci":
    case "etci":
      return plain(await decode(layerUrl(layerId, month)));
    case "hybrid": {
      const [t, n] = await Promise.all([decode(layerUrl("tci", month)), decode(layerUrl("ndvi", month))]);
      return blend(plain(t), colorize(n, "RdYlGn"), 0.5);
    }
    case "colorblind":
      return colorize(await decode(layerUrl("ndvi", month)), "Cividis");
    default:
      return colorize(await decode(layerUrl(layerId, staticLayer ? "static" : month)), cmap);
  }
}

export const GREY_LAYERS = new Set(["ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "et", "soc", "dem", "rvi", "rsm"]);
export const DEFAULT_PALETTE: Record<string, string> = {
  ndvi: "RdYlGn", evi: "RdYlGn", savi: "RdYlGn", ndre: "RdYlGn", ndmi: "Blues", ndwi: "Blues", et: "Viridis",
  soc: "YlOrBr", dem: "Terrain", rvi: "Viridis", rsm: "Blues",
};

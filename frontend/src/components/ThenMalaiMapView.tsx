/**
 * ThenMalaiMapView.tsx  — "real-map" edition with Terrain Shadow & Cloud Forecast
 *
 * Features:
 *  1. A real Leaflet map (CartoDB dark / ArcGIS satellite / OSM street) centered on
 *     Then Malai parcel coordinates (8.91°N, 77.32°E).
 *  2. Real-time deterministic Terrain-Shadow raster engine (Web Worker ray-marching
 *     across Copernicus 30m DEM cache). Coarse interactive drag pass + fine release pass.
 *  3. Numerical Weather Prediction Cloud Forecast layer (~10km Open-Meteo hourly model).
 *  4. Fictional demo parcel boundary polygons (TM-01 to TM-06).
 *  5. Transparent SVG sun-path arc & compass overlay on the live map.
 *  6. Glassy left sidebar with Solar Ephemeris & Terrain Shading analytics.
 *  7. Glassy bottom timeline slider with day/night gradient & cloud forecast strip.
 *  8. Map Layers popover with Terrain Shadow and Cloud Forecast toggles + Legend.
 *
 * Then Malai demo ONLY — strictly isolated to Then Malai.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  Sun,
  X,
  Mountain,
  ChevronDown,
  Calendar,
  Layers,
  Check,
  Clock,
  Cloud,
  CloudSun,
  Play,
  Pause,
  Eclipse,
  Eye,
  Info,
  Map as MapIcon,
  ShieldAlert,
} from "lucide-react";
import {
  calcDay,
  calcPos,
  computeParcelSunSummary,
  lookupHorizonAngle,
  type DirectSunWindow,
  type HorizonPoint,
  type ParcelTerrainSunSummary,
  type ShadedInterval,
  type SolarDay,
  type SolarPos,
} from "../lib/solarGeometry";
import { VerticalShadowTimeControl, type ObservedSunshineData } from "./VerticalShadowTimeControl";
import { DraggableLayersControl } from "./DraggableLayersControl";
import { ParcelSunlightPanel } from "./ParcelSunlightPanel";
import { QuickSatelliteLayers } from "./QuickSatelliteLayers";
import { useDraggable } from "../lib/useDraggable";
import { useMediaQuery } from "../lib/useMediaQuery";
import { EpidemicDemo } from "./EpidemicDemo";
import { FieldZonesOverlay } from "./FieldZonesOverlay";
import { SolarPanel, ShadowPanel, SolarTimeline, MapTypeSwitch, hm } from "./cropsy/MapOverlays";
import { fetchSatelliteOverview, type SatelliteOverview } from "@/lib/cropsy-api";

// ─────────────────────────────────────────────────────────────────────────────
// Parcel data (TM-01 to TM-16)
// ─────────────────────────────────────────────────────────────────────────────
// All 120 Then Malai parcels come from the generated dataset module (backend/scripts/export_frontend_data.py), exposed through
// lib/parcels.ts so non-map pages can use them without loading Leaflet. Do not hard-code parcels here.
import { THEN_MALAI_PARCELS, CROP_COLORS, HEALTH_COLORS, cropColor, healthColor, type ParcelId } from "../lib/parcels";
export { THEN_MALAI_PARCELS, CROP_COLORS, HEALTH_COLORS, cropColor, healthColor };
export type { ParcelId };
const hexA = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

// ─────────────────────────────────────────────────────────────────────────────
// Layer Configuration for Then Malai Map (8 distinct layers)
// ─────────────────────────────────────────────────────────────────────────────
export interface ThenMalaiLayers {
  cadastral: boolean;
  fmb: boolean;
  survey: boolean;
  terrainShadow: boolean;
  hillshade: boolean;
  cloudForecast: boolean;
  ridge: boolean;
  sunArc: boolean;
  lighting: boolean;
}

export const DEFAULT_TM_LAYERS: ThenMalaiLayers = {
  cadastral: true,
  fmb: true,
  survey: true,
  terrainShadow: true,
  hillshade: false,
  cloudForecast: false,
  ridge: true,
  sunArc: true,
  lighting: true,
};

export const TM_LAYERS_CONFIG: Array<{
  key: keyof ThenMalaiLayers;
  label: string;
  color: string;
  desc: string;
}> = [
  { key: "cadastral",     label: "Cadastral Parcels", color: "#fbbf24", desc: "Demo boundaries TM-01 to TM-16" },
  { key: "fmb",           label: "FMB Subdivisions",  color: "#22d3ee", desc: "Internal field survey lines" },
  { key: "survey",        label: "Survey Badges",     color: "#fde68a", desc: "On-map parcel & crop tags" },
  { key: "terrainShadow", label: "Terrain Shadow",    color: "#94a3b8", desc: "DEM 30m ray-marched mountain shade" },
  { key: "hillshade",     label: "Relief Hillshade",  color: "#a8a29e", desc: "Esri World Hillshade relief under the shadow" },
  { key: "cloudForecast", label: "Cloud Forecast",    color: "#38bdf8", desc: "Open-Meteo ~10km hourly cloud model" },
  { key: "ridge",         label: "Western Ghats Ridge", color: "#d97706", desc: "Foothill shadow projection line" },
  { key: "sunArc",        label: "Solar Sun-Path Arc", color: "#f59e0b", desc: "NOAA trajectory & compass" },
  { key: "lighting",      label: "Atmospheric Lighting", color: "#60a5fa", desc: "Altitude-driven day/night tint" },
];

// ─────────────────────────────────────────────────────────────────────────────
// Tile URLs (100% key-free real tile providers)
// ─────────────────────────────────────────────────────────────────────────────
const TILES = {
  dark: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    opts: {
      maxNativeZoom: 19,
      maxZoom: 21,
      subdomains: "abc",
      className: "tm-dark-tile",
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    opts: {
      maxNativeZoom: 17,   // the imagery has no sharper tiles here; beyond this level we enlarge the last one
      maxZoom: 21,
      attribution: "&copy; Esri &mdash; World Imagery",
    },
  },
  street: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    opts: {
      maxNativeZoom: 19,
      maxZoom: 21,
      subdomains: "abc",
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

const fmt = (m: number, s = false) => {
  const h = Math.floor(m / 60) % 24,
    mi = Math.floor(m % 60),
    sc = Math.round((m % 1) * 60);
  return s
    ? `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}:${String(sc).padStart(2, "0")}`
    : `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
};
const durFmt = (m: number) => `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`;
const dateToStr = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function arcXY(az: number, alt: number, cx: number, cy: number, R: number) {
  const frac = 1 - Math.max(0, Math.min(90, alt)) / 90;
  const a = (az - 90) * D2R;
  return { x: cx + R * frac * Math.cos(a), y: cy + R * frac * Math.sin(a) };
}

function buildArc(lat: number, lon: number, date: Date) {
  const pts: { az: number; alt: number }[] = [];
  for (let m = 0; m <= 1440; m += 5) {
    const p = calcPos(lat, lon, date, m);
    if (p.alt > 0) pts.push({ az: p.az, alt: p.alt });
  }
  return pts;
}

function calcNightOverlay(alt: number): { bg: string; opacity: number; tileFilter: string; desc: string } {
  if (alt >= 6) {
    return { bg: "transparent", opacity: 0, tileFilter: "none", desc: "Daylight" };
  } else if (alt > 0) {
    const t = 1 - alt / 6;
    const op = t * 0.22;
    return {
      bg: "linear-gradient(180deg, rgba(15, 23, 42, 0.4) 0%, rgba(180, 83, 9, 0.32) 100%)",
      opacity: Math.round(op * 100) / 100,
      tileFilter: `brightness(${(1 - t * 0.12).toFixed(2)}) saturate(${(1 + t * 0.1).toFixed(2)})`,
      desc: "Golden Hour",
    };
  } else if (alt >= -6) {
    const t = -alt / 6;
    const op = 0.22 + t * 0.32;
    return {
      bg: "linear-gradient(180deg, rgba(8, 15, 33, 0.9) 0%, rgba(55, 22, 50, 0.8) 100%)",
      opacity: Math.round(op * 100) / 100,
      tileFilter: `brightness(${(0.88 - t * 0.22).toFixed(2)}) contrast(1.05)`,
      desc: "Civil Twilight",
    };
  } else if (alt >= -12) {
    const t = (-alt - 6) / 6;
    const op = 0.54 + t * 0.18;
    return {
      bg: "linear-gradient(180deg, rgba(4, 8, 22, 0.95) 0%, rgba(6, 12, 32, 0.95) 100%)",
      opacity: Math.round(op * 100) / 100,
      tileFilter: `brightness(${(0.66 - t * 0.22).toFixed(2)}) saturate(0.8)`,
      desc: "Nautical Twilight",
    };
  } else {
    const depth = Math.min(1, (-alt - 12) / 20);
    const op = 0.72 + depth * 0.08;
    return {
      bg: "rgba(3, 6, 18, 0.94)",
      opacity: Math.round(op * 100) / 100,
      tileFilter: `brightness(${(0.44 - depth * 0.16).toFixed(2)}) saturate(0.6)`,
      desc: "Night",
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Calendar Picker Popup
// ─────────────────────────────────────────────────────────────────────────────
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAYS = ["Su","Mo","Tu","We","Th","Fr","Sa"];

function CalendarPicker({ value, onChange, onClose }: { value: Date; onChange: (d: Date) => void; onClose: () => void }) {
  const [view, setView] = useState(new Date(value.getFullYear(), value.getMonth(), 1));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yr = view.getFullYear(),
    mo = view.getMonth();
  const firstDow = new Date(yr, mo, 1).getDay();
  const daysInMonth = new Date(yr, mo + 1, 0).getDate();
  const cells: Array<number | null> = Array(firstDow).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const isSelected = (d: number | null) =>
    d != null && value.getFullYear() === yr && value.getMonth() === mo && value.getDate() === d;
  const isToday = (d: number | null) =>
    d != null && today.getFullYear() === yr && today.getMonth() === mo && today.getDate() === d;

  const gl = "rgba(8,12,22,0.96)",
    bdr = "rgba(251,191,36,0.28)",
    txt = "rgba(226,232,240,0.9)",
    mut = "rgba(100,116,139,0.7)";

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 198, cursor: "default" }} />
      <div
        style={{
          position: "absolute",
          top: "calc(100% + 4px)",
          left: 0,
          zIndex: 199,
          background: gl,
          border: `1px solid ${bdr}`,
          borderRadius: 10,
          boxShadow: "0 12px 40px rgba(0,0,0,0.65)",
          backdropFilter: "blur(20px)",
          padding: 10,
          width: 224,
          userSelect: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <button
            onClick={() => setView(new Date(yr, mo - 1, 1))}
            style={{ border: 0, background: "transparent", color: txt, cursor: "pointer", padding: "2px 5px", borderRadius: 4, fontSize: 14 }}
          >
            ‹
          </button>
          <span style={{ fontSize: 11, fontWeight: 700, color: txt }}>
            {MONTHS[mo]} {yr}
          </span>
          <button
            onClick={() => setView(new Date(yr, mo + 1, 1))}
            style={{ border: 0, background: "transparent", color: txt, cursor: "pointer", padding: "2px 5px", borderRadius: 4, fontSize: 14 }}
          >
            ›
          </button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 2, marginBottom: 4 }}>
          {DAYS.map((d) => (
            <div key={d} style={{ textAlign: "center", fontSize: 8.5, color: mut, fontFamily: "monospace", fontWeight: 700, padding: "2px 0" }}>
              {d}
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 2 }}>
          {cells.map((d, i) => (
            <button
              key={i}
              onClick={() => {
                if (d) {
                  const nd = new Date(Date.UTC(yr, mo, d));
                  onChange(nd);
                  onClose();
                }
              }}
              style={{
                border: 0,
                borderRadius: 5,
                width: "100%",
                aspectRatio: "1",
                background: isSelected(d) ? "#f59e0b" : isToday(d) ? "rgba(245,158,11,0.18)" : "transparent",
                color: isSelected(d) ? "#000" : d ? txt : mut,
                fontFamily: "monospace",
                fontSize: 10,
                fontWeight: isSelected(d) || isToday(d) ? 700 : 400,
                cursor: d ? "pointer" : "default",
                outline: isToday(d) && !isSelected(d) ? "1px solid rgba(245,158,11,0.45)" : "none",
              }}
            >
              {d || ""}
            </button>
          ))}
        </div>
        <button
          onClick={() => {
            onChange(new Date(today));
            onClose();
          }}
          style={{
            marginTop: 7,
            width: "100%",
            border: `1px solid rgba(245,158,11,0.3)`,
            background: "rgba(245,158,11,0.08)",
            borderRadius: 6,
            padding: "4px 0",
            fontSize: 9.5,
            fontFamily: "monospace",
            color: "#f59e0b",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          Today
        </button>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Timeline Bar with Cloud Forecast Strip
// ─────────────────────────────────────────────────────────────────────────────
export interface HourlyCloud {
  hour: number;
  cloudCoverPct: number | null;
  directRadWm2: number | null;
}

function TimelineBar({
  curMin,
  sd,
  onChange,
  onDragStart,
  onDragEnd,
  cloudHourly,
  isLive,
  onJumpNow,
}: {
  curMin: number;
  sd: SolarDay;
  onChange: (m: number | ((prev: number) => number)) => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  cloudHourly: HourlyCloud[];
  isLive: boolean;
  onJumpNow: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const animRef = useRef<number | null>(null);
  const lastTickTimeRef = useRef<number | null>(null);

  const read = useCallback(
    (e: React.PointerEvent | PointerEvent) => {
      if (!ref.current) return;
      const { left, width } = ref.current.getBoundingClientRect();
      let m = Math.max(0, Math.min(1, (e.clientX - left) / width)) * 1440;
      if (e.shiftKey) {
        m = Math.round(m);
      } else {
        m = Math.round(m / 5) * 5;
      }
      onChange(Math.max(0, Math.min(1440, m)));
    },
    [onChange]
  );

  useEffect(() => {
    const mv = (e: PointerEvent) => {
      if (drag.current) read(e);
    };
    const up = () => {
      if (drag.current) {
        drag.current = false;
        onDragEnd?.();
      }
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
    };
  }, [read, onDragEnd]);

  // Smooth Day Simulation Animation (~20s per 24h = 72 min/sec)
  useEffect(() => {
    if (!isPlaying) {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      lastTickTimeRef.current = null;
      return;
    }

    const speedMinPerSec = 72;
    const step = (timestamp: number) => {
      if (lastTickTimeRef.current == null) {
        lastTickTimeRef.current = timestamp;
      }
      const dtSec = (timestamp - lastTickTimeRef.current) / 1000;
      lastTickTimeRef.current = timestamp;

      onChange((prevMin: number) => {
        const next = (prevMin + dtSec * speedMinPerSec) % 1440;
        return next;
      });

      animRef.current = requestAnimationFrame(step);
    };

    animRef.current = requestAnimationFrame(step);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, onChange]);

  const stops: string = [
    `rgba(8,14,26,0.95) 0%`,
    `rgba(8,14,26,0.95) ${((sd.dawn / 1440) * 100).toFixed(1)}%`,
    `rgba(30,58,95,0.92) ${((sd.rise / 1440) * 100).toFixed(1)}%`,
    `rgba(120,60,10,0.92) ${((sd.ghStart / 1440) * 100).toFixed(1)}%`,
    `rgba(202,108,8,0.92) ${(((sd.ghStart + 20) / 1440) * 100).toFixed(1)}%`,
    `rgba(245,158,11,0.92) ${((sd.noon / 1440) * 100).toFixed(1)}%`,
    `rgba(202,108,8,0.92) ${(((sd.ghEnd - 20) / 1440) * 100).toFixed(1)}%`,
    `rgba(120,60,10,0.92) ${((sd.ghEnd / 1440) * 100).toFixed(1)}%`,
    `rgba(30,58,95,0.92) ${((sd.set / 1440) * 100).toFixed(1)}%`,
    `rgba(8,14,26,0.95) ${((sd.dusk / 1440) * 100).toFixed(1)}%`,
    `rgba(8,14,26,0.95) 100%`,
  ].join(", ");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Top Header Row with Time, Play/Pause, Now */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button
            id="tm-horizontal-play-btn"
            onClick={() => setIsPlaying((p) => !p)}
            title={isPlaying ? "Pause day simulation" : "Play day simulation (20s)"}
            style={{
              border: `1px solid ${isPlaying ? "rgba(34,211,238,0.45)" : "rgba(251,191,36,0.3)"}`,
              background: isPlaying ? "rgba(34,211,238,0.18)" : "rgba(255,255,255,0.06)",
              color: isPlaying ? "#22d3ee" : "#fbbf24",
              borderRadius: 4,
              padding: "1px 6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 3,
              fontSize: 8,
              fontFamily: "monospace",
              fontWeight: 700,
            }}
          >
            {isPlaying ? <Pause size={9} /> : <Play size={9} />}
            <span>{isPlaying ? "PAUSE" : "PLAY"}</span>
          </button>

          <button
            id="tm-horizontal-now-btn"
            onClick={() => {
              setIsPlaying(false);
              onJumpNow();
            }}
            title="Jump back to current Asia/Kolkata IST time"
            style={{
              border: `1px solid ${isLive ? "rgba(34,211,238,0.45)" : "rgba(251,191,36,0.25)"}`,
              background: isLive ? "rgba(34,211,238,0.15)" : "rgba(255,255,255,0.05)",
              color: isLive ? "#22d3ee" : "#94a3b8",
              borderRadius: 4,
              padding: "1px 6px",
              fontSize: 8,
              fontFamily: "monospace",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 3,
            }}
          >
            <Clock size={8} style={{ color: isLive ? "#22d3ee" : "#fbbf24" }} />
            <span>⊙ NOW</span>
          </button>
        </div>

        <div style={{ fontSize: 8.5, fontFamily: "monospace", color: "#fbbf24", fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: isLive ? "#22d3ee" : "rgba(148,163,184,0.7)" }}>{isLive ? "● LIVE" : "● MANUAL"}</span>
          <span style={{ background: "rgba(245,158,11,0.15)", border: "1px solid rgba(251,191,36,0.3)", padding: "1px 6px", borderRadius: 4 }}>
            SIMULATION TIME: {fmt(curMin)} IST
          </span>
        </div>
      </div>

      {/* Hour labels */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "rgba(255,255,255,0.45)", fontFamily: "monospace" }}>
        {[0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => (
          <span key={h}>{String(h).padStart(2, "0")}:00</span>
        ))}
      </div>

      {/* Main Slider Track */}
      <div
        ref={ref}
        role="slider"
        aria-label="Solar Simulation Time (Horizontal)"
        aria-valuemin={0}
        aria-valuemax={1440}
        aria-valuenow={Math.round(curMin)}
        tabIndex={0}
        style={{
          position: "relative",
          height: 18,
          borderRadius: 9,
          background: `linear-gradient(to right, ${stops})`,
          border: "1px solid rgba(251,191,36,0.35)",
          cursor: "pointer",
          userSelect: "none",
          boxShadow: "inset 0 1px 4px rgba(0,0,0,0.5)",
        }}
        onPointerDown={(e) => {
          drag.current = true;
          setIsPlaying(false);
          onDragStart?.();
          read(e);
        }}
        onKeyDown={(e) => {
          setIsPlaying(false);
          const step = e.shiftKey ? 1 : 5;
          if (e.key === "ArrowLeft" || e.key === "ArrowUp") onChange((m: number) => Math.max(0, m - step));
          if (e.key === "ArrowRight" || e.key === "ArrowDown") onChange((m: number) => Math.min(1440, m + step));
          if (e.key === "PageUp") onChange((m: number) => Math.max(0, m - 60));
          if (e.key === "PageDown") onChange((m: number) => Math.min(1440, m + 60));
        }}
      >
        {/* Sunrise & Sunset Markers */}
        {[sd.rise, sd.set].map((m, i) => (
          <div
            key={i}
            title={i === 0 ? `Sunrise: ${fmt(sd.rise)} IST` : `Sunset: ${fmt(sd.set)} IST`}
            style={{
              position: "absolute",
              top: "50%",
              left: `${((m / 1440) * 100).toFixed(2)}%`,
              transform: "translate(-50%,-50%)",
              width: 2,
              height: 14,
              borderRadius: 1,
              background: "#fbbf24",
              opacity: 0.95,
              boxShadow: "0 0 4px #fbbf24",
            }}
          />
        ))}

        {/* Draggable Knob */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: `${((curMin / 1440) * 100).toFixed(2)}%`,
            transform: "translate(-50%,-50%)",
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: "#fbbf24",
            border: "2.5px solid #fff",
            boxShadow: "0 2px 10px rgba(0,0,0,0.6), 0 0 0 1px rgba(245,158,11,0.7)",
            zIndex: 2,
          }}
        />
      </div>

      {/* Cloud & Direct Sun Forecast Strip */}
      <div style={{ display: "flex", flexDirection: "column", gap: 1, marginTop: 1 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(24, 1fr)",
            height: 4,
            borderRadius: 2,
            overflow: "hidden",
            background: "rgba(15,23,42,0.8)",
            border: "1px solid rgba(56,189,248,0.25)",
          }}
          title="Expected direct sun & cloud forecast (Open-Meteo ~10km)"
        >
          {Array.from({ length: 24 }).map((_, h) => {
            const fc = cloudHourly.find((c) => c.hour === h);
            const cc = fc?.cloudCoverPct ?? 0;
            const color =
              fc?.cloudCoverPct == null
                ? "rgba(100,116,139,0.3)"
                : cc < 25
                ? "rgba(251,191,36,0.85)"
                : cc < 65
                ? "rgba(56,189,248,0.7)"
                : "rgba(148,163,184,0.6)";
            return (
              <div
                key={h}
                style={{
                  background: color,
                  borderRight: h < 23 ? "1px solid rgba(0,0,0,0.3)" : "none",
                  height: "100%",
                }}
              />
            );
          })}
        </div>
      </div>

      {/* Sunrise, current time, sunset readout */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "rgba(255,255,255,0.5)", fontFamily: "monospace", marginTop: 1 }}>
        <span style={{ color: "#fde68a" }}>↑ Sunrise {fmt(sd.rise)}</span>
        <span style={{ color: "rgba(148,163,184,0.7)" }}>Solar Day Progression (00:00 – 24:00)</span>
        <span style={{ color: "#fde68a" }}>Sunset {fmt(sd.set)} ↓</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SVG Sun-Path Overlay
// ─────────────────────────────────────────────────────────────────────────────
function SunOverlay({
  lat,
  lon,
  date,
  curMin,
  w,
  h,
}: {
  lat: number;
  lon: number;
  date: Date;
  curMin: number;
  w: number;
  h: number;
}) {
  const cx = w / 2,
    cy = h / 2,
    R = Math.min(w, h) * 0.36;
  const arc = useMemo(() => buildArc(lat, lon, date), [lat, lon, date]);
  const cur = useMemo(() => calcPos(lat, lon, date, curMin), [lat, lon, date, curMin]);

  const pts = arc
    .map((p) => {
      const { x, y } = arcXY(p.az, p.alt, cx, cy, R);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const sun = cur.alt > 0 ? arcXY(cur.az, cur.alt, cx, cy, R) : null;

  const compass = [
    { l: "N", az: 0 },
    { l: "E", az: 90 },
    { l: "S", az: 180 },
    { l: "W", az: 270 },
  ].map(({ l, az }) => {
    const a = (az - 90) * D2R,
      lr = R + 22;
    return { l, x: cx + lr * Math.cos(a), y: cy + lr * Math.sin(a) };
  });

  return (
    <svg
      className="tm-sun-arc"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", overflow: "visible", zIndex: 5 }}
      viewBox={`0 0 ${w} ${h}`}
      aria-hidden="true"
    >
      <defs>
        <filter id="tmglow">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id="tmfade" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(251,191,36,0.0)" />
          <stop offset="100%" stopColor="rgba(251,191,36,0.07)" />
        </radialGradient>
      </defs>

      <circle cx={cx} cy={cy} r={R + 20} fill="url(#tmfade)" />
      <circle cx={cx} cy={cy} r={R} fill="none" stroke="rgba(251,191,36,0.4)" strokeWidth="1.5" strokeDasharray="5 3" />

      {[30, 60].map((a) => (
        <circle key={a} cx={cx} cy={cy} r={R * (1 - a / 90)} fill="none" stroke="rgba(251,191,36,0.18)" strokeWidth="0.8" strokeDasharray="3 4" />
      ))}

      {[0, 90].map((az) => {
        const a = (az - 90) * D2R;
        return (
          <line
            key={az}
            x1={cx - (R + 10) * Math.cos(a)}
            y1={cy - (R + 10) * Math.sin(a)}
            x2={cx + (R + 10) * Math.cos(a)}
            y2={cy + (R + 10) * Math.sin(a)}
            stroke="rgba(251,191,36,0.16)"
            strokeWidth="0.8"
          />
        );
      })}

      <text x={cx + R * 0.667 + 3} y={cy - 3} fill="rgba(251,191,36,0.65)" fontSize="9" fontFamily="monospace">
        30°
      </text>
      <text x={cx + R * 0.333 + 3} y={cy - 3} fill="rgba(251,191,36,0.65)" fontSize="9" fontFamily="monospace">
        60°
      </text>

      {compass.map(({ l, x, y }) => (
        <text
          key={l}
          x={x}
          y={y + 4}
          textAnchor="middle"
          fill="rgba(255,255,255,0.88)"
          fontSize="12"
          fontWeight="700"
          fontFamily="monospace"
          style={{ filter: "drop-shadow(0 1px 3px rgba(0,0,0,0.9))" }}
        >
          {l}
        </text>
      ))}

      {arc.length > 1 && (
        <polygon
          points={[
            `${arcXY(arc[0].az, 0, cx, cy, R).x.toFixed(1)},${arcXY(arc[0].az, 0, cx, cy, R).y.toFixed(1)}`,
            ...arc.map((p) => {
              const { x, y } = arcXY(p.az, p.alt, cx, cy, R);
              return `${x.toFixed(1)},${y.toFixed(1)}`;
            }),
            `${arcXY(arc[arc.length - 1].az, 0, cx, cy, R).x.toFixed(1)},${arcXY(arc[arc.length - 1].az, 0, cx, cy, R).y.toFixed(1)}`,
          ].join(" ")}
          fill="rgba(251,191,36,0.09)"
          stroke="none"
        />
      )}

      {arc.length > 1 && (
        <polyline points={pts} fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" filter="url(#tmglow)" opacity=".92" />
      )}

      <circle cx={cx} cy={cy} r="3.5" fill="none" stroke="rgba(251,191,36,0.5)" strokeWidth="1" />

      {sun && (
        <g>
          <circle cx={sun.x} cy={sun.y} r="15" fill="rgba(251,191,36,0.1)" stroke="rgba(251,191,36,0.3)" strokeWidth="1" />
          <circle cx={sun.x} cy={sun.y} r="8" fill="rgba(251,191,36,0.2)" stroke="rgba(251,191,36,0.6)" strokeWidth="1.2" />
          <circle cx={sun.x} cy={sun.y} r="5" fill="#fbbf24" stroke="#fff" strokeWidth="2" filter="url(#tmglow)" />
          <line x1={cx} y1={cy} x2={sun.x} y2={sun.y} stroke="rgba(251,191,36,0.2)" strokeWidth="1" strokeDasharray="3 3" />
        </g>
      )}
      {!sun && (
        <text x={cx} y={cy + 20} textAnchor="middle" fill="rgba(148,163,184,0.75)" fontSize="11" fontFamily="monospace">
          Sun below horizon
        </text>
      )}

      <circle cx={cx} cy={cy} r="5" fill="#22d3ee" stroke="#fff" strokeWidth="1.5" opacity=".92" />
      <circle cx={cx} cy={cy} r="12" fill="none" stroke="rgba(34,211,238,0.35)" strokeWidth="1" />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Map Legend (Step 6)
// ─────────────────────────────────────────────────────────────────────────────
function MapLegend({ colorBy, docked = false, joined = false }: { colorBy: "crop" | "health"; docked?: boolean; joined?: boolean }) {
  const d = useDraggable<HTMLDivElement>("cropsy.drag.legend");
  const [open, setOpen] = useState(false);
  return (
    <div
      {...(docked ? {} : { ref: d.ref, ...d.bind })}
      style={{
        ...(docked ? {} : d.style),
        position: docked ? "relative" : "absolute",
        ...(docked ? {} : { bottom: 100, right: 10 }),
        zIndex: 14,
        background: "color-mix(in oklab, var(--overlay) 92%, transparent)",
        border: "1px solid var(--border)",
        borderRadius: joined ? "0 12px 12px 0" : 12,
        ...(joined ? { borderLeft: 0 } : {}),
        backdropFilter: "blur(14px)",
        padding: "0 12px",
        pointerEvents: "auto",
        cursor: docked ? "default" : "grab",
        boxShadow: "0 12px 30px rgba(0,0,0,0.45)",
      }}
    >
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        aria-label="Map legend" title="Map legend"
        className="flex h-[34px] items-center px-1 text-secondary-foreground">
        <MapIcon className="size-4" />
      </button>
      {open && <div data-nodrag style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 8.5, fontFamily: "monospace", cursor: "default" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: "#fbbf24", boxShadow: "0 0 4px #fbbf24" }} />
          <span style={{ color: "rgba(226,232,240,0.9)" }}>Direct Sunlit</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: "rgba(30, 41, 59, 0.9)", border: "1px solid #94a3b8" }} />
          <span style={{ color: "rgba(203,213,225,0.9)" }}>Terrain Shaded</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: "rgba(56, 189, 248, 0.7)", border: "1px solid #38bdf8" }} />
          <span style={{ color: "rgba(56,189,248,0.95)" }}>Cloud Forecast</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: "rgba(3, 6, 18, 0.95)", border: "1px solid #64748b" }} />
          <span style={{ color: "rgba(148,163,184,0.8)" }}>Night / Twilight</span>
        </div>
        <div style={{ height: 1, background: "rgba(251,191,36,0.15)", margin: "2px 0" }} />
        {colorBy === "crop" ? (
          <>
            {Object.entries(CROP_COLORS).map(([crop, col]) => (
              <div key={crop} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: hexA(col, 0.35), border: `1px solid ${col}` }} />
                <span style={{ color: "rgba(226,232,240,0.9)" }}>{crop}</span>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, border: "1px dashed #e2e8f0" }} />
              <span style={{ color: "rgba(226,232,240,0.9)" }}>Issue reported</span>
            </div>
          </>
        ) : (
          <>
            {([["normal", "Steady greenness"], ["watch", "Slight dip"], ["stress", "Falling: stress signal"], ["insufficient", "No clear view (cloud)"]] as const).map(([k, label]) => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: hexA(HEALTH_COLORS[k], 0.4), border: `1px solid ${HEALTH_COLORS[k]}` }} />
                <span style={{ color: "rgba(226,232,240,0.9)" }}>{label}</span>
              </div>
            ))}
            <span style={{ color: "rgba(148,163,184,0.7)", fontSize: 7.5 }}>Sentinel-2 NDVI, real data</span>
          </>
        )}
      </div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main ThenMalaiMapView Component
// ─────────────────────────────────────────────────────────────────────────────
export interface ThenMalaiMapViewProps {
  onClose?: () => void;
  dark?: boolean;
  initialParcelId?: ParcelId;
  onParcelChange?: (id: ParcelId, lat: number, lon: number, crop: string, elev: number) => void;
}


export function ThenMalaiMapView({ onClose, initialParcelId = "TM-01", onParcelChange }: ThenMalaiMapViewProps) {
  const [selId, setSelId] = useState<ParcelId>(initialParcelId);
  // Map colouring: by crop (default) or by real Sentinel-2 crop health (NDVI trend)
  const [colorBy, setColorBy] = useState<"crop" | "health">("crop");
  const narrow = useMediaQuery("(max-width: 639px)");
  const [satOverview, setSatOverview] = useState<SatelliteOverview | null>(null);
  useEffect(() => {
    let live = true;
    fetchSatelliteOverview().then((o) => live && setSatOverview(o)).catch(() => undefined);
    return () => { live = false; };
  }, []);

  // Follow the parcel selected elsewhere in the app (chat, header dropdown, typed "TM-45"), not just the first value.
  useEffect(() => {
    if (initialParcelId && THEN_MALAI_PARCELS.some((p) => p.id === initialParcelId)) setSelId(initialParcelId);
  }, [initialParcelId]);
  const [date, setDate] = useState<Date>(() => {
    const d = new Date(2026, 8, 28); // 2026-09-28 default for consistency
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [curMin, setCurMin] = useState<number>(12 * 60); // 12:00 IST default Solar Timeline
  const [shadowMin, setShadowMin] = useState<number>(14 * 60 + 32); // 14:32 IST independent Shadow Time
  const [isLive, setIsLive] = useState(false); // set to true if user clicks LIVE/NOW
  const [objH, setObjH] = useState(2);
  const [mapType, setMapType] = useState<"dark" | "satellite" | "street">("satellite");
  const [showMenu, setShowMenu] = useState(false);
  const [showCal, setShowCal] = useState(false);
  const [layers, setLayers] = useState<ThenMalaiLayers>(DEFAULT_TM_LAYERS);
  const [isDraggingSlider, setIsDraggingSlider] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => {
      setCurMin((prev) => (prev + 5) % 1440);
    }, 150);
    return () => clearTimeout(t);
  }, [playing, curMin]);

  // DEM Cache & Horizon profiles
  const [demMeta, setDemMeta] = useState<any>(null);
  const [dispDem, setDispDem] = useState<Int16Array | null>(null);
  const [fullDem, setFullDem] = useState<Int16Array | null>(null);
  const [horizonProfiles, setHorizonProfiles] = useState<Record<string, any>>({});
  const [cloudHourly, setCloudHourly] = useState<HourlyCloud[]>([]);

  // Worker ref
  const shadowWorkerRef = useRef<Worker | null>(null);
  const lastJobIdRef = useRef(0);
  const shadowCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const shadowOverlayRef = useRef<L.ImageOverlay | null>(null);
  const hillshadeRef = useRef<L.TileLayer | null>(null);
  const cloudOverlayPaneRef = useRef<HTMLDivElement | null>(null);

  const toggleLayer = (k: keyof ThenMalaiLayers) => {
    setLayers((prev) => ({ ...prev, [k]: !prev[k] }));
  };

  // Map refs
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const boundaryRef = useRef<L.LayerGroup | null>(null);

  // Sizing
  const outerRef = useRef<HTMLDivElement>(null);
  const [mapSz, setMapSz] = useState({ w: 700, h: 520 });
  useLayoutEffect(() => {
    if (!outerRef.current) return;
    const ro = new ResizeObserver((es) => {
      const { width, height } = es[0].contentRect;
      setMapSz({ w: Math.round(width), h: Math.round(height) });
    });
    ro.observe(outerRef.current);
    return () => ro.disconnect();
  }, []);

  const parcel = THEN_MALAI_PARCELS.find((p) => p.id === selId)!;
  const dateUTC = useMemo(() => new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())), [date]);
  const sd = useMemo(() => calcDay(parcel.lat, parcel.lon, dateUTC), [parcel, dateUTC]);
  const pos = useMemo(() => calcPos(parcel.lat, parcel.lon, dateUTC, curMin), [parcel, dateUTC, curMin]);
  const shadowM = pos.shadowX !== null ? (pos.shadowX * objH).toFixed(2) : null;
  const night = useMemo(() => calcNightOverlay(pos.alt), [pos.alt]);

  // Parcel horizon profile & summary (Step 4)
  const currentParcelProfile: HorizonPoint[] = useMemo(() => {
    const pdata = horizonProfiles[parcel.id];
    return pdata?.profile || [];
  }, [horizonProfiles, parcel.id]);

  const parcelSummary: ParcelTerrainSunSummary = useMemo(() => {
    return computeParcelSunSummary(parcel.lat, parcel.lon, dateUTC, currentParcelProfile, curMin);
  }, [parcel, dateUTC, currentParcelProfile, curMin]);

  // Independent Shadow Time Sun Position & Terrain Obstruction
  const shadowPos = useMemo(() => calcPos(parcel.lat, parcel.lon, dateUTC, shadowMin), [parcel, dateUTC, shadowMin]);
  const shadowHorizonAngle = useMemo(() => lookupHorizonAngle(currentParcelProfile, shadowPos.az), [currentParcelProfile, shadowPos.az]);
  const isShadowObstructed = useMemo(() => shadowPos.alt > 0 && shadowPos.alt <= shadowHorizonAngle, [shadowPos.alt, shadowHorizonAngle]);
  const shadowParcelSummary = useMemo(() => computeParcelSunSummary(parcel.lat, parcel.lon, dateUTC, currentParcelProfile, shadowMin), [parcel, dateUTC, currentParcelProfile, shadowMin]);

  const isCompact = mapSz.h < 440 || mapSz.w < 600;

  // ── Load DEM Cache and Horizon Profiles on mount (Step 1 & 2) ──
  useEffect(() => {
    async function loadDemAndHorizons() {
      try {
        const [metaRes, horizRes] = await Promise.all([
          fetch("/data/then_malai/dem/dem_metadata.json"),
          fetch("/data/then_malai/horizon_profiles.json"),
        ]);
        if (metaRes.ok) {
          const meta = await metaRes.json();
          setDemMeta(meta);

          // Fetch binary arrays
          const [dispBuf, fullBuf] = await Promise.all([
            fetch("/data/then_malai/dem/dem_display_30m.bin").then((r) => r.arrayBuffer()),
            fetch("/data/then_malai/dem/dem_full_90m.bin").then((r) => r.arrayBuffer()),
          ]);
          setDispDem(new Int16Array(dispBuf));
          setFullDem(new Int16Array(fullBuf));
        }
        if (horizRes.ok) {
          const hdata = await horizRes.json();
          setHorizonProfiles(hdata.parcels || {});
        }
      } catch (err) {
        console.error("Error loading DEM or horizon profiles:", err);
      }
    }
    loadDemAndHorizons();
  }, []);

  // ── Fetch Open-Meteo Cloud Forecast for Then Malai (Step 5) ──
  useEffect(() => {
    const dateStr = dateToStr(date);
    const url = `https://api.open-meteo.com/v1/forecast?latitude=8.91&longitude=77.32&hourly=cloud_cover,direct_radiation&timezone=Asia%2FKolkata&start_date=${dateStr}&end_date=${dateStr}`;
    fetch(url)
      .then((r) => r.json())
      .then((d) => {
        const hourly = d.hourly || {};
        const times = hourly.time || [];
        const cloudCover = hourly.cloud_cover || [];
        const directRad = hourly.direct_radiation || [];
        const parsed: HourlyCloud[] = times.map((_: any, i: number) => ({
          hour: i,
          cloudCoverPct: cloudCover[i] ?? null,
          directRadWm2: directRad[i] ?? null,
        }));
        setCloudHourly(parsed);
      })
      .catch((e) => {
        console.warn("Open-Meteo cloud forecast fetch failed:", e);
      });
  }, [date]);

  // ── Initialize Web Worker for Terrain Shadow Engine (Step 3) ──
  useEffect(() => {
    let worker: Worker | null = null;
    try {
      worker = new Worker(new URL("../workers/terrainShadowWorker.ts", import.meta.url), { type: "module" });
      worker.onmessage = (e) => {
        const { jobId, shadowMask, outWidth, outHeight } = e.data;
        if (jobId !== lastJobIdRef.current) return; // stale response

        // Render shadow mask onto Leaflet canvas overlay
        if (!shadowCanvasRef.current) {
          shadowCanvasRef.current = document.createElement("canvas");
        }
        const canvas = shadowCanvasRef.current;
        canvas.width = outWidth;
        canvas.height = outHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const imgData = ctx.createImageData(outWidth, outHeight);
        const data32 = new Uint32Array(imgData.data.buffer);

        // Translucent slate-blue terrain shadow: rgba(18, 28, 48, 0.65)
        // Little endian 32-bit: (A << 24) | (B << 16) | (G << 8) | R
        const shadowColor = (165 << 24) | (48 << 16) | (28 << 8) | 18;
        for (let i = 0; i < shadowMask.length; i++) {
          data32[i] = shadowMask[i] === 1 ? shadowColor : 0;
        }
        ctx.putImageData(imgData, 0, 0);

        // Update Leaflet ImageOverlay
        if (mapRef.current && demMeta?.display_grid) {
          const dg = demMeta.display_grid;
          const bounds = L.latLngBounds([dg.lat_min, dg.lon_min], [dg.lat_max, dg.lon_max]);
          const dataUrl = canvas.toDataURL();
          if (shadowOverlayRef.current) {
            shadowOverlayRef.current.setUrl(dataUrl);
          } else {
            shadowOverlayRef.current = L.imageOverlay(dataUrl, bounds, {
              pane: "shadowPane",
              opacity: 1,
              interactive: false,
            }).addTo(mapRef.current);
          }
        }
      };
      shadowWorkerRef.current = worker;
    } catch (err) {
      console.warn("Could not start Web Worker, terrain shadow will run on main thread fallback", err);
    }
    return () => {
      worker?.terminate();
      shadowWorkerRef.current = null;
    };
  }, [demMeta]);

  // ── Send DEM grids to the worker ONCE (jobs below are then tiny messages) ──
  useEffect(() => {
    if (!dispDem || !demMeta?.display_grid || !shadowWorkerRef.current) return;
    shadowWorkerRef.current.postMessage({
      type: "init",
      dispDem: dispDem.slice(),
      dispMeta: demMeta.display_grid,
      fullDem: fullDem ? fullDem.slice() : undefined,
      fullMeta: demMeta.full_grid || undefined,
    });
  }, [dispDem, fullDem, demMeta]);

  // ── Dispatch Shadow Computation to Web Worker ──
  const triggerShadowComputation = useCallback(
    (coarse: boolean) => {
      if (!dispDem || !demMeta) return;

      // If terrain shadow layer is disabled or night, clear overlay
      if (!layers.terrainShadow || shadowPos.alt <= 0) {
        if (shadowOverlayRef.current) {
          // Transparent 1x1 png
          shadowOverlayRef.current.setUrl("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7");
        }
        return;
      }

      const jobId = ++lastJobIdRef.current;
      const payload = {
        type: "job" as const,
        jobId,
        sunAlt: shadowPos.alt, // apparent (refracted) altitude
        sunAz: shadowPos.az,
        coarse,
      };

      if (shadowWorkerRef.current) {
        shadowWorkerRef.current.postMessage(payload);
      }
    },
    [dispDem, fullDem, demMeta, layers.terrainShadow, shadowPos.alt, shadowPos.az]
  );

  // Re-run shadow when shadowMin sun position or layer toggle changes
  useEffect(() => {
    triggerShadowComputation(isDraggingSlider);
  }, [triggerShadowComputation, isDraggingSlider, shadowPos.alt, shadowPos.az, layers.terrainShadow]);

  // ── Real-time clock: auto update every 30s when isLive ──
  useEffect(() => {
    if (!isLive) return;
    const tick = () => {
      const n = new Date();
      setCurMin(n.getHours() * 60 + n.getMinutes() + n.getSeconds() / 60);
    };
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, [isLive]);

  // ── Initialize Leaflet Map ──
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const map = L.map(mapContainerRef.current, {
      center: [parcel.lat, parcel.lon],
      zoom: 15,
      zoomControl: false,
      maxZoom: 21,
      attributionControl: false,
    });
    mapRef.current = map;
    L.control.zoom({ position: "topright" }).remove();

    // Panes hierarchy:
    // tilePane (200) < nightPane (250) < shadowPane (260) < cloudPane (270) < overlayPane (400)
    const reliefPane = map.createPane("reliefPane");
    reliefPane.style.zIndex = "210";
    reliefPane.style.pointerEvents = "none";
    reliefPane.style.mixBlendMode = "multiply";

    const nightPane = map.createPane("nightPane");
    nightPane.style.zIndex = "250";
    nightPane.style.pointerEvents = "none";
    nightPane.style.transition = "opacity 0.25s ease, background 0.25s ease, filter 0.25s ease";

    const shadowPane = map.createPane("shadowPane");
    shadowPane.style.zIndex = "260";
    shadowPane.style.pointerEvents = "none";

    const cloudPane = map.createPane("cloudPane");
    cloudPane.style.zIndex = "270";
    cloudPane.style.pointerEvents = "none";
    cloudPane.style.transition = "opacity 0.3s ease";

    tileRef.current = L.tileLayer(TILES.satellite.url, TILES.satellite.opts as L.TileLayerOptions).addTo(map);
    return () => {
      map.remove();
      mapRef.current = null;
      tileRef.current = null;
      shadowOverlayRef.current = null;
      hillshadeRef.current = null;
    };
  }, []);

  // ── Relief hillshade tiles (optional cartographic layer below the terrain shadow) ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (layers.hillshade && !hillshadeRef.current) {
      hillshadeRef.current = L.tileLayer(
        "https://server.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}",
        { pane: "reliefPane", maxNativeZoom: 16, maxZoom: 19, opacity: 0.55, attribution: "Esri World Hillshade" },
      ).addTo(map);
    } else if (!layers.hillshade && hillshadeRef.current) {
      map.removeLayer(hillshadeRef.current);
      hillshadeRef.current = null;
    }
  }, [layers.hillshade]);

  // ── Dynamic Day/Night Lighting Overlay ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const nightPane = map.getPane("nightPane");
    if (nightPane) {
      if (layers.lighting) {
        nightPane.style.background = night.bg;
        nightPane.style.opacity = String(night.opacity);
      } else {
        nightPane.style.opacity = "0";
      }
    }
    const tilePane = map.getPane("tilePane");
    if (tilePane) {
      if (!layers.lighting) {
        tilePane.style.filter = "none";
      } else if (mapType === "dark") {
        tilePane.style.filter = pos.alt < 0 ? "brightness(0.85)" : "none";
      } else {
        tilePane.style.filter = night.tileFilter;
      }
    }
  }, [night, pos.alt, mapType, layers.lighting]);

  // ── Switch Tile Layer ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (tileRef.current) {
      map.removeLayer(tileRef.current);
      tileRef.current = null;
    }
    const cfg = TILES[mapType];
    tileRef.current = L.tileLayer(cfg.url, cfg.opts as L.TileLayerOptions).addTo(map);
  }, [mapType]);

  // ── Redraw Boundary Polygons ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    // flyTo on a zero-size (hidden-tab) container yields NaN and crashes the page: only fly when the map has a real size
    if (map.getSize().x > 0 && map.getSize().y > 0 && Number.isFinite(parcel.lat) && Number.isFinite(parcel.lon)) {
      map.flyTo([parcel.lat, parcel.lon], 15, { duration: 0.8 });
    }
    if (boundaryRef.current) {
      map.removeLayer(boundaryRef.current);
    }
    const g = L.layerGroup();

    THEN_MALAI_PARCELS.forEach((p) => {
      const dLat = 0.0004,
        dLon = 0.00048;
      const coords = (p as any).coords as [number, number][] | undefined;
      const poly: L.LatLngExpression[] = coords || [
        [p.lat + dLat, p.lon - dLon],
        [p.lat + dLat, p.lon + dLon],
        [p.lat - dLat, p.lon + dLon],
        [p.lat - dLat, p.lon - dLon],
      ];
      const sel = p.id === selId;

      // 1. Cadastral Boundary Layer
      if (layers.cadastral) {
        const isMountainShaded = sel && isShadowObstructed;
        const sat = satOverview?.parcels?.[p.id];
        const cc = colorBy === "health" ? healthColor(sat?.status) : cropColor(p.crop);
        const hasIssue = colorBy === "crop" && p.issueCode !== "healthy";
        const polyLayer = L.polygon(poly, {
          color: sel ? (isMountainShaded ? "#38bdf8" : "#f97316") : cc,
          fillColor: sel
            ? isMountainShaded
              ? "rgba(14, 116, 144, 0.35)"
              : "rgba(249, 115, 22, 0.22)"
            : hexA(cc, 0.2),
          weight: sel ? 2.5 : 1.4,
          fillOpacity: 1,
          dashArray: sel ? undefined : hasIssue ? "4 3" : undefined,
        });

        // 2. Survey Labels (Decluttered: full badge for selected, compact ID badge for others)
        if (layers.survey) {
          const statusSuffix = sel
            ? shadowPos.alt <= 0
              ? " · 🌑 Night"
              : isShadowObstructed
              ? " · ⛰ Shaded"
              : " · ☀ Sunlit"
            : "";
          const labelText = sel
            ? `${p.id} · ${p.crop}${layers.fmb ? " (FMB)" : ""}${statusSuffix} ◀`
            : colorBy === "health"
              ? `${p.id} · ${p.crop} · ${sat && sat.ndvi != null ? `NDVI ${sat.ndvi} (${sat.status}${sat.change != null ? `, ${sat.change > 0 ? "+" : ""}${sat.change}` : ""})` : "no clear satellite view"}`
              : `${p.id} · ${p.crop} · ${p.stage}${hasIssue ? ` · ⚠ ${p.issue}` : ""}`;
          polyLayer.bindTooltip(labelText, {
            permanent: sel,
            sticky: !sel,
            direction: sel ? "center" : "top",
            className: sel ? "tm-parcel-lbl-selected" : "tm-parcel-lbl-compact",
          });
        }
        polyLayer.on("click", () => handleParcelChange(p.id));
        polyLayer.addTo(g);
      }

      // 3. FMB Field Subdivision Lines
      if (layers.fmb) {
        if (coords && coords.length === 4) {
          const mid01: L.LatLngExpression = [(coords[0][0] + coords[1][0]) / 2, (coords[0][1] + coords[1][1]) / 2];
          const mid23: L.LatLngExpression = [(coords[2][0] + coords[3][0]) / 2, (coords[2][1] + coords[3][1]) / 2];
          const mid12: L.LatLngExpression = [(coords[1][0] + coords[2][0]) / 2, (coords[1][1] + coords[2][1]) / 2];
          const mid30: L.LatLngExpression = [(coords[3][0] + coords[0][0]) / 2, (coords[3][1] + coords[0][1]) / 2];
          L.polyline([mid01, mid23], { color: sel ? "#fb923c" : "#f97316", weight: 0.8, dashArray: "3 3", opacity: 0.7 }).addTo(g);
          L.polyline([mid12, mid30], { color: sel ? "#fb923c" : "#f97316", weight: 0.8, dashArray: "3 3", opacity: 0.7 }).addTo(g);
        } else {
          const fmbLine1: L.LatLngExpression[] = [
            [p.lat - dLat, p.lon],
            [p.lat + dLat, p.lon],
          ];
          const fmbLine2: L.LatLngExpression[] = [
            [p.lat, p.lon - dLon],
            [p.lat, p.lon + dLon],
          ];
          L.polyline(fmbLine1, { color: sel ? "#fb923c" : "#f97316", weight: 0.8, dashArray: "3 3", opacity: 0.7 }).addTo(g);
          L.polyline(fmbLine2, { color: sel ? "#fb923c" : "#f97316", weight: 0.8, dashArray: "3 3", opacity: 0.7 }).addTo(g);
        }
      }

      // 4. Western Ghats Ridge Line
      if (layers.ridge && sel) {
        const ridgeLon = p.lon - p.ridgeKm * 0.009;
        const ridgeLine: L.LatLngExpression[] = [
          [p.lat - 0.003, ridgeLon],
          [p.lat, ridgeLon + 0.0005],
          [p.lat + 0.003, ridgeLon - 0.0003],
        ];
        L.polyline(ridgeLine, { color: "#ea580c", weight: 2.5, opacity: 0.85, dashArray: "5 4" })
          .bindTooltip(`Western Ghats Ridge (~${p.ridgeM}m, ${p.ridgeKm}km W)`, {
            permanent: true,
            direction: "right",
            className: "tm-parcel-lbl-selected",
          })
          .addTo(g);
      }
    });

    g.addTo(map);
    boundaryRef.current = g;
  }, [selId, layers.cadastral, layers.fmb, layers.survey, layers.ridge, parcel, colorBy, satOverview]);

  // ── Resize Observer ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const t = setTimeout(() => map.invalidateSize(), 150);
    return () => clearTimeout(t);
  }, [mapSz]);

  const handleParcelChange = (id: ParcelId) => {
    setSelId(id);
    setShowMenu(false);
    const p = THEN_MALAI_PARCELS.find((x) => x.id === id)!;
    onParcelChange?.(id, p.lat, p.lon, p.crop, p.elevM);
  };

  const handleTimeChange = (m: number | ((prev: number) => number)) => {
    setCurMin((prev) => (typeof m === "function" ? m(prev) : m));
    setIsLive(false);
  };

  const jumpToCurrentTime = useCallback(() => {
    const n = new Date();
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    setDate(today);
    setCurMin(n.getHours() * 60 + n.getMinutes() + n.getSeconds() / 60);
    setIsLive(true);
  }, []);

  // ── Design Tokens ──
  const GLASS = "rgba(6,10,20,0.85)";
  const BDR = "rgba(251,191,36,0.25)";
  const TXT = "rgba(226,232,240,0.92)";
  const SUB = "rgba(148,163,184,0.8)";
  const MUT = "rgba(100,116,139,0.65)";
  const ACC = "#f59e0b";

  const row = (l: string, v: string, c = TXT) => (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
      <span style={{ fontSize: 9.5, color: SUB }}>{l}</span>
      <span style={{ fontFamily: "monospace", fontSize: 10.5, fontWeight: 700, color: c }}>{v}</span>
    </div>
  );
  const div = <div style={{ height: 1, background: "rgba(251,191,36,0.13)", margin: "6px 0" }} />;

  // Current Cloud Cover at curMin
  const curHour = Math.floor(curMin / 60);
  const curCloud = cloudHourly[curHour]?.cloudCoverPct ?? 45;
  const directRad = cloudHourly[curHour]?.directRadWm2 ?? null;

  // Observed Sunshine Data (Last 6 hours satellite/radiation integration)
  const observedData: ObservedSunshineData | null = useMemo(() => {
    if (!cloudHourly || cloudHourly.length === 0) return null;
    const currentHour = Math.floor(shadowMin / 60);
    const startH = Math.max(0, currentHour - 5);
    const last6 = cloudHourly.slice(startH, currentHour + 1);
    if (last6.length === 0) return null;

    let totalObs = 0;
    let totalClearSky = 0;

    last6.forEach((pt) => {
      const ptMin = pt.hour * 60 + 30;
      const ptPos = calcPos(parcel.lat, parcel.lon, dateUTC, ptMin);
      const elevRad = Math.max(0, Math.sin((ptPos.alt * Math.PI) / 180));
      const clearSkyW = elevRad > 0 ? 1000 * elevRad : 0;
      const obsW = pt.directRadWm2 ?? (pt.cloudCoverPct != null ? (1 - pt.cloudCoverPct / 100) * clearSkyW : clearSkyW * 0.75);
      totalObs += obsW;
      totalClearSky += clearSkyW;
    });

    const pct = totalClearSky > 0 ? Math.min(100, Math.max(0, Math.round((totalObs / totalClearSky) * 100))) : 0;
    const hStr = String(currentHour).padStart(2, "0");
    return {
      last6hPct: pct,
      obsWh: totalObs,
      clearSkyWh: totalClearSky,
      timestamp: `${dateToStr(date)} ${hStr}:00`,
    };
  }, [cloudHourly, shadowMin, parcel, dateUTC, date]);

  return (
    <>
      <style>{`
        .tm-dark-tile {
          filter: invert(100%) hue-rotate(180deg) brightness(78%) contrast(115%) !important;
        }
        .tm-sidebar-scroll {
          scrollbar-width: none !important;
          -ms-overflow-style: none !important;
        }
        .tm-sidebar-scroll::-webkit-scrollbar {
          display: none !important;
          width: 0px !important;
          height: 0px !important;
          background: transparent !important;
        }
        .tm-parcel-lbl-selected {
          background: rgba(6,10,22,0.94) !important;
          border: 1.5px solid #fbbf24 !important;
          color: #fbbf24 !important;
          font: 700 9.5px/1.2 'DM Mono',monospace !important;
          padding: 3px 7px !important;
          border-radius: 5px !important;
          white-space: nowrap !important;
          box-shadow: 0 2px 12px rgba(251,191,36,0.35) !important;
          z-index: 1000 !important;
        }
        .tm-parcel-lbl-compact {
          background: rgba(6,10,22,0.82) !important;
          border: 1px solid rgba(34,211,238,0.4) !important;
          color: rgba(34,211,238,0.95) !important;
          font: 600 8.5px/1 'DM Mono',monospace !important;
          padding: 2px 5px !important;
          border-radius: 4px !important;
          white-space: nowrap !important;
          box-shadow: 0 1px 6px rgba(0,0,0,0.4) !important;
        }
        .tm-parcel-lbl-selected::before, .tm-parcel-lbl-compact::before { display:none !important; }
      `}</style>

      <div ref={outerRef} id="then-malai-map-view" style={{ position: "absolute", inset: 0, zIndex: 20, overflow: "hidden", background: "#060a14" }}>
        {/* 1. Real Leaflet Map */}
        <div ref={mapContainerRef} style={{ position: "absolute", inset: 0, zIndex: 0, background: "#060a14" }} />

        {/* 2. Dynamic Day/Night Lighting */}
        {layers.lighting && (
          <div
            id="tm-night-overlay"
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 1,
              pointerEvents: "none",
              background: night.bg,
              opacity: night.opacity,
              transition: "opacity 0.25s ease, background 0.25s ease",
            }}
          />
        )}

        {/* 3. Soft NWP Cloud Overlay Layer (Step 5) */}
        {layers.cloudForecast && (
          <div
            id="tm-cloud-forecast-overlay"
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 2,
              pointerEvents: "none",
              background: `radial-gradient(ellipse at 50% 50%, rgba(224, 242, 254, ${(curCloud / 100) * 0.38}) 0%, rgba(186, 230, 253, ${(curCloud / 100) * 0.25}) 50%, rgba(56, 189, 248, ${(curCloud / 100) * 0.15}) 100%)`,
              opacity: layers.cloudForecast ? 1 : 0,
              transition: "opacity 0.35s ease, background 0.35s ease",
            }}
          />
        )}

        {/* 4. Transparent SVG Arc Overlay */}
        {layers.sunArc && <SunOverlay lat={parcel.lat} lon={parcel.lon} date={dateUTC} curMin={curMin} w={mapSz.w} h={mapSz.h} />}

        {/* 5. Map Legend Overlay (Step 6) */}


        {showCal && (
          <div style={{ position: "absolute", top: 80, left: 10, zIndex: 50 }}>
            <CalendarPicker value={date} onChange={(d) => { setDate(d); setIsLive(false); }} onClose={() => setShowCal(false)} />
          </div>
        )}

        {/* 7a. PER-PARCEL SUNLIGHT HOURS + GIS EXPORT */}


        {/* 7b. DRAGGABLE MAP LAYERS CONTROL */}

        {/* Top bar: solar ephemeris | map style + crop view | shadow time, one fixed line across the map */}
        <div className="pointer-events-none absolute inset-x-3 top-3 z-20 flex flex-wrap items-start justify-between gap-2">
          <SolarPanel
            parcels={THEN_MALAI_PARCELS}
            selId={selId}
            onParcel={(id) => {
              setSelId(id as ParcelId);
              const p = THEN_MALAI_PARCELS.find((x) => x.id === id)!;
              onParcelChange?.(id as ParcelId, p.lat, p.lon, p.crop, p.elevM);
            }}
            village="Then Malai · Demo Village"
            dateLabel={date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
            onDate={() => setShowCal((v) => !v)}
            timeLabel={isLive ? "LIVE" : hm(curMin)}
            onNow={jumpToCurrentTime}
            isLive={isLive}
            alt={pos.alt}
            az={pos.az}
            compass={pos.compass}
            noon={sd.noon}
            dayMin={sd.dayMin}
            rise={sd.rise}
            set={sd.set}
            golden={sd.ghEnd}
            directStart={parcelSummary.directSunStartStr}
            directEnd={parcelSummary.directSunEndStr}
            demNote={`Copernicus 30m DEM • Ridge cutoff ${parcelSummary.directSunEndStr}`}
          />
          <div className="pointer-events-auto order-none flex h-[50px] items-center gap-2 max-sm:order-first max-sm:w-full max-sm:justify-center">
            <div className="flex items-center gap-2 rounded-2xl border border-border bg-overlay/90 p-1.5 shadow-xl backdrop-blur-xl">
              <div className="flex items-center gap-1">
                {([["crop", "Crop"], ["health", narrow ? "Health" : "Crop health"]] as const).map(([k, label]) => (
                  <button key={k} type="button" onClick={() => setColorBy(k)}
                    className={`h-9 whitespace-nowrap rounded-lg px-4 text-sm font-semibold transition ${colorBy === k ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-accent"}`}>
                    {label}
                  </button>
                ))}
              </div>
              <MapTypeSwitch value={mapType} onChange={setMapType} />
            </div>
          </div>
          <ShadowPanel
            headerExtra={
              <DraggableLayersControl
                layers={layers}
                onToggleLayer={toggleLayer}
                onResetLayers={() => setLayers(DEFAULT_TM_LAYERS)}
                mapWidth={mapSz.w}
                mapHeight={mapSz.h}
                docked
                compact
              />
            }
            shadowMin={shadowMin}
            onShadowMin={setShadowMin}
            onDragStart={() => setIsDraggingSlider(true)}
            onDragEnd={() => setIsDraggingSlider(false)}
            status={shadowPos.alt <= 0 ? "night" : isShadowObstructed ? "shaded" : "direct"}
            startMin={parcelSummary.windows[0]?.startMin ?? sd.rise}
            cutoffMin={parcelSummary.windows[parcelSummary.windows.length - 1]?.endMin ?? sd.set}
            alt={shadowPos.alt}
            az={shadowPos.az}
            horizon={shadowHorizonAngle}
            obstructed={isShadowObstructed}
            cloud={cloudHourly[Math.floor(shadowMin / 60)]?.cloudCoverPct ?? curCloud}
            parcelId={parcel.id}
            onSync={() => setShadowMin(curMin)}
            observed={
              observedData ? (
                <div className="rounded border border-brand/20 bg-brand/5 p-1.5 font-mono text-[8px] text-orange-200/90">
                  <div className="flex items-center justify-between font-semibold text-brand-soft">
                    <span>Observed Sunshine</span>
                    <span>{observedData.last6hPct}% of clear-sky</span>
                  </div>
                  <div className="mt-0.5 flex justify-between text-[7px] text-stone-400">
                    <span>Obs: {Math.round(observedData.obsWh)} Wh/m²</span>
                    <span>Ref: {Math.round(observedData.clearSkyWh)} Wh/m²</span>
                  </div>
                </div>
              ) : undefined
            }
          />
        </div>

        {/* Map tools: one tidy row above the time bar, so nothing floats over anything else */}
        <div className="pointer-events-none absolute inset-x-3 bottom-[92px] z-30 flex flex-wrap items-end gap-2">
          {/* the epidemic icon is joined to the layers button as one pill */}
          <div className="flex items-end [&_#epi-btn]:rounded-l-none [&_#epi-btn]:border-l-0 [&>div:first-child_button]:rounded-r-none">
            <QuickSatelliteLayers getMap={() => mapRef.current} docked />
            <EpidemicDemo getMap={() => mapRef.current} selectedId={selId} />
            <FieldZonesOverlay getMap={() => mapRef.current} />
          </div>
          {/* sunlight hours and legend, joined, at the right end of the row */}
          <div className="ml-auto flex items-end [&_#tm-sunlight-btn]:rounded-r-none">
            <ParcelSunlightPanel
              docked
              parcels={THEN_MALAI_PARCELS as any}
              horizonProfiles={horizonProfiles}
              date={dateUTC}
              selId={selId}
              onSelect={(id) => {
                setSelId(id as ParcelId);
                const p = THEN_MALAI_PARCELS.find((x) => x.id === id)!;
                onParcelChange?.(id as ParcelId, p.lat, p.lon, p.crop, p.elevM);
              }}
            />
            <MapLegend colorBy={colorBy} docked joined />
          </div>
        </div>

        {/* 8. HORIZONTAL 24-HOUR SOLAR SCRUBBER */}
        <SolarTimeline
          minutes={curMin}
          rise={sd.rise}
          set={sd.set}
          isLive={isLive}
          playing={playing}
          onTogglePlay={() => setPlaying((v) => !v)}
          onNow={jumpToCurrentTime}
          onScrub={handleTimeChange}
          onDragStart={() => setIsDraggingSlider(true)}
          onDragEnd={() => setIsDraggingSlider(false)}
        />

      </div>
    </>
  );
}

export type { ParcelId as ThenMalaiParcelId };

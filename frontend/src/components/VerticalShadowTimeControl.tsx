/**
 * VerticalShadowTimeControl.tsx
 *
 * Dedicated 24-Hour Vertical Shadow Time Control for Then Malai:
 *  - Independent 24-hour time scrubber (24:00 to 00:00).
 *  - Minute-level continuous dragging with pointer events.
 *  - Visually renders calculated terrain mountain-shade intervals along the vertical rail.
 *  - Real-time mountain obstruction status & astronomy readout.
 *  - Separates terrain shadow from numerical cloud forecast and observed satellite radiation.
 */

import React, { useCallback, useEffect, useRef } from "react";
import { Mountain, Sun, Eclipse, Cloud, Info, Radio, Clock } from "lucide-react";
import {
  calcPos,
  lookupHorizonAngle,
  type HorizonPoint,
  type ShadedInterval,
  type SolarPos,
} from "../lib/solarGeometry";

export interface ObservedSunshineData {
  last6hPct: number;
  obsWh: number;
  clearSkyWh: number;
  timestamp: string;
}

export interface VerticalShadowTimeControlProps {
  shadowMin: number;
  onShadowMinChange: (m: number | ((prev: number) => number)) => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  date: Date;
  parcel: {
    id: string;
    lat: number;
    lon: number;
    elevM: number;
    crop: string;
    ridgeKm: number;
    ridgeM: number;
  };
  horizonProfile: HorizonPoint[];
  shadedIntervals: ShadedInterval[];
  cloudCoverPct: number;
  observedData?: ObservedSunshineData | null;
  solarTimeMin: number;
}

export function VerticalShadowTimeControl({
  shadowMin,
  onShadowMinChange,
  onDragStart,
  onDragEnd,
  date,
  parcel,
  horizonProfile,
  shadedIntervals,
  cloudCoverPct,
  observedData,
  solarTimeMin,
}: VerticalShadowTimeControlProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Compute shadow sun position and horizon obstruction for shadowMin
  const dateUTC = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const pos: SolarPos = calcPos(parcel.lat, parcel.lon, dateUTC, shadowMin);
  const horizonAngle = lookupHorizonAngle(horizonProfile, pos.az);
  const isNight = pos.alt <= 0;
  const isObstructed = pos.alt > 0 && pos.alt <= horizonAngle;

  const fmt = (m: number) => {
    const h = Math.floor(m / 60) % 24;
    const mi = Math.floor(m % 60);
    return `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
  };

  // Convert client Y coordinate to minutes (Top is 24:00 = 1440m, Bottom is 00:00 = 0m)
  const readPointerPos = useCallback(
    (e: React.PointerEvent | PointerEvent) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const relativeY = (e.clientY - rect.top) / rect.height; // 0 at top, 1 at bottom
      const clamped = Math.max(0, Math.min(1, relativeY));
      // Top = 1440, Bottom = 0
      let m = (1 - clamped) * 1440;
      if (e.shiftKey) {
        m = Math.round(m);
      } else {
        m = Math.round(m / 5) * 5;
      }
      onShadowMinChange(Math.max(0, Math.min(1440, m)));
    },
    [onShadowMinChange]
  );

  useEffect(() => {
    const onPointerMove = (e: PointerEvent) => {
      if (isDraggingRef.current) {
        e.preventDefault();
        readPointerPos(e);
      }
    };
    const onPointerUp = () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
        onDragEnd?.();
      }
    };
    window.addEventListener("pointermove", onPointerMove, { passive: false });
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [readPointerPos, onDragEnd]);

  // Major ticks: 24, 21, 18, 15, 12, 09, 06, 03, 00
  const TICKS = [24, 21, 18, 15, 12, 9, 6, 3, 0];

  // Fraction from top (0 at 24:00, 1 at 00:00)
  const knobPctFromTop = (1 - shadowMin / 1440) * 100;

  return (
    <div
      id="then-malai-vertical-shadow-time-control"
      style={{
        position: "absolute",
        top: 10,
        right: 10,
        bottom: 95,
        width: 178,
        zIndex: 12,
        background: "rgba(6, 10, 20, 0.92)",
        border: "1px solid rgba(251, 191, 36, 0.28)",
        borderRadius: 11,
        backdropFilter: "blur(20px)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.75)",
        padding: "8px 9px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
        pointerEvents: "auto",
        userSelect: "none",
      }}
    >
      {/* 1. Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          paddingBottom: 4,
          borderBottom: "1px solid rgba(251,191,36,0.16)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <Eclipse size={12} style={{ color: "#38bdf8" }} />
          <span
            style={{
              font: "700 8.5px/1 'DM Mono',monospace",
              color: "#38bdf8",
              letterSpacing: "0.07em",
              textTransform: "uppercase",
            }}
          >
            Shadow Time
          </span>
        </div>
        <span
          style={{
            fontSize: 6.5,
            fontFamily: "monospace",
            color: "#fbbf24",
            background: "rgba(251,191,36,0.12)",
            border: "1px solid rgba(251,191,36,0.25)",
            padding: "1px 4px",
            borderRadius: 3,
            fontWeight: 700,
          }}
        >
          24H RULER
        </span>
      </div>

      {/* 2. Vertical 24-Hour Scrubber Rail & Status */}
      <div style={{ display: "flex", gap: 8, flex: 1, minHeight: 180 }}>
        {/* Vertical Scrubber Track */}
        <div
          ref={trackRef}
          role="slider"
          aria-label="24-Hour Terrain Shadow Time Scrubber"
          aria-valuemin={0}
          aria-valuemax={1440}
          aria-valuenow={Math.round(shadowMin)}
          tabIndex={0}
          onPointerDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            isDraggingRef.current = true;
            onDragStart?.();
            readPointerPos(e);
          }}
          onKeyDown={(e) => {
            const step = e.shiftKey ? 1 : 5;
            if (e.key === "ArrowUp") onShadowMinChange((m: number) => Math.min(1440, m + step));
            if (e.key === "ArrowDown") onShadowMinChange((m: number) => Math.max(0, m - step));
            if (e.key === "PageUp") onShadowMinChange((m: number) => Math.min(1440, m + 60));
            if (e.key === "PageDown") onShadowMinChange((m: number) => Math.max(0, m - 60));
          }}
          style={{
            position: "relative",
            width: 32,
            height: "100%",
            borderRadius: 6,
            background: "linear-gradient(to bottom, #080e1a 0%, #1e3a5f 25%, #f59e0b 50%, #1e3a5f 75%, #080e1a 100%)",
            border: "1px solid rgba(56,189,248,0.35)",
            cursor: "ns-resize",
            flexShrink: 0,
            overflow: "hidden",
            boxShadow: "inset 0 0 6px rgba(0,0,0,0.6)",
          }}
        >
          {/* Shaded Mountain Intervals along the rail */}
          {shadedIntervals.map((int, i) => {
            const topPct = (1 - int.endMin / 1440) * 100;
            const heightPct = ((int.endMin - int.startMin) / 1440) * 100;
            return (
              <div
                key={i}
                title={`Mountain Shade: ${int.startStr} - ${int.endStr} IST`}
                style={{
                  position: "absolute",
                  top: `${topPct.toFixed(1)}%`,
                  height: `${heightPct.toFixed(1)}%`,
                  left: 0,
                  right: 0,
                  background: "rgba(14, 116, 144, 0.75)",
                  borderTop: "1px solid #38bdf8",
                  borderBottom: "1px solid #38bdf8",
                  zIndex: 2,
                }}
              />
            );
          })}

          {/* Hour Tick Markers */}
          {TICKS.map((h) => {
            const topPct = (1 - (h * 60) / 1440) * 100;
            return (
              <div
                key={h}
                style={{
                  position: "absolute",
                  top: `${topPct}%`,
                  left: 2,
                  right: 2,
                  transform: "translateY(-50%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  pointerEvents: "none",
                  zIndex: 3,
                }}
              >
                <span style={{ fontSize: 6.5, fontFamily: "monospace", color: "rgba(255,255,255,0.7)", fontWeight: 700 }}>
                  {String(h).padStart(2, "0")}
                </span>
                <div style={{ width: 4, height: 1, background: "rgba(255,255,255,0.5)" }} />
              </div>
            );
          })}

          {/* Draggable Knob */}
          <div
            style={{
              position: "absolute",
              top: `${knobPctFromTop}%`,
              left: 0,
              right: 0,
              transform: "translateY(-50%)",
              height: 14,
              background: "#38bdf8",
              border: "1.5px solid #ffffff",
              borderRadius: 3,
              boxShadow: "0 0 8px #38bdf8, 0 2px 4px rgba(0,0,0,0.8)",
              zIndex: 5,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div style={{ width: 8, height: 1.5, background: "#080e1a", borderRadius: 1 }} />
          </div>
        </div>

        {/* Right Status Panel */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 5, minWidth: 0 }}>
          {/* Time & State Box */}
          <div
            style={{
              padding: "4px 6px",
              borderRadius: 6,
              background: "rgba(0,0,0,0.4)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div style={{ fontSize: 7, color: "rgba(148,163,184,0.7)", fontFamily: "monospace", textTransform: "uppercase" }}>
              SHADOW TIME
            </div>
            <div style={{ fontSize: 11.5, fontWeight: 800, color: "#38bdf8", fontFamily: "monospace" }}>
              {fmt(shadowMin)} <span style={{ fontSize: 8, fontWeight: 600, color: "rgba(148,163,184,0.7)" }}>IST</span>
            </div>

            {/* Terrain State Badge */}
            <div
              style={{
                marginTop: 3,
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "2px 5px",
                borderRadius: 4,
                background: isNight
                  ? "rgba(100,116,139,0.2)"
                  : isObstructed
                  ? "rgba(14,116,144,0.3)"
                  : "rgba(245,158,11,0.2)",
                border: `1px solid ${
                  isNight ? "#64748b" : isObstructed ? "#38bdf8" : "#fbbf24"
                }`,
                fontSize: 8,
                fontWeight: 700,
                fontFamily: "monospace",
                color: isNight ? "#94a3b8" : isObstructed ? "#38bdf8" : "#fbbf24",
              }}
            >
              {isNight ? (
                <>🌑 NIGHT</>
              ) : isObstructed ? (
                <>
                  <Mountain size={10} /> ⛰ SHADED
                </>
              ) : (
                <>
                  <Sun size={10} /> ☀ DIRECT SUN
                </>
              )}
            </div>
          </div>

          {/* Astronomy & Horizon Metrics */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr",
              gap: 2,
              fontSize: 7.5,
              fontFamily: "monospace",
              background: "rgba(0,0,0,0.25)",
              padding: "4px 5px",
              borderRadius: 5,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(148,163,184,0.8)" }}>Sun altitude:</span>
              <span style={{ fontWeight: 700, color: pos.alt > 0 ? "#fbbf24" : "#94a3b8" }}>{pos.alt}°</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(148,163,184,0.8)" }}>Sun azimuth:</span>
              <span style={{ fontWeight: 700, color: "#f8fafc" }}>{pos.az}°</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(148,163,184,0.8)" }}>Terrain horizon:</span>
              <span style={{ fontWeight: 700, color: "#38bdf8" }}>{horizonAngle}°</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(148,163,184,0.8)" }}>Mountain obstruct:</span>
              <span
                style={{
                  fontWeight: 800,
                  color: isNight ? "#94a3b8" : isObstructed ? "#38bdf8" : "#22c55e",
                }}
              >
                {isNight ? "NIGHT" : isObstructed ? "YES" : "NO"}
              </span>
            </div>
          </div>

          {/* Explanation Text */}
          <div
            style={{
              fontSize: 6.8,
              lineHeight: 1.25,
              fontFamily: "monospace",
              color: isNight ? "#94a3b8" : isObstructed ? "#7dd3fc" : "#fef08a",
              padding: "2px 4px",
              background: "rgba(0,0,0,0.2)",
              borderRadius: 4,
            }}
          >
            {isNight
              ? "Night: Sun below astronomical horizon"
              : isObstructed
              ? "Mountain shade: Terrain blocks direct sunlight"
              : "Direct sunlight: Terrain does not block the Sun"}
          </div>
        </div>
      </div>

      {/* 3. Cloud Effect (Clear Spatial Disclaimer) */}
      <div
        style={{
          padding: "4px 5px",
          borderRadius: 5,
          background: "rgba(0,0,0,0.3)",
          border: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          flexDirection: "column",
          gap: 1.5,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 3.5 }}>
            <Cloud size={10} style={{ color: "#67e8f9" }} />
            <span style={{ fontSize: 7.5, fontWeight: 700, color: "#67e8f9", fontFamily: "monospace" }}>
              Cloud Effect
            </span>
          </div>
          <span style={{ fontSize: 7.5, fontWeight: 800, color: "#f8fafc", fontFamily: "monospace" }}>
            {cloudCoverPct}%
          </span>
        </div>
        <div style={{ fontSize: 6.5, color: "rgba(148,163,184,0.7)", fontFamily: "monospace", lineHeight: 1.2 }}>
          Cloud-shadow position not spatially modeled
        </div>
      </div>

      {/* 4. Observed Sunshine Layer (Additive from Open-Meteo ~2km endpoint) */}
      {observedData && (
        <div
          style={{
            padding: "4px 5px",
            borderRadius: 5,
            background: "rgba(14,116,144,0.12)",
            border: "1px solid rgba(56,189,248,0.25)",
            display: "flex",
            flexDirection: "column",
            gap: 2,
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <Radio size={9} style={{ color: "#38bdf8" }} />
              <span style={{ fontSize: 7, fontWeight: 700, color: "#38bdf8", fontFamily: "monospace" }}>
                OBSERVED SUNSHINE
              </span>
            </div>
            <span style={{ fontSize: 6.5, color: "rgba(148,163,184,0.7)", fontFamily: "monospace" }}>~2 km</span>
          </div>
          <div style={{ fontSize: 7, color: "#f8fafc", fontFamily: "monospace" }}>
            Last 6h: <strong style={{ color: "#fbbf24" }}>{observedData.last6hPct}%</strong> of clear-sky
          </div>
          <div style={{ fontSize: 6.5, color: "rgba(148,163,184,0.8)", fontFamily: "monospace" }}>
            Obs: {Math.round(observedData.obsWh)} Wh/m² · Ref: {Math.round(observedData.clearSkyWh)} Wh/m²
          </div>
        </div>
      )}

      {/* 5. Utility / Sync Button */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
        <button
          onClick={() => onShadowMinChange(solarTimeMin)}
          title={`Sync Shadow Time (${fmt(shadowMin)}) to Solar Simulation Time (${fmt(solarTimeMin)})`}
          style={{
            border: "1px solid rgba(56,189,248,0.3)",
            background: "rgba(56,189,248,0.08)",
            color: "#38bdf8",
            borderRadius: 4,
            padding: "2px 5px",
            fontSize: 7,
            fontFamily: "monospace",
            fontWeight: 700,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 3,
          }}
        >
          <Clock size={8} />
          <span>Sync to Solar Time</span>
        </button>

        <span style={{ fontSize: 6.5, color: "rgba(148,163,184,0.6)", fontFamily: "monospace" }}>
          Parcel {parcel.id}
        </span>
      </div>
    </div>
  );
}

/**
 * DraggableLayersControl.tsx
 *
 * Compact, draggable map layers control for the Then Malai Map View:
 *  - Fully draggable with pointer events (mouse & touch) within map bounds.
 *  - Prevents accidental map panning while dragging.
 *  - Differentiates drag from tap/click (opens/closes layer popover).
 *  - Smart popover anchoring based on current screen quadrant.
 *  - Persists chosen position in localStorage with bounding box validation.
 *  - Default position: clean upper-left corner of the map (x: 236, y: 12).
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Layers, X, Check, GripVertical } from "lucide-react";
import type { ThenMalaiLayers } from "./ThenMalaiMapView";
import { TM_LAYERS_CONFIG } from "./ThenMalaiMapView";

const STORAGE_KEY = "cropsy_tm_layers_pos_v1";

const GLASS = "color-mix(in oklab, var(--overlay) 94%, transparent)";
const BDR = "var(--border)";
const ACC = "var(--primary)";
const TXT = "var(--foreground)";
const MUT = "var(--muted-foreground)";

export interface DraggableLayersControlProps {
  layers: ThenMalaiLayers;
  onToggleLayer: (key: keyof ThenMalaiLayers) => void;
  onResetLayers: () => void;
  mapWidth: number;
  mapHeight: number;
  /** sit in the map's bottom tool row: no dragging, the popover opens upward */
  docked?: boolean;
  /** small icon-only button (used inside the Shadow time panel) */
  compact?: boolean;
}

export function DraggableLayersControl({
  layers,
  onToggleLayer,
  onResetLayers,
  mapWidth,
  mapHeight,
  docked = false,
  compact = false,
}: DraggableLayersControlProps) {
  const btnRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // Approximate control dimensions for boundary clamping
  const BTN_W = 132;
  const BTN_H = 36;

  // Clamp position within map viewport
  const clampPos = useCallback(
    (x: number, y: number, mw = mapWidth, mh = mapHeight) => {
      const minX = 10;
      const maxX = Math.max(minX, mw - BTN_W - 10);
      const minY = 10;
      const maxY = Math.max(minY, mh - BTN_H - 10);
      return {
        x: Math.round(Math.max(minX, Math.min(maxX, x))),
        y: Math.round(Math.max(minY, Math.min(maxY, y))),
      };
    },
    [mapWidth, mapHeight]
  );

  // Initialize position from localStorage or clean upper-left default (x: 236, y: 12)
  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          return { x: parsed.x, y: parsed.y };
        }
      }
    } catch {
      // ignore JSON error
    }
    // Default: bottom-left, just above the "16 layers" chip (placed once the map size is known, below)
    return { x: 12, y: 0 };
  });
  const usedDefault = useRef(!(() => { try { return !!localStorage.getItem(STORAGE_KEY); } catch { return false; } })());

  // Re-clamp position if map dimensions resize
  useEffect(() => {
    if (mapWidth > 0 && mapHeight > 0) {
      if (usedDefault.current) {
        usedDefault.current = false;
        setPos(clampPos(12, mapHeight - (mapWidth < 640 ? 150 : 100), mapWidth, mapHeight));
        return;
      }
      setPos((prev) => {
        const clamped = clampPos(prev.x, prev.y, mapWidth, mapHeight);
        if (clamped.x !== prev.x || clamped.y !== prev.y) {
          return clamped;
        }
        return prev;
      });
    }
  }, [mapWidth, mapHeight, clampPos]);

  // Save to localStorage when position changes
  const savePos = (p: { x: number; y: number }) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
    } catch {
      // ignore storage errors
    }
  };

  // Drag handling refs
  const dragStartRef = useRef<{
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
    hasMoved: boolean;
  }>({
    startX: 0,
    startY: 0,
    initialX: 0,
    initialY: 0,
    hasMoved: false,
  });

  const handlePointerDown = (e: React.PointerEvent) => {
    // Only respond to main button / touch
    if (e.button !== 0 && e.pointerType === "mouse") return;

    // Prevent Leaflet map panning or document selection
    e.stopPropagation();

    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: pos.x,
      initialY: pos.y,
      hasMoved: false,
    };

    setIsDragging(true);

    const onPointerMove = (ev: PointerEvent) => {
      ev.stopPropagation();
      const dx = ev.clientX - dragStartRef.current.startX;
      const dy = ev.clientY - dragStartRef.current.startY;

      if (!dragStartRef.current.hasMoved && Math.hypot(dx, dy) > 4) {
        dragStartRef.current.hasMoved = true;
      }

      if (dragStartRef.current.hasMoved) {
        const newX = dragStartRef.current.initialX + dx;
        const newY = dragStartRef.current.initialY + dy;
        const clamped = clampPos(newX, newY);
        setPos(clamped);
      }
    };

    const onPointerUp = (ev: PointerEvent) => {
      ev.stopPropagation();
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      setIsDragging(false);

      if (dragStartRef.current.hasMoved) {
        // Finished dragging: persist new position
        const dx = ev.clientX - dragStartRef.current.startX;
        const dy = ev.clientY - dragStartRef.current.startY;
        const finalPos = clampPos(dragStartRef.current.initialX + dx, dragStartRef.current.initialY + dy);
        setPos(finalPos);
        savePos(finalPos);
      } else {
        // Was a click/tap: toggle popover
        setIsOpen((open) => !open);
      }
    };

    window.addEventListener("pointermove", onPointerMove, { passive: false });
    window.addEventListener("pointerup", onPointerUp, { passive: false });
  };

  const activeCount = Object.values(layers).filter(Boolean).length;

  // Compute smart popover alignment
  const openAbove = compact ? false : docked || pos.y > mapHeight * 0.55;
  const alignRight = compact ? true : !docked && pos.x > mapWidth * 0.6;

  return (
    <div
      ref={btnRef}
      id="then-malai-draggable-layers-control"
      style={{
        position: docked ? "relative" : "absolute",
        ...(docked ? {} : { left: pos.x, top: pos.y }),
        zIndex: 25,
        pointerEvents: "auto",
        touchAction: "none",
        userSelect: "none",
      }}
    >
      {/* Movable Button Pill */}
      <div
        id="tm-layers-toggle-btn"
        {...(docked ? { onClick: () => setIsOpen((o) => !o) } : { onPointerDown: handlePointerDown })}
        title={compact ? `Map overlays (${activeCount} on)` : docked ? "Show or hide map overlays" : "Drag to move · Click to toggle map layers"}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: compact ? "0 6px" : "0 12px 0 8px",
          height: compact ? 24 : 36,
          borderRadius: compact ? 6 : 6,
          background: isOpen ? "color-mix(in oklab, var(--primary) 18%, var(--secondary))" : "var(--secondary)",
          border: `1px solid ${isOpen ? ACC : isDragging ? "#38bdf8" : BDR}`,
          color: isOpen ? ACC : TXT,
          backdropFilter: "blur(18px)",
          boxShadow: isDragging
            ? "0 8px 24px rgba(0,0,0,0.8), 0 0 12px rgba(56,189,248,0.4)"
            : "0 4px 16px rgba(0,0,0,0.55)",
          cursor: docked ? "pointer" : isDragging ? "grabbing" : "grab",
          transform: isDragging ? "scale(1.04)" : "scale(1)",
          transition: isDragging ? "none" : "transform 0.15s ease, border-color 0.15s ease, background 0.15s ease",
        }}
      >
        {!docked && <GripVertical size={13} style={{ color: isDragging ? "#38bdf8" : "rgba(148,163,184,0.5)", flexShrink: 0 }} />}
        <Layers size={compact ? 13 : 16} style={{ color: isOpen ? ACC : "var(--foreground)", flexShrink: 0 }} />
        {!compact && (
          <>
            <span style={{ fontSize: 14, fontWeight: 500 }}>Overlays</span>
            <span
              style={{
                background: "color-mix(in oklab, var(--primary) 22%, transparent)",
                color: ACC,
                borderRadius: 999,
                padding: "0 7px",
                fontSize: 11,
                fontFamily: "monospace",
                fontWeight: 800,
              }}
            >
              {activeCount}
            </span>
          </>
        )}
      </div>

      {/* Layer Control Popover */}
      {isOpen && (
        <>
          {/* Backdrop dismiss */}
          <div
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(false);
            }}
            style={{ position: "fixed", inset: 0, zIndex: 198 }}
          />

          <div
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            style={{
              position: "absolute",
              ...(openAbove ? { bottom: "calc(100% + 6px)" } : { top: "calc(100% + 6px)" }),
              ...(alignRight ? { right: 0 } : { left: 0 }),
              zIndex: 199,
              width: 254,
              background: "rgba(8,12,22,0.97)",
              border: `1px solid ${BDR}`,
              borderTop: openAbove ? `1px solid ${BDR}` : `3px solid ${ACC}`,
              borderBottom: openAbove ? `3px solid ${ACC}` : `1px solid ${BDR}`,
              borderRadius: 11,
              backdropFilter: "blur(20px)",
              boxShadow: "0 12px 40px rgba(0,0,0,0.8)",
              padding: 10,
              pointerEvents: "auto",
            }}
          >
            {/* Popover Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 7,
                paddingBottom: 5,
                borderBottom: "1px solid rgba(251,191,36,0.14)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <Layers size={12} style={{ color: ACC }} />
                <span style={{ font: "700 9px 'DM Mono',monospace", color: ACC, letterSpacing: "0.06em" }}>
                  MAP OVERLAYS ({TM_LAYERS_CONFIG.length})
                </span>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  border: 0,
                  background: "transparent",
                  color: MUT,
                  cursor: "pointer",
                  padding: 2,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <X size={11} />
              </button>
            </div>

            {/* Layer Toggles */}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {TM_LAYERS_CONFIG.map((cfg) => {
                const on = layers[cfg.key];
                return (
                  <label
                    key={cfg.key}
                    onClick={() => onToggleLayer(cfg.key)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 7,
                      padding: "4px 6px",
                      borderRadius: 6,
                      background: on ? "rgba(255,255,255,0.04)" : "transparent",
                      cursor: "pointer",
                      userSelect: "none",
                      transition: "background 0.15s ease",
                    }}
                  >
                    <div
                      style={{
                        width: 13,
                        height: 13,
                        borderRadius: 3,
                        border: `1px solid ${on ? cfg.color : "rgba(100,116,139,0.5)"}`,
                        background: on ? cfg.color : "transparent",
                        display: "grid",
                        placeItems: "center",
                        flexShrink: 0,
                      }}
                    >
                      {on && <Check size={9} strokeWidth={3} color="#000" />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 9,
                          fontWeight: on ? 700 : 500,
                          color: on ? TXT : MUT,
                          fontFamily: "monospace",
                        }}
                      >
                        {cfg.label}
                      </div>
                      <div style={{ fontSize: 7.5, color: "rgba(148,163,184,0.65)" }}>{cfg.desc}</div>
                    </div>
                  </label>
                );
              })}
            </div>

            {/* Footer summary + Reset */}
            <div
              style={{
                marginTop: 7,
                paddingTop: 5,
                borderTop: "1px solid rgba(251,191,36,0.12)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                fontSize: 8.5,
                fontFamily: "monospace",
              }}
            >
              <span style={{ color: MUT }}>
                {activeCount} / {TM_LAYERS_CONFIG.length} active
              </span>
              <button
                onClick={onResetLayers}
                style={{
                  border: 0,
                  background: "transparent",
                  color: ACC,
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "2px 4px",
                }}
              >
                Reset
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

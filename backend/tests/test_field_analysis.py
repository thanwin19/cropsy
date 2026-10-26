"""Satellite evidence and pixel-level zones: real data checks plus deterministic synthetic-raster unit tests (the synthetic ones prove the maths, not live capability)."""
import numpy as np
import pytest

from app import field_analysis as fa


def test_canonical_keeps_latest_scene_monthly_and_baseline_separate():
    c = fa.canonical("TM-05")
    assert c["latest_scene"]["date"] and c["latest_scene"]["indices"]["ndvi"] is not None
    assert c["monthly_composite"]["month"] and c["monthly_composite"]["n_valid"] > 0
    assert "different" in c["why_values_differ"]
    assert c["baseline"]["ndvi"] is not None
    assert c["latest_scene"]["basis"] != c["monthly_composite"]["basis"]


def test_unknown_parcel_has_no_evidence_and_no_zones():
    assert fa.canonical("TM-999") is None
    z = fa.zones("TM-999")
    assert z["available"] is False and "unknown parcel" in z["reason"]
    assert "no satellite summary" in fa.evidence_text("TM-999")


def test_zones_are_real_and_labelled():
    z = fa.zones("TM-05")
    assert z["available"] and z["provenance"]["month"] and z["n_valid"] >= fa.MIN_PARCEL_PX
    assert {c["class"] for c in z["cells"]} <= {"lower", "typical", "higher", "no_data"}
    for c in z["cells"]:
        if c["class"] != "no_data":
            assert c["n_valid"] >= fa.MIN_CELL_PX and abs(c["vs_parcel"]) < 1.0
    assert "diagnosis" in z["caution"]


def test_missing_month_reports_unavailable_instead_of_inventing():
    z = fa.zones("TM-05", month="1999-01")
    assert z["available"] is False


def test_layer_mean_matches_zone_mean():
    pm = fa.parcel_layer_mean("TM-05", "ndvi")
    z = fa.zones("TM-05")
    assert abs(pm["mean"] - z["parcel_mean"]) < 0.002


def test_synthetic_raster_flags_the_dark_corner_only(monkeypatch):
    """A flat field with one clearly low corner: that corner, and no other, must be 'lower'. Synthetic data: tests the maths only."""
    ring = [[77.30, 8.90], [77.3011, 8.90], [77.3011, 8.9011], [77.30, 8.9011]]
    monkeypatch.setattr(fa, "_rings", lambda: {"SYN": ring})
    m, s, w, n, e, W, H = fa._grid_geometry()
    # pretend the raster is flat 0.6, except the south-east (low-lat, high-lon) third of the parcel at 0.3
    vals = np.full((H, W), 0.6, dtype=np.float32)
    valid = np.ones((H, W), dtype=bool)
    x0, x1 = int((77.3007 - w) / (e - w) * W), int((77.3011 - w) / (e - w) * W) + 1
    y0, y1 = int((n - 8.9004) / (n - s) * H), int((n - 8.9) / (n - s) * H) + 1
    vals[y0:y1, x0:x1] = 0.3
    monkeypatch.setattr(fa, "_values", lambda layer, month: (vals, valid))
    z = fa.zones("SYN", "ndvi", "2026-09")
    assert z["available"]
    lower = {c["name"] for c in z["cells"] if c["class"] == "lower"}
    assert "south-east" in lower and "north-west" not in lower


def test_synthetic_clouded_parcel_is_not_analysed(monkeypatch):
    monkeypatch.setattr(fa, "_values", lambda layer, month: (np.zeros((468, 572), np.float32), np.zeros((468, 572), bool)))
    z = fa.zones("TM-05")
    assert z["available"] is False and "clear pixels" in z["reason"]

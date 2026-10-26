"""Satellite edge cases: stale imagery, missing baseline, too few clear pixels, and values of different kinds that must never be mixed.
The decision rules are tested with controlled observations and synthetic rasters (deterministic; they prove the rules, not live satellite capability)."""
import importlib
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from app import field_analysis as fa

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture(scope="module")
def build_satellite():
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("build_satellite")


def _obs(as_of: date, days_ago_and_ndvi):
    return [{"date": (as_of - timedelta(days=d)).isoformat(), "ndvi_mean": v} for d, v in days_ago_and_ndvi]


AS_OF = date(2026, 10, 3)


def test_stale_latest_scene_is_insufficient_not_normal(build_satellite):
    obs = _obs(AS_OF, [(120, 0.5), (140, 0.52), (160, 0.55), (180, 0.5)])        # the last pass is 120 days old
    e = build_satellite.summarise({"P": obs}, AS_OF)["P"]
    assert e["status"] == "insufficient" and e["change"] is None and "120 days old" in e["reason"]


def test_fewer_than_two_baseline_scenes_is_insufficient(build_satellite):
    obs = _obs(AS_OF, [(3, 0.40), (30, 0.42)])                                     # only one scene in the 15 to 75 day window
    e = build_satellite.summarise({"P": obs}, AS_OF)["P"]
    assert e["status"] == "insufficient" and e["change"] is None and "baseline" in e["reason"]


def test_no_observations_at_all(build_satellite):
    e = build_satellite.summarise({"P": []}, AS_OF)["P"]
    assert e["status"] == "insufficient" and "no cloud-free observation" in e["reason"]


@pytest.mark.parametrize("latest,expected", [(0.28, "stress"), (0.34, "watch"), (0.39, "normal"), (0.60, "normal")])
def test_status_thresholds_are_the_documented_ones(build_satellite, latest, expected):
    obs = _obs(AS_OF, [(3, latest), (30, 0.40), (45, 0.40), (60, 0.40)])           # baseline 0.40
    assert build_satellite.summarise({"P": obs}, AS_OF)["P"]["status"] == expected


def _fake_data(monkeypatch, summary_entry, scene_ndvi=0.30, scene_date="2026-09-29", monthly_mean=0.20, as_of="2026-10-03"):
    row = {"parcel_id": "TM-05", "date": scene_date, "ndvi_mean": str(scene_ndvi), "evi_mean": "0.2", "savi_mean": "0.2", "ndre_mean": "0.1", "ndmi_mean": "0.0", "ndwi_mean": "-0.4",
           "ndvi_std": "0.05", "valid_frac": "0.9", "n_pixels": "150", "scene_cloud_pct": "10",
           **{f"ndvi_{s}": "0.3" for s in fa.SECTORS}}
    monkeypatch.setattr(fa, "_observations", lambda: {"TM-05": [row]})
    monkeypatch.setattr(fa, "_summary", lambda: {"as_of": as_of, "source": "test", "parcels": {"TM-05": summary_entry}})
    monkeypatch.setattr(fa, "parcel_layer_mean", lambda pid, layer, month=None: {"layer": "ndvi", "month": "2026-09", "mean": monthly_mean, "n_valid": 120, "n_inside": 150})


def test_stale_scene_is_marked_stale_and_the_prompt_says_so(monkeypatch):
    _fake_data(monkeypatch, {"baseline_ndvi": 0.4, "n_baseline": 3, "change": None, "status": "insufficient", "reason": "latest observation is 80 days old"}, scene_date="2026-07-15")
    c = fa.canonical("TM-05")
    assert c["latest_scene"]["stale"] is True and c["status"] == "insufficient"
    text = fa.evidence_text("TM-05")
    assert "STALE" in text and "latest observation is 80 days old" in text


def test_missing_baseline_tells_the_model_not_to_compare(monkeypatch):
    _fake_data(monkeypatch, {"baseline_ndvi": None, "n_baseline": 0, "change": None, "status": "insufficient", "reason": "fewer than 2 baseline observations"})
    text = fa.evidence_text("TM-05")
    assert "None" not in text.split("Monthly composite")[0].replace("None-", "")           # no 'baseline NDVI None' leaks into the prompt
    assert "No historical baseline is available" in text and "fewer than 2 baseline observations" in text and "do not compare" in text
    assert fa.canonical("TM-05").get("baseline") is None


def test_latest_scene_and_monthly_composite_stay_separate_and_labelled(monkeypatch):
    _fake_data(monkeypatch, {"baseline_ndvi": 0.4, "n_baseline": 4, "change": -0.1, "status": "stress"}, scene_ndvi=0.30, monthly_mean=0.20)
    c = fa.canonical("TM-05")
    assert c["latest_scene"]["indices"]["ndvi"] == 0.30 and c["monthly_composite"]["mean"] == 0.20       # two different numbers, neither overwritten
    assert c["latest_scene"]["basis"] != c["monthly_composite"]["basis"]
    text = fa.evidence_text("TM-05")
    assert "Latest scene" in text and "Monthly composite" in text and "different quantities" in text


def test_unknown_parcel_returns_no_invented_values():
    assert fa.canonical("TM-ZZZ") is None
    assert "no satellite summary" in fa.evidence_text("TM-ZZZ")


def test_parcel_with_too_few_clear_pixels_gives_no_zones(monkeypatch):
    """The parcel's pixels are mostly cloud-masked: 20 clear pixels of about 150. Zones must be reported unavailable, with the count."""
    vals = np.full((468, 572), 0.5, dtype=np.float32)
    valid = np.zeros((468, 572), dtype=bool)
    pm = fa._parcel_mask("TM-05")
    mask, x0, y0 = pm
    ys, xs = np.nonzero(mask)
    for i in range(20):
        valid[y0 + ys[i], x0 + xs[i]] = True
    monkeypatch.setattr(fa, "_values", lambda layer, month: (vals, valid))
    z = fa.zones("TM-05")
    assert z["available"] is False and z["n_valid"] == 20 and "clear pixels" in z["reason"]
    assert "cells" not in z


def test_flat_field_reports_no_lower_zone(monkeypatch):
    vals = np.full((468, 572), 0.55, dtype=np.float32)
    monkeypatch.setattr(fa, "_values", lambda layer, month: (vals, np.ones((468, 572), dtype=bool)))
    z = fa.zones("TM-05")
    assert z["available"] and not [c for c in z["cells"] if c["class"] in ("lower", "higher")]


def test_api_returns_unavailable_states_not_conclusions(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app import field_api
    _fake_data(monkeypatch, {"baseline_ndvi": None, "n_baseline": 0, "change": None, "status": "insufficient", "reason": "fewer than 2 baseline observations"})
    monkeypatch.setattr(fa, "zones", lambda pid, layer="ndvi", month=None: {"parcel_id": pid, "available": False, "reason": "only 20 clear pixels"})
    app = FastAPI()
    app.include_router(field_api.router)
    c = TestClient(app)
    r = c.get("/api/field-health/TM-05").json()
    assert r["evidence"]["status"] == "insufficient" and r["zones"]["available"] is False and "clear pixels" in r["zones"]["reason"]
    assert c.get("/api/field-health/TM-NOPE").status_code == 404

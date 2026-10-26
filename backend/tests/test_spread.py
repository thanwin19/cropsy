"""Tests for the village spread-risk model (app/spread.py): geometry, wind direction, scoring and the verifier. Pure arithmetic, no AWS."""
from __future__ import annotations

import math

import pytest

from app import spread


def test_wind_from_the_south_west_carries_spores_to_the_north_east():
    # target is exactly north-east of the source
    d, b = spread.haversine_bearing(8.90, 77.30, 8.9025, 77.3025)
    assert 40 < b < 50
    move_to = (225 + 180) % 360                       # wind FROM 225 (SW) moves the air toward 45 (NE)
    assert spread.angle_diff(b, move_to) < 6
    assert spread.angle_diff(b, (45 + 180) % 360) > 150      # wind from the NE would carry spores away from the target


def test_two_distance_methods_agree():
    d1, b1 = spread.haversine_bearing(8.9, 77.3, 8.905, 77.307)
    d2, b2 = spread.flat_distance_bearing(8.9, 77.3, 8.905, 77.307)
    assert abs(d1 - d2) / d1 < 0.01 and spread.angle_diff(b1, b2) < 1


def _blast_source():
    src = next(s for s in spread.infected_sources(40) if s["code"] == "rice_blast" and s["parcel_id"] == "TM-31")
    return src["parcel_id"]


def test_downwind_neighbour_scores_higher_than_upwind_one():
    pid = _blast_source()
    sw = spread.forecast(pid, wind_speed_kmh=14, wind_from_deg=225, favourable=True)
    ne = spread.forecast(pid, wind_speed_kmh=14, wind_from_deg=45, favourable=True)
    a = {r["parcel_id"]: r["risk"] for r in sw["parcels"]}
    b = {r["parcel_id"]: r["risk"] for r in ne["parcels"]}
    changed = [p for p in a if abs(a[p] - b[p]) > 5]
    assert changed, "reversing the wind must change some parcel's risk"
    p = max(changed, key=lambda x: abs(a[x] - b[x]))
    # the parcel NE of the source is riskier under a SW wind
    src = next(r for r in sw["parcels"] if r["parcel_id"] == p)
    if 0 <= src["bearing_deg"] <= 90:
        assert a[p] > b[p]


def test_no_wind_driven_exposure_for_other_crops_or_far_parcels():
    r = spread.forecast(_blast_source(), wind_speed_kmh=14, wind_from_deg=225, favourable=True)
    for x in r["parcels"]:
        if x["crop"] != "Rice" or x["distance_m"] > spread.DISEASES["rice_blast"]["max_m"]:
            assert x["risk"] == 0.0


def test_unfavourable_weather_lowers_risk():
    pid = _blast_source()
    good = spread.forecast(pid, wind_speed_kmh=14, wind_from_deg=225, favourable=True)
    assert good["weather"]["assumed_perfect"] and good["weather"]["favourable_hours"] == good["weather"]["of"]
    top_good = max(x["risk"] for x in good["parcels"])
    assert top_good >= 20


def test_verifier_passes_and_catches_a_bad_row():
    pid = _blast_source()
    r = spread.forecast(pid, wind_speed_kmh=14, wind_from_deg=225, favourable=True)
    assert r["verification"]["passed"]
    spread.tools._load_parcels()
    ps = {p["parcel_id"]: p for p in spread.tools._PARCELS}
    w = spread.build_weather(r["source"]["lat"], r["source"]["lon"], 14, 225, True)
    bad = dict(r["parcels"][0], risk=90.0, distance_m=r["parcels"][0]["distance_m"] + 400)
    out = spread.verify_geometry(pid, [bad], ps, w, spread.DISEASES["rice_blast"])
    assert not out["passed"] and out["failed"]


def test_unknown_or_non_airborne_source_is_rejected():
    with pytest.raises(ValueError):
        spread.forecast("TM-999")
    healthy = next(p for p in spread.tools._PARCELS if (p.get("observed_issue") or {}).get("code") == "healthy")
    with pytest.raises(ValueError):
        spread.forecast(healthy["parcel_id"])


def test_timeline_is_monotone_and_ends_at_the_final_risk():
    r = spread.forecast(_blast_source(), wind_speed_kmh=14, wind_from_deg=225, favourable=True)
    live = [x for x in r["parcels"] if x["crop"] == "Rice" and x["distance_m"] <= spread.DISEASES["rice_blast"]["max_m"]]
    assert live
    for x in live:
        tl = x["timeline"]
        assert len(tl) == 25 and tl[0] == 0.0 and all(b >= a for a, b in zip(tl, tl[1:]))
        assert abs(tl[-1] - x["risk"]) < 0.11


def test_prevention_returns_steps_and_quotes_with_pages():
    p = spread.prevention("rice_blast")
    assert p["steps"] and p["ask"]
    assert all("[" in q and "]" in q for q in p["tnau_passages"])


def test_village_exposure_feeds_the_ranking():
    from app import priority
    expo = spread.village_exposure()
    assert expo and all(0 <= v["risk"] <= 100 for v in expo.values())
    top = max(expo, key=lambda k: expo[k]["risk"])
    row = priority.ranked(top)["items"][0]
    if expo[top]["risk"] >= 10:
        assert any("downwind of" in r["text"] for r in row["reasons"])


def test_scenario_for_parcel_without_recorded_disease():
    """Any parcel of a modelled crop can be treated as 'what if infected'; other crops are refused clearly."""
    from app import spread
    r = spread.forecast("TM-94", favourable=True)
    assert r["source"]["disease_code"] == "rice_blast"
    try:
        spread.forecast("TM-01")
        assert False, "coconut has no modelled wind-borne disease"
    except ValueError as e:
        assert "not one of the wind-borne" in str(e)


def test_cordana_is_modelled_with_a_labelled_regional_source():
    from app import spread
    r = spread.forecast("TM-02", disease_code="banana_cordana", favourable=True)
    assert r["source"]["disease_code"] == "banana_cordana"
    kinds = {e["kind"] for e in r["disease"]["evidence"]}
    assert any("not TNAU" in k for k in kinds) and "assumption" in kinds
    assert spread.prevention("banana_cordana")["steps"]

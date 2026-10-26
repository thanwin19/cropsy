"""Index Results windows, comparison and field directions (synthetic cache, no files needed)."""
from app import indices as ix


def _prime(series, sectors=None):
    ix._cache.clear()
    ix._cache.update(series={"ndvi": {"P": series}}, village_median={"ndvi": {d: 0.5 for d, _ in series}}, sectors={"P": sectors or {}})


def test_window_and_previous_window_are_equal_length_and_adjacent():
    _prime([("2026-01-10", 0.40), ("2026-01-20", 0.50), ("2026-03-10", 0.60), ("2026-03-20", 0.70)])
    r = ix.results("P", "2026-03-01", "2026-03-31", ["ndvi"])
    s = r["indices"]["ndvi"]
    assert r["previous_window"] == ["2026-01-30", "2026-02-28"] or r["previous_window"][1] == "2026-02-28"
    assert s["n_points"] == 2 and s["window_mean"] == 0.65
    assert s["previous_mean"] is None and s["change_vs_previous"] is None      # nothing in the previous 31 days
    r2 = ix.results("P", "2026-02-01", "2026-03-31", ["ndvi"])                  # previous window now holds January
    assert r2["indices"]["ndvi"]["previous_mean"] == 0.45 and r2["indices"]["ndvi"]["change_vs_previous"] == 0.2


def test_points_carry_the_village_median_for_the_same_date():
    _prime([("2026-03-10", 0.6)])
    assert ix.results("P", "2026-03-01", "2026-03-31", ["ndvi"])["indices"]["ndvi"]["points"][0]["village_median"] == 0.5


def test_field_directions_point_to_the_weakest_side_and_ignore_flat_fields():
    sec = {"N": 0.60, "NE": 0.62, "E": 0.61, "SE": 0.60, "S": 0.40, "SW": 0.55, "W": 0.59, "NW": 0.60}
    _prime([("2026-03-10", 0.6)], {"2026-03-10": sec})
    d = ix.field_directions("P")
    assert d["weakest"] == "S" and "S side" in d["note"]
    _prime([("2026-03-10", 0.6)], {"2026-03-10": {k: 0.6 for k in sec}})
    assert "differ little" in ix.field_directions("P")["note"]


def test_every_catalogued_index_is_returned():
    _prime([("2026-03-10", 0.6)])
    assert set(ix.results("P", "2026-03-01", "2026-03-31")["indices"]) == set(ix.CATALOG)

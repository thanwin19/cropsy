from app import stcr


def test_equation_arithmetic_and_clipping():
    r = stcr.calculate(50, {"N": 200, "P2O5": 10, "K2O": 300}, stcr.EXAMPLE["coefficients"], 2.0)
    n = r["nutrients"]
    assert n["N"]["dose_kg_ha"] == round(4.25 * 50 - 0.45 * 200, 1)       # 122.5
    assert n["P2O5"]["dose_kg_ha"] == round(3.55 * 50 - 4.89 * 10, 1)     # 128.6
    assert n["K2O"]["dose_kg_ha"] == round(max(0, 2.10 * 50 - 0.18 * 300), 1)  # 105 - 54 = 51
    assert r["field_products"]["urea_kg"] > 0


def test_negative_dose_is_zero_with_warning():
    r = stcr.calculate(10, {"N": 400, "P2O5": 1, "K2O": 1}, stcr.EXAMPLE["coefficients"])
    assert r["nutrients"]["N"]["dose_kg_ha"] == 0 and any("N:" in w for w in r["warnings"])


def test_rejects_bad_input():
    import pytest
    with pytest.raises(ValueError):
        stcr.calculate(0, {"N": 1, "P2O5": 1, "K2O": 1}, stcr.EXAMPLE["coefficients"])
    with pytest.raises(ValueError):
        stcr.calculate(40, {"N": 1}, stcr.EXAMPLE["coefficients"])


def test_tnau_row11_with_fym():
    """TNAU row 11 (rice, Kharif, Manakkarai series): FN = 4.25 T - 0.60 SN - 0.79 ON, etc."""
    row = next(p for p in stcr.PRESETS if p["id"] == "tnau_row11_rice_kharif_manakkarai")
    r = stcr.calculate(50, {"N": 180, "P2O5": 12, "K2O": 150}, row["coefficients"], None, {"N": 20, "P2O5": 5, "K2O": 10})
    n = r["nutrients"]
    assert n["N"]["dose_kg_ha"] == round(4.25 * 50 - 0.60 * 180 - 0.79 * 20, 1)
    assert n["P2O5"]["dose_kg_ha"] == round(2.71 * 50 - 4.39 * 12 - 0.89 * 5, 1)
    assert n["K2O"]["dose_kg_ha"] == round(3.83 * 50 - 0.60 * 150 - 0.82 * 10, 1)
    assert "Tenkasi" in row["source"]

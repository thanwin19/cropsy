"""stcr.py: soil-test crop response (STCR) fertilizer calculator. Plain arithmetic, no model.

STCR fertilizer adjustment equations have the form  F = a*T - b*S  for each nutrient, where T is the yield target (q/ha), S the soil-test value (kg/ha available nutrient),
and a (kg nutrient per quintal of target yield) and b (soil-test efficiency) are fitted per crop, variety, soil series and season. They are NOT portable: the same crop gives different
a and b in a different soil series. So the coefficients are an input (from your soil lab or the state STCR table for your soil series). One published example is included only to show the
arithmetic; it comes from a Madhya Pradesh / Uttar Pradesh study, not Tamil Nadu, and must not be used for Then Malai.
"""
from __future__ import annotations

from app.steps.calculator import compute

EXAMPLE = {
    "id": "example_rice_mp_up",
    "label": "Worked example only: rice, Choudhary et al. 2020 (BHU / JNKVV)",
    "source": "Journal of Pharmacognosy and Phytochemistry 2020; 9(5): 1000-1003 (https://phytojournal.com/archives/2020/vol9issue5/PartN/9-5-51-872.pdf)",
    "applies_to": "the soils of that study (Madhya Pradesh / Uttar Pradesh), not Tamil Nadu",
    "coefficients": {"N": [4.25, 0.45], "P2O5": [3.55, 4.89], "K2O": [2.10, 0.18]},
}


def calculate(target_q_ha: float, soil: dict, coeffs: dict, area_ha: float | None = None, organic_credit: dict | None = None) -> dict:
    if target_q_ha <= 0 or target_q_ha > 120:
        raise ValueError("yield target must be between 0 and 120 quintals per hectare")
    out, warnings = {}, []
    for nutrient in ("N", "P2O5", "K2O"):
        if nutrient not in coeffs or nutrient not in soil:
            raise ValueError(f"need both the equation coefficients and the soil-test value for {nutrient}")
        a, b, *rest = (float(x) for x in coeffs[nutrient])
        oe = rest[0] if rest else 1.0      # efficiency of the organic nutrient (TNAU's third coefficient); 1.0 when the equation has none
        s = float(soil[nutrient])
        if s < 0:
            raise ValueError("soil-test values cannot be negative")
        credit = oe * float((organic_credit or {}).get(nutrient, 0))
        raw = a * target_q_ha - b * s - credit
        dose = max(0.0, raw)
        if raw < 0:
            warnings.append(f"{nutrient}: soil supply already covers the target (equation gives {raw:.0f}); dose set to 0, not negative")
        out[nutrient] = {"a": a, "b": b, "soil_test_kg_ha": s, "organic_credit_kg_ha": credit, "dose_kg_ha": round(dose, 1)}
    res = {"target_q_ha": target_q_ha, "nutrients": out, "warnings": warnings,
           "per_ha_products": compute(1.0, out["N"]["dose_kg_ha"], out["P2O5"]["dose_kg_ha"], out["K2O"]["dose_kg_ha"]),
           "method": "F = a x T - b x S per nutrient, clipped at zero; products: urea 46% N, DAP 18-46-0 (its N is credited), MOP 60% K2O"}
    if area_ha:
        res["area_ha"] = area_ha
        res["field_products"] = compute(area_ha, out["N"]["dose_kg_ha"], out["P2O5"]["dose_kg_ha"], out["K2O"]["dose_kg_ha"])
    res["limits"] = ["The coefficients decide the answer. Use the ones for your crop, variety, soil series and season from the TNAU / soil-lab STCR table; ask your soil testing lab or KVK.",
                     "Split the nitrogen and apply as your agriculture officer advises; this gives the total, not the schedule."]
    return res


# Published TNAU equations (rice, STCR-IPNS table): https://agritech.tnau.ac.in/agriculture/agri_Nutrient_mainfeild_%20P_K_Rice.html (read 2026-10-13).
# Variables: T target yield q/ha; S soil-test N, P, K (kg/ha); O nutrient from organic manure (kg/ha). Coefficients are [a, b] with the organic credit passed separately.
# The page names the soil series but NOT the districts. Then Malai is in Tenkasi (formerly part of Tirunelveli); whether its soil belongs to the Manakkarai series is NOT
# established here, so a soil lab or KVK must confirm the series before this row is used. The page's "maintenance / maximum dose" notes are not applied by this calculator.
_SRC = "TNAU Agritech STCR-IPNS rice table (agritech.tnau.ac.in/agriculture/agri_Nutrient_mainfeild_ P_K_Rice.html)"
_NOTE = "Series is not tied to a district on the TNAU page. Tenkasi was part of Tirunelveli, but confirm the soil series with your soil lab or KVK before using this row."
PRESETS = [
    {"id": "tnau_row11_rice_kharif_manakkarai", "label": "TNAU rice, Kharif (Kuruvai), river alluvium, Manakkarai series", "source": _SRC + ". " + _NOTE,
     "coefficients": {"N": [4.25, 0.60, 0.79], "P2O5": [2.71, 4.39, 0.89], "K2O": [3.83, 0.60, 0.82]}},
    {"id": "tnau_rice_rabi_manakkarai", "label": "TNAU rice, Rabi (Pishanam), river alluvium, Manakkarai series", "source": _SRC + ". " + _NOTE,
     "coefficients": {"N": [4.47, 0.58, 0.79], "P2O5": [2.66, 3.68, 0.89], "K2O": [4.08, 0.65, 0.82]}},
    {"id": "tnau_rice_kharif_noyyal", "label": "TNAU rice, Kharif, river alluvium, Noyyal series", "source": _SRC,
     "coefficients": {"N": [4.39, 0.52, 0.80], "P2O5": [2.22, 3.63, 0.98], "K2O": [2.44, 0.39, 0.72]}},
    {"id": "tnau_rice_kharif_irugur", "label": "TNAU rice, Kharif, red sandy loam, Irugur series", "source": _SRC,
     "coefficients": {"N": [5.19, 0.89, 0.98], "P2O5": [2.27, 4.50, 1.09], "K2O": [3.11, 0.59, 1.02]}},
    {"id": "tnau_rice_kharif_kalathur", "label": "TNAU rice, Kharif (Kuruvai), black alluvium, Kalathur series", "source": _SRC,
     "coefficients": {"N": [5.29, 0.75, 0.89], "P2O5": [1.65, 1.76, 0.78], "K2O": [2.73, 0.37, 0.82]}},
]

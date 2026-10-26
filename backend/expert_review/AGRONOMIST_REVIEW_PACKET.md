# Agronomist review packet (Cropsy release candidate)

Reviewer must check against CURRENT CIB&RC registrations and product labels, not TNAU text alone. Nothing below is verified. Fill the Decision and Correction columns.

## A. Pesticide regulatory status entries (app/pesticides.py REGULATORY)

| Chemical | Status shown to farmers | Basis | Confirmed with CIB&RC | Decision | Correction |
|---|---|---|---|---|---|
| monocrotophos | banned (use) per the 2023 order; the 36% SL window for existing stock was one year | Insecticides (Prohibition) Order 2023, Gazette notification 29 Sep 2023: dicofol, dinocap, methomyl and monocrotophos; monocrotophos 36% SL 'only for clearance of existing stock' | False | | |
| carbofuran | restricted: all formulations except the 3% encapsulated granule (CG) | October 2023 order as reported (S.O. 4294(E) is cited by one secondary source) | False | | |
| paraquat | paraquat dimethyl sulphate is on the banned list; paraquat dichloride is restricted | the Odisha government's 'List of pesticides banned in India' (27 items for manufacture, import and use) names paraquat dimethyl sulphate | False | | |

Also review the full banned / restricted name lists in app/pesticides.py (BANNED, RESTRICTED) and the Tamil transliterations.

## B. Paraquat flag
Current wording: paraquat dimethyl sulphate banned, paraquat dichloride restricted. Question: is this accurate today, and is the farmer-facing wording (refer to KVK, no dose) right?  Decision: ____

## C. Recommendation conflicts (app/conflicts.py)

### turmeric_basal_fym (Turmeric: basal farmyard manure)
- Basal FYM 25 t/ha (with neem or groundnut cake 200 kg/ha), as part of NPK 150:60:108 kg/ha  [Crop Production Guide: Horticulture 2020, TNAU and Directorate of Horticulture, p.186, 2020, Tamil Nadu]
- Basal FYM 10 t, tank silt 10 t, neem cake 200 kg, SSP 150 kg, MOP 25 kg (sole crop)  [Turmeric: Cultivation practices, Spices Board India / ICAR-IISR, p.table, Application time: Basal, None, India (national)]
Which recommendation applies, and under what condition? ____

### rice_zinc_sulphate (Rice: zinc sulphate dose)
- 37.5 kg zinc sulphate per ha mixed with sand to 75 kg and spread on the levelled field, not incorporated  [Crop Production Guide: Agriculture 2020, TNAU, p.31, 2020, Tamil Nadu]
- ZnSO4 25 kg/ha with FeSO4 50 kg/ha and 12.5 t FYM as basal, where zinc and iron deficiency were noted  [Crop Production Guide: Agriculture 2020, TNAU, p.50, 2020, Tamil Nadu]
Which recommendation applies, and under what condition? ____

### chilli_pheromone_traps (Chilli: pheromone traps for Helicoverpa and Spodoptera)
- Pheromone traps for Helicoverpa armigera / Spodoptera litura at 12 per ha  [Crop Production Guide: Horticulture 2020, TNAU and Directorate of Horticulture, p.89, 2020, Tamil Nadu]
- Pheromone trap at 15 per ha for tobacco cutworm (Spodoptera litura)  [TNAU Agritech Crop Protection: Pests of chilli, p.chilli_3.html, None, Tamil Nadu]
- Pheromone trap with Helilure at 15 per ha for gram caterpillar (Helicoverpa armigera)  [TNAU Agritech Crop Protection: Pests of chilli, p.chilli_4.html, None, Tamil Nadu]
Which recommendation applies, and under what condition? ____

## D. Product-dose mappings
For each, confirm the dose belongs to that product, crop and pest, and is on the current label. Items come from the gold set and TNAU text:

| Question | Product -> dose shown | Source page | Current label dose | OK? |
|---|---|---|---|---|
| ragi blast | carbendazim 500 g/ha or iprobenphos 500 ml/ha | ragi p.113 | | |
| blackgram pod/leaf pest | chlorpyriphos 20 EC 3750 ml/ha; chlorantraniliprole 150 ml/ha; flubendiamide 100 ml/ha | blackgram p.152 | | |
| groundnut leaf spot | carbendazim 500 g/ha; mancozeb 1000 g/ha; chlorothalonil 1000 g/ha | groundnut p.206 | | |
Run `python tests/run_gold_live.py` for the current wording and add every other pesticide the reviewer wants checked.

## E. Fertilizer calculations (worked examples from the real calculator, rice, per-hectare blanket doses from TNAU pp.46 and 48)

Conversion rules in code: urea 46% N, DAP 18-46-0 (its N credited against N need), MOP 60% K2O.

**Parcel TM-31 area 1.3 ha**

- 75:25:37.5 kg N:P2O5:K2O per ha (Guide p.48): for 1.3 ha that is N 98 kg, P2O5 32 kg, K2O 49 kg in total, which is about urea 184 kg, DAP 71 kg and MOP 81 kg for the whole parcel.
- 50:25:25 kg N:P2O5:K2O per ha (Guide p.46): for 1.3 ha that is N 65 kg, P2O5 32 kg, K2O 32 kg in total, which is about urea 114 kg, DAP 71 kg and MOP 54 kg for the whole parcel.
- How the totals are worked: urea 46% N; DAP 18-46-0 (its N is credited); MOP 60% K2O; whole kg. Split the nitrogen and apply it at the stages the TNAU guide lists for your variety.

**Parcel TM-31 area 0.2 ha**

- 75:25:37.5 kg N:P2O5:K2O per ha (Guide p.48): for 0.2 ha that is N 15 kg, P2O5 5 kg, K2O 8 kg in total, which is about urea 28 kg, DAP 11 kg and MOP 12 kg for the whole parcel.
- 50:25:25 kg N:P2O5:K2O per ha (Guide p.46): for 0.2 ha that is N 10 kg, P2O5 5 kg, K2O 5 kg in total, which is about urea 17 kg, DAP 11 kg and MOP 8 kg for the whole parcel.
- How the totals are worked: urea 46% N; DAP 18-46-0 (its N is credited); MOP 60% K2O; whole kg. Split the nitrogen and apply it at the stages the TNAU guide lists for your variety.

Independent check of TM-31: recompute each total by hand (dose x area; DAP kg = P2O5/0.46; N credit = DAP x 0.18; urea = remaining N / 0.46; MOP = K2O/0.60).  Result: ____

## F. Split-application guidance
The app quotes TNAU timing text (basal / tillering / panicle initiation) and does not compute splits. Confirm the timing wording for rice, maize, groundnut, and say whether a computed split should be added.  Decision: ____



| Reviewer name / qualification | |
|---|---|
| Date | |
| Overall decision (approve / approve with changes / reject) | |

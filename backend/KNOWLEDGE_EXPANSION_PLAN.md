# Cropsy knowledge expansion: proposed sources and coverage plan (for approval)

Nothing in this plan has been ingested. It was prepared from the repository audit (`scripts/coverage_audit.py`, output in `tests/coverage_audit.json`) and from checks of the sources named below.

## 1. Where the gaps are (874 chunks today)
Covered: rice 166, banana 244, cotton 102, sugarcane 75, coconut 68, groundnut 49, blackgram 48, maize 47, turmeric 36, chilli 26, tomato 13.
Absent: sorghum, pearl millet, finger millet, wheat; redgram, greengram, bengalgram, cowpea, horsegram; soybean, sesame, castor, sunflower; brinjal, bhendi, onion, cabbage, cauliflower, potato, cucurbits; mango, guava, papaya, citrus, pomegranate, grapes; pepper, cardamom, ginger, tea, cashew, arecanut; flowers, fodder, livestock.
Region: every source is Tamil Nadu (TNAU) except one national PDF (Spices Board, turmeric). No other state is covered.

## 2. Batch A: sections of the two TNAU Crop Production Guides we ALREADY HOLD (no new download)
`dataset/knowledge/TNAU_CPG/0c002046_AGRICULTURE.pdf` (460 pages) and `d829671c_HORTICULTURE.pdf` (442 pages) are the same documents that already supply rice, maize, sugarcane, coconut, banana, groundnut, cotton, blackgram, chilli and turmeric. Only ten crops were extracted from them. Their table of contents holds all the crops below. Page numbers are PDF pages found by heading search; the ends are the start of the next crop. Chunk estimates are characters divided by 1000, not a measured chunker run.

| Batch | Crop | Source file | PDF pages | Est. chunks | Gap it fills |
|---|---|---|---|---|---|
| A1 cereals and millets | Sorghum | Agriculture | 77-92 | 33 | absent crop |
| | Pearl millet (cumbu) | Agriculture | 93-104 | 23 | absent crop |
| | Finger millet (ragi) | Agriculture | 105-114 (heading to confirm) | 21 | absent crop |
| | Wheat | Agriculture | 134-136 | 5 | absent crop (TNAU's wheat entry is short) |
| A2 pulses | Redgram | Agriculture | 137-145 | 19 | absent crop |
| | Greengram | Agriculture | 156-164 | 18 | absent crop |
| | Cowpea | Agriculture | 165-169 | 9 | absent crop |
| | Horsegram | Agriculture | 170-172 | 4 | absent crop |
| | Bengalgram | Agriculture | 173-184 | 20 | absent crop |
| A3 vegetables | Tomato (nutrient, pest, planting) | Horticulture | 71-76 | 12 | tomato has no nutrient, pest or harvest chunks |
| | Brinjal | Horticulture | 77-82 | 12 | absent crop |
| | Bhendi (okra) | Horticulture | 83-86 | 7 | absent crop |
| | Cucurbits | Horticulture | 96-120 | 44 | absent group |
| | Cabbage, cauliflower | Horticulture | 133-141 | 16 | absent crops |
| | Carrot, radish, beetroot | Horticulture | 142-147 | 8 | absent crops |
| | Potato | Horticulture | 148-151 | 6 | absent crop |
| | Onion | Horticulture | 165-169 | 9 | absent crop |
| A4 oilseeds | Soybean | Agriculture | 185-189 | 8 | absent crop |
| | Sesame | Agriculture | 209-216 | 14 | absent crop |
| | Castor | Agriculture | 217-226 | 18 | absent crop |
| | Sunflower | Agriculture | 227-234 | 15 | absent crop |
| A5 fruits, plantation, spice, flowers | Mango, guava, papaya, citrus, pomegranate, grapes | Horticulture | 15-20, 31-33, 34-41, 42-43, 47-52 | about 55 | absent crops |
| | Pepper, cardamom, ginger, tea, cashew, arecanut | Horticulture | 179-184, 188-189, 206-216, 237-238 | about 38 | absent crops |
| | Rose, jasmine, marigold | Horticulture | 262-274 | about 22 | flowers |
| A6 cross-cutting | Weeds, soil constraints, micro-irrigation, agrometeorology, forage crops, mushroom | Agriculture | 327-358, 404-436 | not estimated | general topics |

Batches A1-A4 total roughly 340 chunks; A5 about 115 more. A smaller first step is A1 + A2 + the tomato rows of A3.

**Licence and region.** Same publisher, document and status as what is already in use: Tamil Nadu Agricultural University and the Directorates of Agriculture and Horticulture, 2020, region Tamil Nadu. The TNAU portal's disclaimer (`agritech.tnau.ac.in/disclaimer_en.html`) says the material is "provided for information purposes only" and states no open licence. Cropsy uses it as an attributed retrieval source in a prototype; the usage rights for any wider deployment have not been confirmed with TNAU.

**Method.** Add rows to `NEW_SECTIONS` in `scripts/build_knowledge.py`, appended after the existing crops so existing chunk order and embeddings do not move; then `embed_knowledge.py` and `embed_subchunks.py`. Duplicate guard: the 80%-word-overlap check from `ingest_web_docs3.py`. Each batch is measured with `tests/run_retrieval_eval.py` before the next.

## 3. Batch B: other regions and institutions (documents to be confirmed before any download)
Checked here: the pages respond; the documents named were seen only in search results and, for the first, a header request. None has been read or downloaded.

| Source | Publisher, region | What it would add | Status |
|---|---|---|---|
| `https://millets.res.in/pub/2026/GAP-English.pdf` | ICAR-Indian Institute of Millets Research, all India with state-specific practices | Good Agricultural Practices manual for millets (about 127 pages, 21 MB, file dated 23 Feb 2026) | reachable (HTTP 200, application/pdf). Licence not checked |
| `https://millets.res.in/technologies.php` | ICAR-IIMR | kharif and rabi sorghum package-of-practices pages | reachable; specific PDFs not yet located |
| `https://www.pau.edu/content/ccil/pf/pp_rabi.pdf` and `.../pp_kharif.pdf` | Punjab Agricultural University, Punjab | Package of Practices for crops of Punjab (wheat and other rabi and kharif crops); the search listed the rabi edition as 2024-25 | the URLs redirect (HTTP 301 then 200); the content type and the newest edition are not yet confirmed |
| `https://iihr.res.in` | ICAR-Indian Institute of Horticultural Research, Karnataka | fruit and vegetable technology pages | site reachable; no document chosen |
| `https://icar.org.in` | ICAR | umbrella listing of ICAR institutes | reachable |
| `https://ppqs.gov.in` | Plant Protection, Quarantine and Storage, Government of India | the pesticide registration data that Cropsy does not hold today | reachable; no machine-readable list identified yet |

Not reachable from this machine when tested (HTTP failures, cause unknown): iipr.icar.gov.in, iiwbr.icar.gov.in, iivr.icar.gov.in, ctcri.icar.gov.in, farmer.gov.in, cibrc.nic.in. Kerala Agricultural University (kau.in) answered HTTP 403. They are NOT proposed until a working document URL is found.

Licence: government and ICAR sites usually give no explicit open licence on the document. Each document's own copyright page must be read before approval, and "official" will not be treated as "open".

## 4. Region awareness (already partly in place)
- A question that names another state or country is answered as labelled general guidance, because the knowledge base is Tamil Nadu only.
- Proposed next: a `region` field on every chunk (Tamil Nadu, Punjab, India-wide). Retrieval would prefer the question's region and show the other region's guidance as a separate, labelled item. Conflicts (for example TNAU 25 t/ha FYM against Spices Board 10 t/ha for turmeric) stay visible and are not merged.

## 5. What to approve
1. Batch A1 (sorghum, pearl millet, finger millet, wheat) and A2 (five pulses), plus the tomato pages of A3. About 150 chunks, no new download.
2. Whether to pursue Batch B documents (IIMR manual, PAU packages). I will read each document's copyright page and report before any ingestion.
3. The region field (section 4).


---
# Update 2026-10-16: decisions taken and results

## Batch A was approved and ingested in three stages (from the TNAU guides already in the repository)
Chunks 874 before, 1,111 after (117 + 110 + 10). Duplicates dropped: 0. Garbled chunks dropped: 0. Each chunk keeps document, page and a region field (Tamil Nadu). Backups of the chunk file and the embeddings from before Batch A are in `knowledge/chunks.jsonl.bak_before_batchA` and `cache/*.bak_before_batchA`.

| Stage | Crops | Chunks | Questions added | New-question hit@3 | Old 68 questions (hit@1, hit@3, hit@5) |
|---|---|---|---|---|---|
| before | | 874 | | | 0.794, 0.897, 0.941 |
| 1 | sorghum, cumbu, ragi, wheat | +117 | 11 | 0.909 | unchanged, no rank changed |
| 2 | redgram, greengram, cowpea, horsegram, bengalgram | +110 | 12 | 0.917 | unchanged |
| 3 | tomato (guide pages 71-76) | +10 | 7 | 1.000 | unchanged |

Known gaps found: the seed-rate lines of wheat and of bengal gram variety CO 3 sit inside variety tables and rank poorly (M11, B11 miss); wheat STCR equations (guide p136) are numeric tables that the text-quality filter drops, so they are not in the knowledge base. Not ingested in this round: soybean, sesame, castor, sunflower and the vegetables other than tomato (still outside the approved stages).

## Batch B: documents read, NOT ingested. Findings for your decision
| Document | Edition | Pages | Rights statement found in the file | Region | Recommendation |
|---|---|---|---|---|---|
| ICAR-IIMR "Good Agricultural Practices (GAP) Manual for Sustainable Millets Production in India" (millets.res.in/pub/2026/GAP-English.pdf) | December 2025, ISBN 978-93-94673-53-3, file dated 23 Feb 2026 | 147 PDF pages (text says pp 127) | "(c) 2025 ICAR-Indian Institute of Millets Research". No reuse licence is stated. Figures carry individual photo credits. Funded by FAO TCP/RAS/3909 | all India with state-specific practices | usable only with written permission or a stated licence from ICAR-IIMR; ask before ingesting |
| PAU "Package of Practices for Crops of Punjab, Rabi 2025-26" (pau.edu/content/ccil/pf/pp_rabi.pdf) | Vol 42 No 2, August 2025 | 184 | "All matter published in this package is copyright. No part of it should be reproduced without the prior permission of Publisher/Editor." Sold publication | Punjab | NOT usable without written permission from PAU |
| PAU "... Kharif 2026" (pp_kharif.pdf) | Vol 43 No 1, March 2026 | 208 | same copyright sentence | Punjab | NOT usable without written permission |
Current edition: the Rabi URL serves 2025-26 and the Kharif URL serves 2026 today; a Rabi 2026-27 edition was not at that address. The PDFs were downloaded to a scratch folder for reading only and nothing was added to the knowledge base.

## Region field: built (backend and a small frontend control)
`app/region.py` resolves the farmer's region from their words, a saved profile or the selected parcel (country, state, district, zone, and how we know). Chunks and sources carry a region (all Tamil Nadu, except the national Spices Board PDF). Retrieval gives a small bonus to region-matched chunks and a small penalty to other-region chunks without ever removing one. A question that names another state or country is answered as labelled general guidance. When the region is unknown and the question depends on place (sowing time, variety, dose, spray), the answer says the advice is for Tamil Nadu and asks for the state or district. The location is sent only when the farmer sets it, and saved on the device only if they tick "remember".

## Safety review
See `tests/expert_review_queue.json` (reviewer, date and verdict fields are blank by design) and `app/pesticides.py` `REGULATORY` for the regulatory evidence gathered, with its limits. Recommendation conflicts are recorded in `data/knowledge_conflicts.json` (3 entries, all unresolved) and shown to the farmer when the passages are retrieved together.


---
# Update (oilseeds ingested; vegetables proposed; permissions drafted)

## Oilseeds from the TNAU Agriculture guide (stages 4 and 5), approved and ingested
Chunks 1,111 -> 1,198 (+87). Duplicates dropped: 0. Garbled: 0. Pages checked before ingestion: soybean 185-189, sesame 209-216 (text ends on 215), castor 217-226, sunflower 227-234. Sword bean (p190) was not ingested.

| Stage | Crops | Chunks | New questions, hit@1 / hit@3 / hit@5 / MRR | Previous answerable questions |
|---|---|---|---|---|
| 4 | soybean 19, sesame 23 | +42 | 0.75 / 1.00 / 1.00 / 0.875 (8 questions) | 106 questions, identical before and after (0.764 / 0.887 / 0.925 / 0.825), no rank changed |
| 5 | castor 22, sunflower 23 | +45 | 7 questions, all found in the top 3; crop hit@3 1.00 for castor and sunflower | 114 questions: 0.763 / 0.895 / 0.930 / 0.829, no rank changed |

All questions together now (178 questions, 125 answerable): hit@1 0.784, hit@3 0.904, hit@5 0.936, MRR 0.844.
Crop precision@5 dipped to 0.947 because crops with few chunks (wheat 10, horsegram 7) filled the top 5 with other crops' passages. Cause: the crop filter only moved the named crop to the front. Fix (measured, no change in hit rates): when the question names a covered crop and at least two of that crop's passages are found, other crops' passages are no longer passed to the model.

## Proposal: other vegetables (NOT ingested; waits for your approval)
Same source: TNAU Horticulture Crop Production Guide 2020, `d829671c_HORTICULTURE.pdf`, already in the repository. Chunks below were measured by running the real chunker without writing anything. All pages are present in the extraction file.

| Crop | PDF pages | Chunks | With a dose | Notes |
|---|---|---|---|---|
| Brinjal | 77-82 | 11 | 9 | |
| Okra (bhendi) | 83-86 | 6 | 6 | |
| Cucurbits (pumpkin, gourds, cucumber, melons) | 96-120 | 36 | 32 | one group: 12 crops share the section |
| Cabbage | 133-137 | 7 | 7 | |
| Cauliflower | 138-141 | 7 | 7 | |
| Carrot, radish, beetroot | 142-147 | 6 | 6 | |
| Potato | 148-151 | 5 | 5 | |
| Onion | 165-169 | 9 | 8 | |
Total 87 chunks. Suggested stages: (1) brinjal + okra, (2) onion + potato, (3) cabbage + cauliflower + root vegetables, (4) cucurbits. Each stage measured against the evaluation set before the next. The router's list of plants outside the knowledge base would lose these crops at each stage.
Risks: nearly every chunk carries a dose; these are Tamil Nadu recommendations printed in a 2020 guide and some products named may since have been restricted (the pesticide guard and the expert-review queue cover this).

## Permissions
Draft requests to ICAR-IIMR and PAU are in `PERMISSION_REQUEST_DRAFTS.md`. Nothing has been sent. Neither source is in the knowledge base.

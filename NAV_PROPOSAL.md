# Navigation proposal for Cropsy

Status: proposal only. `IconRail.tsx` and `home.tsx` belong to the session finishing the dashboard, which will apply it.

## What is wrong today
The left rail has **eight unlabelled icons**. A first-time user (or a judge) has to hover each one to learn what it does, and the topics overlap:

| Today's icon | Overlaps with |
|---|---|
| Map & Solar Advisory (chat + sun map) | the only place to ask a question |
| Evidence Sources | How Cropsy Thinks (both are "why this answer") |
| How Cropsy Thinks | Evidence Sources |
| Land & Crop Advisory | Field Report (both are "what should I do on this parcel") |
| Field Report & Alerts | Land & Crop Advisory |
| Satellite Layers & Index Results | (distinct) |
| Field History 2021-2025 | Field Report (past seasons of the same parcel) |
| Bell | Field Report alerts |

The parcel the user is looking at is chosen in different places on different pages, and the "dummy vs real" labelling is repeated inconsistently.

## Proposal: four sections, one persistent top bar

```
┌ top bar ─────────────────────────────────────────────────────────────────────────────────────┐
│ Cropsy · Then Malai   [ Parcel ▾ TM-09 · Rice · Panicle Initiation ]   Sample data badge   🖨  │
├ rail (labels shown, collapsible) ─┬ content ────────────────────────────────────────────────────┤
│ ASK        Chat & map             │                                                             │
│ MY FIELD   Field report  (default)│   tabs inside the page:  Today | Water | Soil | Pests | History
│ SATELLITE  Layers & indices       │                                                             │
│ TRUST      Evidence & trace       │                                                             │
└───────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

| Section | Contains | Replaces |
|---|---|---|
| **Ask** | chat + solar map (as now) | Map & Solar Advisory |
| **My field** | the dashboard: village headline, "what to do now", health, irrigation, soil, growth and yield, pests, fertiliser. Tabs for **History** (past seasons) and **Advisory** (latest chat answer for this parcel) | Field Report, Land & Crop Advisory, Field History |
| **Satellite** | layer picker ("What do you want to know?"), map controls, coordinate lookup, bulk export, index results with the two-season chart and pass calendar | Satellite Layers & Index Results |
| **Trust** | tabs **Sources** and **Route trace** for the last answer, plus the verification checks | Evidence Sources, How Cropsy Thinks |

The bell opens **My field** scrolled to alerts (village alerts list), with the unread dot driven by the count of high-severity alerts.

## Rules that make it feel organised
1. **One parcel selector**, in the top bar, drives every page. Selecting on the map, in alerts or by typing a parcel in chat all update it. (Chat keeps the "general question" mode switch already built.)
2. **One vocabulary for data honesty**, always the same chip colours: green = real data, amber = dummy or modelled, blue = our own definition. A single "Sample data" chip lives in the top bar; pages stop repeating long disclaimers and keep only the specific limit next to the number it affects.
3. **Every page opens with the answer, then the evidence**: headline instruction first, details below.
4. **Labels on the rail**, collapsible to icons on small screens; on phones the rail becomes a bottom tab bar with the four sections.
5. **Print report** button in the top bar (opens `PrintReport`), available wherever a parcel is selected.
6. **Deep links**: `/#/field/TM-09/water`, `/#/satellite/ndvi/2026-09` so a judge can be sent straight to a view.

## Order of work (small, safe steps)
1. Add the top bar with the parcel selector and the "Sample data" chip; wire it to the existing `selectedParcelId`.
2. Rename and group the rail items (labels only, no routing change).
3. Merge pages: fold Land & Crop Advisory and History into My field as tabs; fold Evidence and Route trace into Trust as tabs.
4. Add the bottom tab bar for narrow screens.
5. Add deep links last, once the routes are stable.

## Risks
- Merging pages touches `home.tsx` routing: do it after the dashboard is finished and tested, keeping the old tab ids working until then.
- The solar map's panels are dense on narrow screens; leave that page as it is and only wrap it in the new top bar.

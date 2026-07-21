# Campaign Tracking — User Story (Phase 1: Athena)

**Product:** New campaign tracking app (Python API + React UI)  
**Phase 1:** Athena campaign tracking only (one user story)  
**Later:** Hermes → Phoenix → full DBM tab / Media Matching / List Key migration  

**Companions:** [`CAMPAIGN_TRACKING_LLD.md`](./CAMPAIGN_TRACKING_LLD.md) · [`ATHENA_CAMPAIGN_FLOW_COMPLETE.md`](./ATHENA_CAMPAIGN_FLOW_COMPLETE.md)

**Alignment note:** This story must match the layman Athena flow — especially **Forecasting = early (before modeling)** vs **Allocate / Maintain Backend = after LOL**. See flow §§8b–10.

---

## What this user story covers (short)

Phase 1 is **one** user story: *senior management and ops can track every Athena campaign/event end-to-end on one board.*

| # | Covered | In one line |
|---|---------|-------------|
| 1 | **Campaign → Event hierarchy** | See campaigns, how many events under each, product, status, DBM job when present |
| 2 | **Spoken keys** | Which packages sit on each Event Id |
| 3 | **Forecasting by state (early)** | Budgeted / net / actual qty, PPPM, total premium, response rates, DTW, mail month, status — per spoken key × state; **before modeling** |
| 4 | **Segment / state (Athena)** | Forecast `STATE_CODE` on `FRCSTDT`; SES segment when present |
| 5 | **Draft vs active counts** | Using Athena’s real codes (not invented “mature”) |
| 6 | **Lifecycle dates** | Entered / schedule / drop / forecast mail & start / backend mail·lettershop·ship dates |
| 7 | **Stage timeline** | Athena gates: setup → forecast → media → match → spoken → list keys registered → allocated → backend |
| 8 | **Media Matching** | Linked vs pending Media ID |
| 9 | **Match %** | Basic / supp %, match sent / approved |
| 10 | **List Key register + Allocate (after LOL)** | Boxes from modeling registered; qty planned to spoken keys; banner: plan ≠ person stamp |
| 11 | **Maintain Backend / Approve** | Backend job `IP` / `BR` / `BE`; Excel ticket for Dan — not ship |
| 12 | **Executive dashboard + search** | KPIs (incl. forecast / allocate gaps) + “where is Event Id X?” |
| 13 | **Placeholders** | Modeling in-flight · Control cards / fulfillment · Hermes · Phoenix · Mature — *not tracked yet* |
| 14 | **Glossary + timing education** | Forecast ≠ Allocate; list key ≠ list code; Allocate ≠ stamp; BR ≠ mailed |
| 15 | **Filters / export / deep-link** | Find, export, open Athena (Forecasting, Media, Events, List Key, Maintain Backend) |

**Out of this story:** Hermes creative status, Phoenix enrollment, Athena **writes**, person-level PII, modeling KEEP/SO rows, control-card execution, Julie verbals content (except noting they are outside Athena).

**Roles:** Senior management · DBM ops · CMS (media link) · Client Services · Creatives/list-key operators (read-only in this app).

**Priority:** Must  
**Stack (future):** Python (FastAPI) + React (Vite/TypeScript)

---

# US-ATHENA-01 — Athena campaign tracking board

### Title
Track all Athena campaigns and events on one management board

### As a / I want / So that

**As a** senior manager, DBM operator, or CMS/creatives operator  
**I want** one place that shows where every Athena Campaign and Event stands — hierarchy, spoken keys, **early forecast by state**, media, match %, **list-key register/allocate (after modeling)**, backend Approve, and stage  
**So that** I can answer “where is this campaign?”, “what did we forecast for CO vs TX?”, and “have we allocated / approved backend yet?” without bouncing across Athena screens — and without guessing Hermes / Phoenix / control-card status

### Description (business context)

Today Athena is FMG’s **order board**:

1. **Early:** Campaigns / Events / SES / spoken keys; **Forecasting** stores budget by spoken key × **state** (qty, PPPM, premium, status) — typically **before** modeling.  
2. **Mid:** CMS links Media IDs; match % shows on the Event.  
3. **After modeling:** LOL creates **list keys**; Athena **registers** those boxes, **Allocates** qty to spoken keys (plan only), then **Maintain Backend → Approve** emails `BackendInstructions_*.xlsx` to Dan.  
4. **Outside Athena:** Julie verbals → Dan control cards stamp people → ship; Hermes creatives; Phoenix enroll; modeling mature ~90d.

This story builds a **read-only** board that pulls Athena signals only. Non-Athena lanes appear as grey placeholders.

Evidence: Athena CODE (`B:\Athena`), Julie FAQ (media before match), Kickoff (Allocate ≠ person stamp; Athena spits backend instructions), Solutioning Jul-13 (Athena → Hermes → Phoenix later). Flow detail: [`ATHENA_CAMPAIGN_FLOW_COMPLETE.md`](./ATHENA_CAMPAIGN_FLOW_COMPLETE.md) §§8b–10.

### Scope in

- Campaign / Event hierarchy, product, DBM job # when Athena has it (`CMUNFLEX` / backend header)  
- Spoken-key inventory and SES segment when present  
- **Forecasting read panel** (View Forecast Handler grain) — early budget by state  
- List-key **registered** vs **allocated** distinction  
- Maintain Backend jobs: status, dates, assigned spoken keys, meaning of Approve Excel  
- Draft-like vs production-like counts + glossary (incl. timing: forecast early / allocate after LOL)  
- Derived Athena stage chip + timeline (incl. forecast + list-key-registered gates)  
- Media link + match % panels  
- Executive KPIs (incl. “has forecast / missing allocate / backend BE”)  
- Search by Event / spoken key / Media ID / DBM job when supported  
- Filters, CSV export, “Open in Athena” deep-links (Forecasting, Media Matching, Events, List Key, Maintain Backend)  
- Placeholders: modeling in-flight, control cards/fulfillment, Hermes, Phoenix, Mature  

### Scope out

- Hermes / Phoenix product status (Phase 2/3)  
- Migrating DBM / Media Matching / List Key **write** UX (Phase 4)  
- Approve / Allocate / Link Media / Forecast **save** writes  
- KEEP/SO person rows, control cards, verbals Excel as data source  
- Account #, SSN, person names/addresses  

---

## Detail — acceptance criteria by area

### A. Cover page / executive dashboard

- **Given** I have `TRACKING_VIEW`  
  **When** I open the app home  
  **Then** I see KPI tiles at least:  
  - campaigns by commun status  
  - events by Athena stage  
  - missing media link  
  - match not approved  
  - **events with forecast data** vs **events with no forecast**  
  - **list keys registered but not allocated**  
  - backend `IP` / `BR` / `BE`  
  - draft-like vs production-like spoken counts  
  - refresh time  
- **Given** I click a KPI  
  **Then** the Event list is filtered to that KPI.  
- **Negative:** No token → 401; wrong role → 403; no PII in KPI payloads.

### B. Campaign → Event hierarchy

- **Given** Athena has Campaigns with Events under them  
  **When** I open the Campaign board  
  **Then** each Campaign shows ID, name, client, commun status (`A` Active / `H` On Hold / `X` Inactive / `N` Entered), and Event count.  
- **Given** I expand a Campaign  
  **When** Events load  
  **Then** each Event shows: Event Id, product, commun status, schedule/drop date if present, **DBM job # if present**, derived stage chip, spoken-key count, **forecast Y/N** (or count of state rows), media linked Y/N, **list-key registered / allocated** indicators, backend status.  
- **Given** product or DBM job is missing  
  **Then** show “—” — do not invent.  
- **Negative:** Empty filter → empty state + clear filters CTA (not an error page).

### C. Event detail (single place for all Athena panels)

- **Given** a valid Event Id  
  **When** I open Event detail  
  **Then** header shows Event Id, client, product, parent Campaign, commun status, **DBM job if present**, and a stage timeline.  
- **Given** Event Id unknown  
  **Then** 404 + “Event not found”.  
- **Given** some panels have no data  
  **Then** those panels show empty/not-started; the page still loads.  
- Panel order (recommended): Timeline → Media → Match % → Spoken keys → **Forecasting** → List keys/Allocate → Backend → Placeholders.

### D. Spoken keys

- **Given** SES / forecast / list-key search return spoken keys for an Event  
  **When** Spoken Keys panel loads  
  **Then** I see each spoken key, source tag, forecast status (`F`/`O`/`E`/`C`) and/or Creatives draft label when available.  
- **Given** zero spoken keys  
  **Then** empty state: “No spoken keys on this Event yet”.  
- **Given** SES has `SOLIC_SEGMENT_ID`  
  **Then** show segment on expand.  
- **Given** forecast has `STATE_CODE` rows  
  **Then** spoken key expands to show states (detail in **D2**).  
- **Negative:** No account # / SSN / person rows in this panel.

### D2. Forecasting by state (View Forecast Handler grain) — **early, before modeling**

Athena Forecasting UI tree: **Event Id → Creative Version → Spoken Key → State**. Tracking app **reads** the same fields (no edit).

- **Given** the Forecasting panel  
  **Then** a short note is visible: “Forecasting is the early state budget (qty / PPPM / premium). It is **not** list-key Allocate. Allocate happens **after** modeling LOL.”  
- **Given** Event has forecast data (`POST .../forcast/search`)  
  **When** Forecasting panel loads  
  **Then** for each spoken key × state I see at least:  
  - State (e.g. `CO - COLORADO`)  
  - Budgeted Quantity, Net Quantity, Actual Quantity  
  - PPPM, Total Premium, Average Buy Amount  
  - DTW (Y/N), DTW Percent  
  - Basic Response Rate, Basic Members, Supp Resp Rate, Supp Members  
  - Mail Month, Start Date, Status (`F`/`O`/`E`/`C` with label e.g. `O - Production`)  
  - Channel, Portfolio, Group, Strategy, Creative Version, Version Type, Carrier  
  - Client Vanity URL when present (`GPEVNTSG`) — “Claim” Vanity URL label is `OPEN` in CODE  
- **Given** Event-level Marketing Quantity  
  **Then** show as sum of budgeted qty under the event (derived — not a separate DB column).  
- **Given** Total Premium  
  **Then** display stored `TC_PREMIUM` and/or qty×PPPM; document source when they differ.  
- **Given** no forecast rows  
  **Then** empty state: “No forecast handler data for this Event” (Event may still be valid — forecast is early planning).  
- **Negative:** Forecast panel is read-only; Save Forecast out of scope (deep-link).  
- **Negative:** Do not invent states not returned by Athena.

### E. Draft vs active / lifecycle (Athena-native) + glossary

- **Given** the glossary is visible (dashboard link + Event help)  
  **When** I view draft/active counts or stage chips  
  **Then** metrics cite real code sets: Campaign/Event commun status, spoken `SPKYSTS` (`F`/`O`/`E`/`C`), Creatives **D–DRAFT** where shown, backend `BKNDSTS`.  
- **Given** glossary content  
  **Then** it explicitly states:  
  - Forecasting ≠ Allocate  
  - Forecasting timing ≈ **before** modeling; Allocate ≈ **after** LOL  
  - List key (100–999) ≠ ops LIST CODE (e.g. 10100)  
  - Allocate ≠ person spoken stamp (control cards)  
  - Backend `BR` = Excel approved/emailed ≠ mail shipped  
  - Mature ≠ Athena Active  
- **Given** a “draft-like” metric is shown  
  **Then** tooltip says it is **derived** (e.g. `F` and/or D–DRAFT).  
- **Negative:** Do **not** label an Event “Mature” from Athena alone.  
- Lifecycle dates: show only dates Athena returns (commun/schedule/forecast mail·start/backend mail·lettershop·ship); omit missing ones.

### F. Stage timeline (Athena-provable only)

Primary stage = furthest completed Athena gate:

| Stage | Meaning |
|-------|---------|
| `SETUP` | Event exists |
| `FORECAST_PRESENT` | ≥1 forecast state row (`FRCSTDT`) — early budget exists |
| `MEDIA_PENDING` / `MEDIA_LINKED` | Media unmatched vs linked |
| `MATCH_RECEIVED` / `MATCH_APPROVED` | Match % / approved date |
| `SPOKEN_READY` | ≥1 spoken key |
| `LISTKEY_REGISTERED` | ≥1 row in `LISTKEY` on Event (boxes registered; may not be allocated yet) |
| `LISTKEY_ALLOCATED` | ≥1 allocate row (`LSTKSPKREL`) |
| `BACKEND_IP` / `BACKEND_BR` | Backend in progress / approved |
| `BACKEND_BE` | Error badge (can sit on top of other stages) |

- **Given** forecast exists but media not linked  
  **Then** stage can still show forecast progress; media warning remains visible.  
- **Given** list keys registered but zero allocate rows  
  **Then** stage is `LISTKEY_REGISTERED` (not `LISTKEY_ALLOCATED`).  
- **Given** media + match done but no backend  
  **Then** stage is match/spoken/list-key — **never** Hermes green.  
- **Given** backend `BE`  
  **Then** error badge is visible.  
- **Given** Modeling in-flight / Control cards / Hermes / Print / Phoenix / Mature  
  **Then** Phase 1 shows grey “Not tracked yet” only.  
- Timeline strip: Setup → Forecast → Media → Match → Spoken → List keys registered → Allocated → Backend IP → Backend BR.

### G. Media Matching + match %

- **Given** media linked to Event  
  **Then** show Media ID(s), status codes, est. records / vendor when available.  
- **Given** no media linked  
  **Then** amber/red: “Media not linked — member match cannot start” (ops rule).  
- **Given** `MAILSTAT` / mailing status API has data  
  **Then** show basic %, supp %, match sent, match approved.  
- Do not claim Athena creates Media IDs (Acxiom does). Auto-approve of match date is `OPEN` — display field only.

### H. List Key + Allocate + Maintain Backend

Must reflect flow §§9–10.

**List keys / Allocate**

- **Given** list keys registered on Event  
  **Then** show list key, description, total/available qty, allocated qty sum, allocations to spoken keys.  
- **Given** list keys exist but no `LSTKSPKREL` rows  
  **Then** show “Registered — not allocated yet.”  
- Banner (always on this panel): “List keys are born in modeling LOL. Athena registers them and **Allocate** is a quantity plan only — it does **not** stamp spoken key on each person (that is control cards later).”  
- Never treat BackendInstructions **LIST CODE** (e.g. 10100) as modeling **LIST_KEY** (100–999).  
- Empty: “No list keys registered on this Event yet (usually after LOL).”

**Maintain Backend / Approve**

- **Given** backend jobs  
  **Then** list: backend id, status `IP`/`BR`/`BE`/`I`, mail / publication / lettershop / due-to-ship dates when present, file description, net qty, seed if returned, **assigned spoken keys**, DBM/CRM job.  
- Panel note: “Maintain Backend builds the instruction job for Dan/ops. **Approve** emails `BackendInstructions_{dbmJob}_{eventId}.xlsx` — it does not mail members or run control cards.”  
- `BR` = “Excel approved/emailed” — not “shipped to members”.  
- `BE` highlighted as blocker (with comment if available).  
- Drill: spoken key → list keys under that spoken key when API returns them.

### I. Search, filters, export, deep-link

- Search by Event Id, spoken key, Media ID, and **DBM job # when indexed** → land on stage/detail. Unknown → empty result, not 500.  
- Filters: client, product, campaign/event status, derived stage, backend status, media linked Y/N, **forecast present Y/N**, **allocated Y/N**, date range; shareable URL query.  
- Export filtered Event board to CSV (`Should`).  
- “Open in Athena” deep-links (`Could`/`Should`): **Forecasting (View Forecast Handler)**, Media Matching, Events / Mailing Status, Spoken Key List Key Relationship, Maintain Backend. If SSO deep-link is `OPEN`, show copyable Event Id.

### J. Placeholders (later / outside Athena)

- Event detail shows grey panels:  
  - **Modeling in-flight** (score/LOL/KEEP) — not Athena  
  - **Fulfillment / control cards** (person spoken stamp) — not Athena  
  - **Hermes** creatives — Phase 2  
  - **Phoenix** enroll — Phase 3  
  - **Mature** (~90d responders) — modeling/Data Hub  
- No fake timestamps.  
- Do not imply Backend `BR` means control cards are done.

---

## Definition of done (this one story)

- [ ] Exec can answer: campaign status, event count, product, DBM job (if any), spoken keys, **forecast qty/PPPM/premium by state**, draft-like vs production-like counts, Athena stage (incl. forecast + registered vs allocated), media, match %, list-key register/allocate, backend `IP`/`BR`/`BE`  
- [ ] Exec understands from UI/glossary: forecast is early; allocate is after LOL; BR ≠ shipped; allocate ≠ person stamp  
- [ ] Exec cannot be misled that Athena knows Hermes / Phoenix / print / mature / control cards  
- [ ] Metrics tagged with source (Athena code vs derived vs open)  
- [ ] No account # / SSN / person PII on open UI  
- [ ] Wireframes in LLD match these panels (incl. forecast timing note + list-key registered vs allocated)

---

## Alignment checklist (vs `ATHENA_CAMPAIGN_FLOW_COMPLETE.md`)

| Flow topic | In user story? |
|------------|----------------|
| Campaign / Event / product | Yes — B, C |
| Spoken keys / SES | Yes — D |
| Forecasting by state + fields | Yes — D2 |
| Forecasting **before** modeling | Yes — D2 note, glossary E, cover #3 |
| Media link before match | Yes — G |
| Match % | Yes — G |
| List keys born in LOL (Athena does not invent) | Yes — H banner |
| Add/register list keys vs Allocate | Yes — H + stage `LISTKEY_REGISTERED` / `LISTKEY_ALLOCATED` |
| Allocate ≠ person stamp | Yes — H, E glossary, J |
| Maintain Backend why/how + Approve Excel | Yes — H |
| `IP`/`BR`/`BE` meanings | Yes — H, E |
| LIST CODE ≠ LIST_KEY | Yes — H, E |
| DBM job on Event/backend | Yes — B, C, H, search I |
| Control cards / verbals outside Athena | Yes — J placeholder + scope out |
| Hermes / Phoenix / Mature placeholders | Yes — J |
| KEEP/SO person data out of Phase 1 UI | Yes — scope out |

---

## Roadmap (not this story)

| Phase | Scope |
|-------|--------|
| **1** | This user story — Athena board |
| **2** | Hermes stage visibility |
| **3** | Phoenix enroll visibility |
| **4** | Migrate full DBM tab + Media Matching + List Key into the new app |

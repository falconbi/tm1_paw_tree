# TM1 Governance Suite — Claude Code Project Brief

**Last updated:** April 2026
**Status:** CubeMap ✅ | PAW Tree ✅ | Model Builder GBL ✅ | CST WIP | Health Monitor stub only
**Note:** Report Builder is a separate app (`tm1_report_writer`) — all `/api/reports/*` routes removed from this codebase.
**Environment:** Ubuntu 24.04 · TM1 V12 on-prem · PAW via Authentik OAuth2 PKCE

---

## Commands

```bash
# Daily startup
cd ~/apps/tm1_governance && source venv/bin/activate && python3 app.py

# Production (Gunicorn)
gunicorn -w 4 -b 0.0.0.0:8080 app:app

# TI linting
python3 ti_lint.py <path/to/process.ti>
```

---

## Architecture

```text
Browser (http://localhost:8080)
    └── Flask app.py
            ├── core/tm1_connect.py       → raw requests.Session (TM1 V12 cookie auth)
            ├── core/tm1py_connect.py     → TM1Service (monkey-patched for V12 on-prem)
            ├── core/paw_connect.py       → PAW Content Services (Authentik PKCE, 6-step)
            ├── extract_tm1_model.py      → writes cube_map/tm1_model.json (cache)
            └── static HTML tools         → CubeMap, PAW Tree, Health Monitor
```

**Two connection methods — this is intentional:**

- `tm1_connect` (raw requests) → lightweight Flask endpoints, fast, minimal deps
- `tm1py_connect` (TM1Service) → heavy extraction only (rules, attributes, DB() scanning)

---

## Project Structure

```text
~/apps/tm1_governance/
├── app.py                        # Flask server — mounts all tools
├── core/
│   ├── tm1_connect.py            # Raw TM1 session
│   ├── tm1py_connect.py          # TM1py + V12 monkey-patches
│   └── paw_connect.py            # PAW Authentik PKCE auth
├── cube_map/
│   ├── extract_tm1_model.py      # Full model extraction → JSON
│   ├── tm1_model.json            # Generated cache (do not hand-edit)
│   └── static/                   # CubeMap HTML/JS/CSS
├── paw_tree/
│   └── static/                   # PAW Tree HTML
├── health_monitor/
│   └── static/                   # Health Monitor HTML (stub)
├── model_builder/
│   ├── build_gbl_model.py        # Orchestrator — GBL dims
│   ├── build_cst_model.py        # Orchestrator — CST cubes
│   ├── create_gbl_*.py           # Individual GBL dimension scripts
│   └── create_cst_*.py           # Individual CST cube/dim scripts
├── groups.json                   # Role definitions (annotations only — not live IDP)
├── .env                          # Credentials — never commit
└── requirements.txt
```

---

## Flask Routes

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET | `/` | CubeMap HTML |
| GET | `/workbook-tree` | PAW Tree HTML |
| GET | `/health-monitor` | Health Monitor HTML |
| POST | `/api/refresh` | Triggers background TM1 extraction |
| GET | `/api/status` | Last run / error / cube count |
| GET | `/api/model` | Cached model JSON |
| GET | `/api/tm1/*` | Live TM1 metadata (cubes, dims, views) |
| GET | `/api/paw/tree` | PAW content tree |
| GET | `/api/config` | Client-safe config values only |

---

## Key Conventions

**TM1 objects:** Ignore anything starting with `}` — these are system objects.
**PAW paths:** Double URL-encode all paths (`/shared` → `%252fshared`).
**Credentials:** All in `.env` — never hardcode, never log.
**Non-system filter:** `not name.startswith('}')` — applied everywhere.
**Architecture Score:** Removed from UI — scoring logic kept in extractor for future use.

---

## Critical Gotchas

- **TM1py V12 patches** — `tm1py_connect.py` monkey-patches `_set_version` and `_construct_root` before every connection. Without these, TM1py fails on V12 on-prem. Do not remove.
- **PAW double-encoding** — PAW Content Services requires paths double-encoded. `encode_path()` does `quote(quote(...))` deliberately — this is correct, not a bug.
- **Session auth** — TM1 uses `TM1SessionId` cookie (not Bearer token). PAW uses `paSession` cookie + `ba-sso-authenticity` header.
- **Background refresh thread** — uses a lock + `already_running` 409 guard. Do not make the refresh endpoint synchronous.
- **groups.json** — role definitions for governance UI only. Never query the identity provider (Authentik) for governance data — it changes too often and is not the source of truth.
- **Private views API** — `GET /Cubes('{cube}')/PrivateViews` is hard-scoped to the authenticated user. `TM1-Impersonate` header exists (TM1 11.1.0+) but only works with CAM/LDAP auth — silently ignored on V12 OAuth (client_id/client_secret) auth. On V11 with traditional auth, impersonation should work: pass `TM1-Impersonate: <username>` on the `/auth/v1/session` POST, then query PrivateViews with the returned session. Confirmed non-working on V12 via `ActiveUser` — always returns admin regardless of header. Test on V11 when available.
- **Private subsets API** — same hard-scoping and same impersonation limitation as private views.
- **PAW private books** — fully visible to admin. Walk `/users/{uuid}/` to enumerate all users' private books. Owner resolved via `system_properties.created_user_pretty_name`. Confirmed working with test user (testpaw / "test tester"). This IS in scope for governance tooling.
- **Python ETL nodes on CubeMap** — `cube_map/python_sources.json` is a manually maintained registry. Refresh re-scans whatever is listed there — it does NOT auto-detect retired scripts. When you stop using a Python ETL script, remove it from `python_sources.json` or it will keep appearing on the map. TI processes and rules disappear automatically on refresh; Python scripts do not.

---

## TODO

### High Priority

- [ ] Cache TM1 sessions (5–10 min TTL) — biggest performance win
- [ ] Add `flask-compress` + static cache headers
- [ ] Add `/api/paw/users` endpoint — fixes orphaned book detection
- [ ] Complete CST Model Builder scripts

### Medium Priority

- [ ] Add `.claude/settings.json` with deny rules for `.env`
- [ ] Health Monitor backend (DuckDB + APScheduler)
- [ ] Move `.env` loading to app startup, inject into `app.config`
- [ ] Add rate-limiting on `/api/refresh`

### Nice to Have

- [ ] Move `groups.json` to annotations-only; build `core/groups.py` live resolver
- [ ] Gunicorn + nginx for shared deployments
- [ ] Prometheus `/metrics` endpoint
- [ ] Structured JSON logging option

---

## Roadmap — Governance Platform

### CubeMap — Edge Classification

- [ ] Split rules text at FEEDERS; keyword — only scan calc section for DB() edges; feeder section DB() = performance hints not data flow
- [ ] Classify edges: `rule_calc` (before FEEDERS;) vs `rule_feeder` (after FEEDERS;)
- [ ] Classify edges by measure type: value measures (Amount/Apportioned Amount/Settled Amount) = flow, rate/driver measures (Driver Percentage Share/Apportionment Rate) = lookup
- [ ] Add edge type field to tm1_model.json: rule_flow, rule_lookup, rule_feeder, python, ti
- [ ] UI toggle checkbox: show/hide feeder edges independently from calc edges
- [ ] Hybrid extractor: live TM1 scan for metadata + local YAML/Python scan for Python ETL edges
- [ ] Save/load named diagram layouts (Cytoscape cy.json() → Flask → layouts/{name}.json)

### CubeMap — Enriched Extraction

- [ ] Extract measure dimension elements (actual measure names) → surface in node detail panel
- [ ] Extract public views per cube (names + count) → show in node drawer
- [ ] TI process edges: which TI processes write to each cube → complete data lineage picture
- [ ] Chore connections: which chores schedule TI processes that touch each cube

### CubeMap — Calculation Trace (next priority)

User picks a cube + measure name → system traces back through rule formulas recursively until it hits root cubes (no rule = TI/Python loaded). Displayed as an expandable formula tree. Two phases:

- [ ] **Phase 1 — Static trace**: Parse rules text already in model JSON. Extract `['Measure'] = DB('SourceCube', ..., 'SourceMeasure')` chains. Walk back recursively, max 4–5 levels. Render as collapsible tree in a side panel. No TM1 re-extraction needed — rules text already in model.
- [ ] **Phase 2 — AI explanation**: Pass the formula tree to Claude API → plain English description of the full calculation logic. Useful for onboarding finance staff and auditors who can't read TM1 rules. Cache explanation in `rules_analysis/` so it's not re-generated every time.

### CubeMap — Inherited Model Support

- [ ] Reverse engineer extractor: pull cubes, rules, TI, dimensions, views, subsets from live server → YAML
- [ ] Git baseline on day one for inherited servers with no source control
- [ ] AI-assisted analysis: explain rules, find missing feeders, identify circular references

### PAW Tree — Extended Consumer View

- [ ] Action buttons: extract from workbook JSON → show TI process called + parameters
- [ ] Websheet scanning: download .xlsx from TM1 Web filesystem, parse PAX formulas with openpyxl — Extract PAX.VIEW, PAX.ELEMENT, PAX.SUBNM references → cube/view/dimension/subset links
- [ ] Full tree: Folder → Workbook → Views + Action Buttons + Websheets
- [ ] Cross-tool link: click cube/view reference in PAW Tree → highlight in CubeMap


### Health Monitor

- [ ] Orphaned cubes: exist in TM1 but no PAW workbook, websheet or TI references them
- [ ] Broken consumers: workbook/websheet references deleted cube, view or dimension
- [ ] Orphaned TI processes: no chore, no PAW action button calling them
- [ ] Stale chores: scheduled TI processes not run recently or failing
- [ ] Security gaps: cubes with no group access defined

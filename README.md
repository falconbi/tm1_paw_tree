# TM1 CubeMap

Interactive data lineage diagram for IBM TM1 / Planning Analytics (V12).

Visualises cubes, rules, TI processes, and Python ETL scripts as a navigable graph. Click any node to inspect rules, script code, dimensions, and data flow.

> **PAW Tree** (workbook governance) is a separate tool in this repo — not covered here.

---

## Quick Start (Docker)

**Prerequisites:** Docker and a TM1 V12 server (on-prem).

### 1. Clone

```bash
git clone https://github.com/your-org/tm1-governance.git
cd tm1-governance
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` — only the TM1 block is needed for CubeMap:

```env
TM1_ADDRESS=192.168.x.x
TM1_PORT=4444
TM1_DATABASE=YourDatabaseName
TM1_CLIENT_ID=your_client_id
TM1_CLIENT_SECRET=your_client_secret
TM1_USER=admin
```

### 3. Run

```bash
docker compose up --build
```

Open **[http://localhost:8082](http://localhost:8082)** and click **Refresh** to extract your model.

---

## Manual Install (Python)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in TM1 block
python3 app.py
```

---

## Requirements

- TM1 / Planning Analytics V12 **on-prem**
- OAuth2 client credentials enabled (`client_id` / `client_secret`)

That's it. CubeMap connects directly to the TM1 REST API — no SSO, no PAW, no Authentik. If your TM1 server has an OAuth2 service client set up, you can run it.

### Compatibility

| Environment | Status | Notes |
| --- | --- | --- |
| On-prem V12 + OAuth2 | ✅ Supported | Fill in `.env` and run |
| Cloud PA V12 (SaaS) | ⚠️ Auth change needed | Same REST API, different auth flow — configure your `.env` connection details accordingly |
| On-prem V11 | ❌ Not supported | V11 uses basic auth; TM1py connection is patched for V12 only |

---

## What it shows

- **Cubes** — all non-system cubes with dimension lists and RAM usage
- **Rules** — DB() references extracted as directed edges between cubes
- **TI Processes** — cube read/write edges, click to view script
- **Python ETL** — registered scripts scanned for cube reads/writes (see `cube_map/python_sources.json`)
- **Tags** — tag any object, generate AI module docs from tagged sets

---

## Architecture

```
Browser → Flask (app.py)
            ├── core/tm1_connect.py    → TM1 REST API (fast, raw requests)
            ├── core/tm1py_connect.py  → TM1py (deep extraction — rules, attributes)
            └── cube_map/extract_tm1_model.py → writes cube_map/tm1_model.json
```

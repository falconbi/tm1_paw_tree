# TM1 PAW Tree

Governance and visibility tool for IBM Planning Analytics Workspace (PAW) V11.

Gives administrators a single view of all PAW books — who created them, when they were last opened, what TM1 views they reference, and which ones haven't been touched in months.

---

## Features

| Feature | Description |
|---------|-------------|
| **Book Tree** | Full folder hierarchy — shared and private books in one view |
| **Book Drawer** | Metadata, pages, TM1 cube/view references per tab |
| **Search** | Filter by book name, folder, or cube name |
| **Group Filter** | Overlay folder permissions for any access group |
| **Dashboard** | Stats overview — orphaned books (90+ days inactive), private book inventory |
| **Activity Tracking** | Background polling detects real book opens; session-deduplication groups activity into user sessions |
| **Impact Panel** | Select a TM1 server, cube, or view to see which PAW books would be affected by a change — results highlight directly in the tree |
| **Workbench vs Dashboard** | Distinct icons for new PAW Workbench and classic Dashboard book types |

---

## Requirements

- Python 3.10+
- IBM Planning Analytics Workspace (PAW) V11 on-prem
- IBM TM1 V11 on-prem (one or more servers)

---

## Quick Start

### 1. Clone

```bash
git clone git@github.com:falconbi/tm1_paw_tree.git
cd tm1_paw_tree
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
PAW_HOST=http://192.168.x.x
PAW_USERNAME=admin
PAW_PASSWORD=your_tm1_password

# Optional — log-based activity tracking (poll mode used if left blank)
# PAW_LOG_PATH=/path/to/WAProxy.log
```

`PAW_ACCOUNT_ID` and `PAW_TENANT_ID` are used to build deep-links back into PAW. Find them in the PAW URL when logged in: `/?accountId=...&tenantId=...`

Edit `config/servers.json` to list your TM1 databases:

```json
[
  {
    "name": "MyServer",
    "address": "192.168.x.x",
    "auth": "v11",
    "user": "admin",
    "password": "apple",
    "databases": [
      {"name": "MyDatabase", "port": 12345, "ssl": false}
    ]
  }
]
```

Set `"ssl": true` for databases that use HTTPS (self-signed certs are accepted automatically).

### 3. Run

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open **http://localhost:8082**

---

## Configuration Reference

### .env

| Variable | Required | Description |
|----------|----------|-------------|
| `PAW_HOST` | Yes | PAW server URL e.g. `http://192.168.1.37` |
| `PAW_USERNAME` | Yes | TM1 admin username |
| `PAW_PASSWORD` | Yes | TM1 admin password |
| `PAW_ACCOUNT_ID` | No | PAW account ID (from browser URL) — enables deep-links |
| `PAW_TENANT_ID` | No | PAW tenant ID (from browser URL) — enables deep-links |
| `PAW_LOG_PATH` | No | Path to `WAProxy.log` for log-based activity tracking |

### config/servers.json

Lists all TM1 databases available to the Impact panel. Each server entry can have multiple databases, each with its own port. Set `"ssl": true` for HTTPS databases (self-signed certs are trusted).

This file is not committed to git — deploy it separately to each environment.

---

## Architecture

```
Browser (http://localhost:8082)
    └── Flask app.py
            ├── core/paw_connect.py      → PAW V11 session auth (username/password cookie)
            ├── core/tm1_connect.py      → Multi-server TM1 session manager (HTTP basic auth)
            └── paw_tree/static/         → Single-page HTML frontend
```

**PAW auth** — simple username/password POST to `/login/form/` sets a session cookie. No OAuth, no PKCE.

**TM1 auth** — HTTP basic auth at `http(s)://address:port/api/v1`. Sessions are cached per database for 10 minutes.

**Activity tracking** — polls PAW asset metadata every N minutes and diffs `used_date` to detect real book opens. If `PAW_LOG_PATH` is set and readable, switches to log-based mode for per-user attribution.

**Impact index** — built on first use by scanning all cached PAW book content for TM1 view references. Keyed by `(server, cube, view)`. Progressive filtering: selecting a server shows all affected books; narrowing to a cube or view refines the results.

---

## Notes

- All PAW sessions run under the configured admin account.
- Private books are fully visible to admin — the tool walks `/users/` to enumerate all users' private content.
- Book tab/view data is fetched on demand when a book drawer is opened — the tree load itself does not touch book content.
- `config/servers.json` is gitignored — never commit credentials.

---

## User Guide

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for full usage instructions.

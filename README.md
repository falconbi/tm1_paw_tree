# TM1 PAW Tree

Governance and visibility tool for IBM Planning Analytics Workspace (PAW).

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
| **Workbench vs Dashboard** | Distinct icons for new PAW Workbench and classic Dashboard book types |

---

## Requirements

- Python 3.10+
- IBM Planning Analytics Workspace (PAW) — on-prem
- Authentik as the identity provider (OAuth2 PKCE)

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
PAW_ACCOUNT_ID=your_account_id
PAW_TENANT_ID=your_tenant_id

AUTHENTIK_HOST=http://192.168.x.x:9000
AUTHENTIK_USERNAME=admin
AUTHENTIK_PASSWORD=your_password
```

`PAW_ACCOUNT_ID` and `PAW_TENANT_ID` are used to build deep-links back into PAW. Find them in the PAW URL when logged in: `/?accountId=...&tenantId=...`

### 3. Run

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open **http://localhost:8082**

---

## Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `PAW_HOST` | Yes | PAW server URL e.g. `http://192.168.1.100` |
| `PAW_ACCOUNT_ID` | Yes | PAW account ID (from browser URL) |
| `PAW_TENANT_ID` | Yes | PAW tenant ID (from browser URL) |
| `AUTHENTIK_HOST` | Yes | Authentik IdP URL e.g. `http://192.168.1.100:9000` |
| `AUTHENTIK_USERNAME` | Yes | Admin account used for PAW API access |
| `AUTHENTIK_PASSWORD` | Yes | Password for above account |

---

## User Guide

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for full usage instructions.

---

## Architecture

```
Browser (http://localhost:8082)
    └── Flask app.py
            ├── core/paw_connect.py      → PAW Content Services API (Authentik PKCE)
            ├── core/activity_store.py   → SQLite session/hit tracking
            └── paw_tree/static/         → Single-page HTML frontend
```

PAW authentication uses a 6-step Authentik OAuth2 PKCE flow. Every API call creates a fresh authenticated session — no session caching between requests.

Activity tracking polls PAW asset metadata (not content) every N minutes and diffs `used_date` to detect real book opens without contaminating the data.

---

## Notes

- All PAW sessions run under the configured admin account. The `used_by` field in activity reflects PAW's own attribution, not individual Authentik users.
- Private books are fully visible to admin. The tool walks `/users/` to enumerate all users' private content.
- Book tab/view data is fetched on demand when a book drawer is opened — the tree load itself does not touch book content.

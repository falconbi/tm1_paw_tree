# TM1 PAW Tree — Claude Code Project Brief

**Last updated:** May 2026
**Environment:** Ubuntu (RIG workstation, 192.168.1.171) · PAW V11 at 192.168.1.37 · TM1 V11 at 192.168.1.179

---

## Commands

```bash
# Daily startup
cd ~/apps/tm1_paw_tree && source venv/bin/activate && python3 app.py

# Or use the run script
bash run.sh
```

---

## Architecture

```text
Browser (http://localhost:8082)
    └── Flask app.py
            ├── core/paw_connect.py       → PAW V11 session auth (username/password cookie)
            ├── core/tm1_connect.py       → Multi-server TM1 session manager (HTTP basic auth)
            ├── core/activity_store.py    → SQLite session/hit tracking
            ├── core/groups.json          → Role definitions (governance annotations only)
            └── paw_tree/static/          → Single-page HTML frontend
```

**App runs on RIG (192.168.1.171), not on the PAW server.** Do not deploy to 192.168.1.37.

---

## Auth

**PAW V11 auth:** POST username/password to `/login/form/` → sets `paSession` + `ba-sso-csrf` cookies. No OAuth, no PKCE, no Authentik.

**TM1 auth:** All TM1 calls route through the PAW proxy — no direct TM1 connections:
```
{PAW_HOST}/api/v0/tm1/{server_name}/api/v1/{resource}
```
`TM1ProxySession` in `tm1_connect.py` wraps the cached PAW session and injects the CSRF header automatically. No per-server ports, addresses, or SSL config. PAW session is cached for 10 minutes (`get_cached_paw_session()`).

PAW has no endpoint to list TM1 server names — `config/servers.json` is still needed for that. Format is simply `[{"name": "ServerName"}, ...]`.

---

## Project Structure

```text
~/apps/tm1_paw_tree/
├── app.py                        # Flask server — all routes
├── core/
│   ├── paw_connect.py            # PAW V11 session (get_paw_session, paw_get, PAW_CONFIG)
│   ├── tm1_connect.py            # TM1ProxySession via PAW proxy (get_session, load_servers)
│   ├── activity_store.py         # SQLite activity tracking
│   └── groups.json               # Role/group definitions
├── paw_tree/
│   └── static/
│       └── tm1_paw_tree.html     # Full SPA frontend
├── config/
│   └── servers.json              # TM1 server list — NOT committed to git
├── activity/
│   └── activity.db               # SQLite DB — NOT committed to git
├── docs/
│   ├── USER_GUIDE.md
│   └── images/
├── .env                          # Credentials — NOT committed to git
├── run.sh                        # Startup script
└── requirements.txt
```

---

## Flask Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` or `/workbook-tree` | PAW Tree SPA |
| GET | `/api/config` | Client-safe config (account/tenant IDs for PAW deep-links) |
| GET | `/api/groups` | Group definitions from groups.json |
| GET | `/api/paw/tree` | Full PAW folder/book tree |
| GET | `/api/paw/book/<id>` | On-demand book tab/view detail |
| GET/POST | `/api/paw/activity/config` | Activity polling config |
| POST | `/api/paw/activity/poll` | Trigger immediate poll |
| GET | `/api/paw/activity/stats` | Activity stats for UI |
| GET | `/api/paw/audit/probe` | Audit data for dashboard |
| GET | `/api/paw/users` | All PAW users (for private book enumeration) |
| GET | `/api/tm1/servers` | List of TM1 databases from servers.json |
| GET | `/api/tm1/cubes` | Cubes for a database (`?server=`) |
| GET | `/api/tm1/views` | Views for a cube (`?server=&cube=`) |
| GET | `/api/tm1/dimensions` | Dimensions for a cube (`?server=&cube=`) |
| GET | `/api/tm1/alldimensions` | All dimensions on a server (`?server=`) |
| GET | `/api/tm1/subsets` | Subsets for a dimension (`?server=&dimension=`) |
| GET | `/api/tm1/subset_info` | Subset detail/elements |
| GET | `/api/tm1/views_with_subset` | Views using a subset |
| GET | `/api/tm1/mdx` | MDX for a view |
| POST | `/api/tm1/impact/build` | Rebuild impact index |
| GET | `/api/tm1/impact` | Impact query (`?server=`, `?cube=`, `?view=`, `?dimension=`, `?subset=`) |

---

## Key Conventions

**TM1 objects:** Ignore anything starting with `}` — these are system objects. Always apply `not name.startswith('}')` before iterating.

**PAW paths:** Double URL-encode all paths (`/shared` → `%252fshared`). `quote(quote(path, safe=''), safe='')` is correct — not a bug.

**Credentials:** All in `.env` — never hardcode, never log.

**config/servers.json:** Lists all TM1 databases with address, port, user, password, and `ssl` flag. Not committed to git — deploy separately. Set `ssl: true` for HTTPS databases (self-signed certs accepted via `verify=False`).

---

## Impact Panel

The Impact panel is embedded in the Tree tab as a toggleable right panel (Impact button in toolbar). It answers: *"Which PAW books reference this TM1 object?"*

- **Impact index** (`_impact_index`): dict keyed by `(server, cube, view)` → `[{id, name, path}]`. Built on first use by scanning `_book_cache`.
- **Progressive filtering**: server only → all books on server; server+cube → books in cube; server+cube+view → exact match. Dimension track also supported.
- **Book click**: `navigateToBook(id)` expands ancestors in the tree, scrolls to the row, and fires `showDetail` — no tab switch.

---

## Activity Tracking

Two modes, auto-selected at startup:

- **Log mode**: reads PAW's `WAProxy.log` at `PAW_LOG_PATH`. Gives real per-user attribution.
- **Poll mode**: calls PAW API every N minutes, diffs `used_date` per book. Falls back to this if log is absent or unreadable.

Sessions: book opens within 2 hours are grouped into one session. History retained for configurable days (default 90).

---

## Critical Gotchas

- **PAW proxy for TM1**: `{PAW_HOST}/api/v0/tm1/{server}/api/v1/{resource}` works on V11 for all 7 databases. Future work: migrate `tm1_connect.py` to use this proxy instead of direct connections, eliminating `servers.json` port/SSL config.
- **PAW double-encoding**: paths to PAW Content Services must be double URL-encoded. Already handled in `paw_connect.get_folder_assets()`.
- **Session cookies**: PAW uses `paSession` + `ba-sso-csrf`. The `ba-sso-authenticity` header must equal `ba-sso-csrf` cookie value on every request.
- **TM1 session cache**: `_session_cache` in `tm1_connect.py` is keyed by `(address, port)`. TTL is 10 minutes.
- **Impact index build timing**: index is built from `_book_cache`. If the tree hasn't loaded yet, the index will be empty. The UI rebuilds automatically — don't pre-build at startup.
- **PermissionError on PAW log**: `_activity_mode()` catches `PermissionError` when checking `PAW_LOG_PATH` — falls back to poll mode silently.
- **Private PAW books**: fully visible to admin. Walk `/pacontent/v1/Assets(path='%252fusers')/Assets` to enumerate all users.
- **groups.json**: governance annotations only — not a live identity provider. Never query Authentik or PAW for group membership.

---

## TODO

### High Priority

- [x] Migrate TM1 calls to PAW proxy — done, all 7 servers confirmed working
- [ ] Auto-discover TM1 server names from PAW (no known endpoint — servers.json still required)
- [ ] Add `/api/paw/users` endpoint — fixes orphaned book detection

### Medium Priority
- [ ] Cache PAW sessions (currently re-authenticates on restart)
- [ ] Add `flask-compress` + static cache headers
- [ ] Health Monitor backend (DuckDB + APScheduler)

### PAW Tree Extended Features
- [ ] Action buttons: extract TI process name + parameters from book JSON
- [ ] Websheet scanning: download .xlsx, parse PAX formulas (PAX.VIEW, PAX.ELEMENT, PAX.SUBNM) → cube/view/dimension/subset links
- [ ] Cross-tool link: click cube/view in PAW Tree → highlight in CubeMap

---
paths:
  - "core/paw_connect.py"
  - "paw_tree/**"
  - "app.py"
---
# PAW Conventions

## Path Encoding
- All PAW Content Services paths MUST be double URL-encoded
- `/shared` → `%252fshared` (not `%2fshared`)
- `encode_path()` calls `quote(quote(...))` — this is intentional and correct

## Auth Flow (6-step Authentik PKCE)
1. GET PAW `/login` → capture Authentik redirect URL
2. POST username to Authentik flow executor
3. POST password → returns `xak-flow-redirect`
4. GET `/application/o/authorize/` with `prompt=login` stripped
5. GET consent executor → retrieve auth code redirect
6. GET PAW `/login?code=...` → sets `paSession` + `ba-sso-csrf`

## Required Headers on Every PAW Request
- Cookie: `paSession`
- Header: `ba-sso-authenticity` = value of `ba-sso-csrf` cookie

## Asset Types
- `folder` — content store directory
- `dashboard` — classic PAW book (tabbed pages)
- `workbench` — new PAW experience (different content schema)
- `view` — standalone saved TM1 cube view

## Identity Provider Independence
- **Never query Authentik for governance data** — it changes too often
- `groups.json` is the source of truth for role definitions
- Derive ownership from PAW asset `system_properties.created_user_pretty_name`

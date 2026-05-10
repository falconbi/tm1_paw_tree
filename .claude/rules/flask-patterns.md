---
paths:
  - "app.py"
  - "blueprints/**"
---
# Flask Patterns

## Refresh Endpoint
- Always runs extraction in a background thread — keep it async
- Thread lock + `already_running` check → return 409 if already running
- Never make `/api/refresh` synchronous — TM1 extraction can take 30+ seconds

## Error Handling
- Catch all exceptions in endpoints, log with `log.exception()`, return JSON error
- Store last error + timestamp — expose via `/api/status`
- Never expose raw Python tracebacks to the client

## Config / Secrets
- All credentials live in `.env` — load once at startup, inject into `app.config`
- `/api/config` exposes only client-safe values — never TM1/PAW passwords or URLs

## Non-System Object Filter
- Apply `not name.startswith('}')` before every TM1 object list
- This must be consistent across all endpoints — never skip it

## Response Shape
- Success: `{"status": "ok", "data": ...}`
- Error: `{"status": "error", "message": "...", "timestamp": "..."}`
- Running: `{"status": "running"}` with HTTP 409

## Static Files
- Tools are self-contained HTML files in `<tool>/static/`
- Frontend calls `/api/*` endpoints — never accesses TM1/PAW directly
- `/api/config` is the only bridge between server env and browser

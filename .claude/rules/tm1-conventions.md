---
paths:
  - "core/*.py"
  - "cube_map/*.py"
  - "model_builder/*.py"
---
# TM1 Conventions

## Connection Rules
- Flask endpoints → use `core/tm1_connect.get_session()` (raw requests, fast)
- Extraction/analysis → use `core/tm1py_connect.get_tm1_service()` (TM1py, full objects)
- Never mix the two in the same function

## Object Filtering
- Always filter system objects: `not name.startswith('}')`
- Apply this filter before any loop or list comprehension over TM1 objects

## TM1py V12 Patches
- Patches in `tm1py_connect.py` are required for V12 on-prem — never remove
- `_patched_set_version` → forces version 12.5.5
- `_patched_construct_root` → fixes REST base URL for database-scoped endpoints

## Session Auth
- TM1 auth returns a `TM1SessionId` cookie (not Bearer token)
- Pass via `session_id` param to TM1Service
- PAW auth: `paSession` cookie + `ba-sso-authenticity` header (= value of `ba-sso-csrf`)

## Model Builder Order
- Always run `build_gbl_model.py` before `build_cst_model.py`
- GBL dimensions are dependencies for CST cubes

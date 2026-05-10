"""
cube_map/scan_python_edges.py
─────────────────────────────
Scans Python ETL scripts for TM1 cube read/write operations and returns
edges suitable for merging into tm1_model.json.

Detection strategy:
  1. Variable assignments — CUBE_VAR = 'Cube Name'
  2. Write operations    — write_values(CUBE_VAR, ...) / write_value(value, CUBE_VAR, ...)
  3. Read operations     — get_value(CUBE_VAR, ...) / execute_mdx(CUBE_VAR, ...)
  4. MDX FROM clauses    — FROM [Cube Name] inside string literals
  5. Script-to-script    — import statements that reference other registered scripts

Returns a list of edge dicts:
  { "source": "Script Label", "target": "Cube Name", "direction": "write", "edgeType": "python" }
  { "source": "Cube Name",    "target": "Script Label", "direction": "read",  "edgeType": "python" }

For CubeMap the edges are converted to cube→cube form by the caller.
"""

import re
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# write_values(CUBE_VAR, ...) — cube is 1st arg
_WRITE_MULTI_PATTERN = re.compile(
    r'\btm1\.\w+\.write_values\s*\(\s*([A-Z_][A-Z0-9_]*)',
    re.MULTILINE,
)

# write_value(value, CUBE_VAR, ...) — cube is 2nd arg
_WRITE_SINGLE_PATTERN = re.compile(
    r'\btm1\.\w+\.write_value\s*\([^,\n]+,\s*([A-Z_][A-Z0-9_]*)',
    re.MULTILINE,
)

# TM1py read method names — cube var as 1st arg
_READ_PATTERNS = re.compile(
    r'\btm1\.\w+\.(?:get_value|execute_view|execute_named_mdx)\s*\(\s*([A-Z_][A-Z0-9_]*)',
    re.MULTILINE,
)

# MDX literal: FROM [Cube Name]
_MDX_FROM_LITERAL = re.compile(
    r'FROM\s+\[([^\]\{]+)\]',
    re.IGNORECASE,
)

# MDX f-string interpolation: FROM [{CUBE_VAR}]
_MDX_FROM_FSTRING = re.compile(
    r'FROM\s+\[\{([A-Z_][A-Z0-9_]*)\}\]',
    re.IGNORECASE,
)

# Variable assignment: CUBE_VAR = 'Cube Name'  (ALL_CAPS convention, any indent)
_VAR_ASSIGN_PATTERN = re.compile(
    r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)

# import statements — captures the module path (before 'import', 'as', or end)
_IMPORT_PATTERN = re.compile(
    r'^(?:import|from)\s+([\w.]+)',
    re.MULTILINE,
)


def _detect_triggers(source: str, stem_to_label: dict) -> list[str]:
    """Return labels of registered scripts imported by this source file.

    Matches by filename stem — e.g. 'import etl.load_gl' matches a registered
    script whose path stem is 'load_gl'.
    """
    triggered = []
    for m in _IMPORT_PATTERN.finditer(source):
        module = m.group(1)
        for part in module.split('.'):
            if part in stem_to_label and stem_to_label[part] not in triggered:
                triggered.append(stem_to_label[part])
    return triggered


def _build_var_map(source: str, known_cubes: set) -> dict:
    """Return {VAR_NAME: 'Cube Name'} for all vars assigned to known cube names."""
    var_map = {}
    for m in _VAR_ASSIGN_PATTERN.finditer(source):
        var, value = m.group(1), m.group(2)
        if value in known_cubes:
            var_map[var] = value
    return var_map


def scan_file(filepath: str, known_cubes: set) -> dict:
    """
    Scan a single Python file.

    Returns:
        {
          "reads":  set of cube names read by this script,
          "writes": set of cube names written by this script,
        }
    """
    source = Path(filepath).read_text(encoding='utf-8', errors='replace')

    var_map = _build_var_map(source, known_cubes)

    reads  = set()
    writes = set()

    # write_values(CUBE_VAR, ...) — cube is 1st arg
    for m in _WRITE_MULTI_PATTERN.finditer(source):
        var = m.group(1)
        if var in var_map:
            writes.add(var_map[var])

    # write_value(value, CUBE_VAR, ...) — cube is 2nd arg
    for m in _WRITE_SINGLE_PATTERN.finditer(source):
        var = m.group(1)
        if var in var_map:
            writes.add(var_map[var])

    # Read operations via variable (get_value, execute_view etc.)
    for m in _READ_PATTERNS.finditer(source):
        var = m.group(1)
        if var in var_map:
            reads.add(var_map[var])

    # MDX FROM [Cube Name] literal
    for m in _MDX_FROM_LITERAL.finditer(source):
        cube = m.group(1).strip()
        if cube in known_cubes:
            reads.add(cube)

    # MDX FROM [{CUBE_VAR}] f-string interpolation
    for m in _MDX_FROM_FSTRING.finditer(source):
        var = m.group(1)
        if var in var_map:
            reads.add(var_map[var])

    return {"reads": reads, "writes": writes}


def scan_all(sources_file: str, known_cubes: set) -> list:
    """
    Read python_sources.json and scan every listed script.

    Returns a list of edge dicts ready for merging into tm1_model.json:
      {
        "scriptLabel": str,
        "scriptPath":  str,
        "reads":  [cube_name, ...],
        "writes": [cube_name, ...],
      }
    """
    sources_path = Path(sources_file)
    if not sources_path.exists():
        log.warning(f"python_sources.json not found at {sources_path} — skipping Python edge scan")
        return []

    sources = json.loads(sources_path.read_text())

    # Build stem→label map for trigger detection (e.g. 'load_gl' → 'ETL — Load GL')
    stem_to_label = {
        Path(entry["path"]).stem: entry.get("label", Path(entry["path"]).name)
        for entry in sources
        if entry.get("path")
    }

    results = []

    for entry in sources:
        path  = entry.get("path", "")
        label = entry.get("label", Path(path).name)

        if not Path(path).exists():
            log.warning(f"Python source not found: {path} — skipping")
            continue

        try:
            source_text = Path(path).read_text(encoding='utf-8', errors='replace')
            result   = scan_file(path, known_cubes)
            # Exclude self from trigger list
            triggers = [t for t in _detect_triggers(source_text, stem_to_label) if t != label]
            results.append({
                "scriptLabel": label,
                "scriptPath":  path,
                "reads":    sorted(result["reads"]),
                "writes":   sorted(result["writes"]),
                "triggers": triggers,
            })
            log.info(f"  {label}: {len(result['reads'])} reads, {len(result['writes'])} writes, {len(triggers)} triggers")
        except Exception as e:
            log.warning(f"Failed to scan {path}: {e}")

    return results


if __name__ == "__main__":
    # Quick test — run directly to see what's detected
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    sources_json = Path(__file__).parent / "python_sources.json"
    model_json   = Path(__file__).parent / "tm1_model.json"

    if not model_json.exists():
        print("tm1_model.json not found — run extract_tm1_model.py first")
        sys.exit(1)

    model = json.loads(model_json.read_text())
    known_cubes = set(model.get("cubes", {}).keys())
    print(f"Known cubes: {len(known_cubes)}")

    results = scan_all(str(sources_json), known_cubes)

    print()
    for r in results:
        print(f"\n{'─'*50}")
        print(f"  {r['scriptLabel']}")
        print(f"  Path: {r['scriptPath']}")
        if r["reads"]:
            print(f"  Reads:")
            for c in r["reads"]:
                print(f"    ← {c}")
        if r["writes"]:
            print(f"  Writes:")
            for c in r["writes"]:
                print(f"    → {c}")

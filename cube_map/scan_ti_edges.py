"""
scan_ti_edges.py
────────────────
Static analysis of TM1 TI process code to find cube read/write edges.

Detection strategies (both applied, results merged):

1. Literal cube names in CellPut*/CellGet* calls:
       CellPutN( val, 'My Cube', e1, e2 )   → write to 'My Cube'
       CellGetN( 'My Cube', e1, e2 )         → read from 'My Cube'

2. Variable assignment resolution:
       sCube = 'CST ETL Control';            → track variable
       CellPutS( val, sCube, e1, e2 )        → resolve to 'CST ETL Control'

3. Known-cube cross-reference:
   Any quoted string that exactly matches a known cube name is treated as
   a potential cube reference, regardless of which function it appears in.

Returns per-process: { reads: set, writes: set }
"""

import re
from typing import Dict, Set, Tuple

# ── Patterns ─────────────────────────────────────────────────────────────────

# CellPutN/S/IncrementN — cube is 2nd argument (after value)
_WRITE_LITERAL  = re.compile(
    r'CellPut[NS]\s*\([^,]+,\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)
_WRITE_VAR = re.compile(
    r'CellPut[NS]\s*\([^,]+,\s*([A-Za-z_]\w*)',
    re.IGNORECASE
)
_INCREMENT_LITERAL = re.compile(
    r'CellIncrementN\s*\([^,]+,\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)
_INCREMENT_VAR = re.compile(
    r'CellIncrementN\s*\([^,]+,\s*([A-Za-z_]\w*)',
    re.IGNORECASE
)

# CellGetN/S — cube is 1st argument
_READ_LITERAL = re.compile(
    r'CellGet[NS]\s*\(\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)
_READ_VAR = re.compile(
    r'CellGet[NS]\s*\(\s*([A-Za-z_]\w*)',
    re.IGNORECASE
)

# Variable string assignment:  varName = 'some value';
_VAR_ASSIGN = re.compile(
    r'([A-Za-z_]\w*)\s*=\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)

# ViewExtract / SubsetCreateByMDX etc. — cube is 1st arg (less common)
_VIEW_EXTRACT = re.compile(
    r'(?:ViewExtract|ViewCreate|ViewDestroy|SubsetCreate)\w*\s*\(\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE
)


def _extract_var_map(code: str) -> Dict[str, str]:
    """Return {varName: literal_value} for all simple string assignments in code."""
    result = {}
    for m in _VAR_ASSIGN.finditer(code):
        result[m.group(1).lower()] = m.group(2)
    return result


def _resolve(name: str, var_map: Dict[str, str]) -> str:
    """If name looks like a variable, resolve it; else return as-is."""
    if name.startswith(("'", '"')):
        return name.strip("'\"")
    return var_map.get(name.lower(), '')


def scan_process(code: str, known_cubes: Set[str]) -> Tuple[Set[str], Set[str]]:
    """
    Scan combined TI code string.
    Returns (reads, writes) — sets of cube names that exist in known_cubes.
    """
    var_map  = _extract_var_map(code)
    reads:  Set[str] = set()
    writes: Set[str] = set()

    known_upper = {c.upper(): c for c in known_cubes}

    def add_write(name: str):
        resolved = _resolve(name, var_map)
        canonical = known_upper.get(resolved.upper())
        if canonical:
            writes.add(canonical)

    def add_read(name: str):
        resolved = _resolve(name, var_map)
        canonical = known_upper.get(resolved.upper())
        if canonical:
            reads.add(canonical)

    for m in _WRITE_LITERAL.finditer(code):
        add_write(m.group(1))
    for m in _WRITE_VAR.finditer(code):
        add_write(m.group(1))
    for m in _INCREMENT_LITERAL.finditer(code):
        add_write(m.group(1))
    for m in _INCREMENT_VAR.finditer(code):
        add_write(m.group(1))
    for m in _READ_LITERAL.finditer(code):
        add_read(m.group(1))
    for m in _READ_VAR.finditer(code):
        add_read(m.group(1))
    for m in _VIEW_EXTRACT.finditer(code):
        add_read(m.group(1))

    # Strategy 3: any quoted string matching a known cube
    for m in re.finditer(r'[\'"]([^\'"]{3,})[\'"]', code):
        canonical = known_upper.get(m.group(1).upper())
        if canonical:
            # Classify as write if a write function is nearby on the same line
            line = code[max(0, m.start()-80):m.end()+10]
            if re.search(r'CellPut|CellIncrement', line, re.IGNORECASE):
                writes.add(canonical)
            elif re.search(r'CellGet|ViewExtract', line, re.IGNORECASE):
                reads.add(canonical)

    # A cube in both reads+writes is a write (reads are often incidental)
    return reads - writes, writes


def scan_all_ti(processes: list, known_cubes: Set[str]) -> list:
    """
    processes: list of dicts with keys Name, PrologProcedure,
               MetadataProcedure, DataProcedure, EpilogProcedure
    Returns list of { processName, reads: set, writes: set }
    — only processes with at least one cube edge.
    """
    results = []
    for p in processes:
        name = p.get('Name', '')
        code = '\n'.join(filter(None, [
            p.get('PrologProcedure', '') or '',
            p.get('MetadataProcedure', '') or '',
            p.get('DataProcedure', '') or '',
            p.get('EpilogProcedure', '') or '',
        ]))
        reads, writes = scan_process(code, known_cubes)
        if reads or writes:
            results.append({
                'processName': name,
                'reads':  reads,
                'writes': writes,
                'code': {
                    'prolog':   p.get('PrologProcedure', '') or '',
                    'metadata': p.get('MetadataProcedure', '') or '',
                    'data':     p.get('DataProcedure', '') or '',
                    'epilog':   p.get('EpilogProcedure', '') or '',
                },
            })
    return results


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys, os, json
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    env_path = Path(__file__).resolve().parent.parent / '.env'
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

    from core.tm1_connect import get_session
    s = get_session()

    cubes_r = s.get(s.base_url + "/Cubes?$select=Name&$filter=not startswith(Name,'}')")
    known_cubes = {c['Name'] for c in cubes_r.json().get('value', [])}

    procs_r = s.get(
        s.base_url +
        "/Processes?$select=Name,PrologProcedure,MetadataProcedure,DataProcedure,EpilogProcedure"
        "&$filter=not startswith(Name,'}')"
    )
    processes = procs_r.json().get('value', [])
    print(f"Scanning {len(processes)} TI processes against {len(known_cubes)} cubes...\n")

    results = scan_all_ti(processes, known_cubes)
    for r in results:
        print(f"  {r['processName']}")
        if r['reads']:  print(f"    reads:  {sorted(r['reads'])}")
        if r['writes']: print(f"    writes: {sorted(r['writes'])}")
    print(f"\n{len(results)} processes with cube edges")

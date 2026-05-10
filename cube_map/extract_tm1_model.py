"""
extract_tm1_model.py
────────────────────
Connects to TM1 V12 on-prem via TM1py and extracts the full cube model
into tm1_model.json — which the CubeMap diagram reads at load time.

Usage:
    python3 extract_tm1_model.py              # extract all cubes
    python3 extract_tm1_model.py --prefix CST # only cubes starting with CST

Output:
    tm1_model.json  (same directory — copy next to tm1_cube_lineage.html)

Run this script any time the model changes to refresh the diagram.
"""

import sys
import re
import json
import argparse
from datetime import datetime, timezone

# ── Path setup ───────────────────────────────────────────────────────────────
# Adjust this if tm1py_connect.py is in a different location
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.tm1py_connect import get_tm1_service, TM1_CONFIG


# ── Helpers ───────────────────────────────────────────────────────────────────

def classify_cube_type(cube_name: str, dims: list[str], has_rules: bool, rules_text: str) -> str:
    """
    Classify a cube into one of six types for colour coding in the diagram.
    Uses cube name conventions from your naming standard first,
    then falls back to rules/dimension analysis.
    """
    name_upper = cube_name.upper()

    # Name-convention hints (your standard: CST prefix + descriptive name)
    if 'RECONCILI' in name_upper:
        return 'recon'
    if any(x in name_upper for x in ['REPORT', 'P&L', 'PROFIT', 'LOSS']):
        return 'report'
    if 'DRIVER' in name_upper:
        return 'driver'
    if 'ALLOCATION' in name_upper:
        return 'allocation'
    if any(x in name_upper for x in ['GL INPUT', 'INPUT', 'LOAD', 'IMPORT']):
        return 'input'
    if any(x in name_upper for x in ['SERVICE LINE', 'COST ROLLUP', 'ROLL']):
        return 'rollup'

    # Rules-based fallback
    if not has_rules:
        return 'input'
    if rules_text and 'DB(' in rules_text.upper():
        return 'allocation'

    return 'input'


def extract_rules_header(rules_text: str) -> str:
    """Extract comment block from top of rules file (lines starting with #)."""
    if not rules_text:
        return ''
    lines = rules_text.split('\n')
    header_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            header_lines.append(stripped.lstrip('#').strip())
        elif stripped == '':
            if header_lines:
                continue  # allow blank lines within header
        else:
            break  # hit actual rules code
    return ' '.join(l for l in header_lines if l)


def analyse_rules(rules_text: str) -> dict:
    """Count rules metrics for complexity scoring."""
    if not rules_text:
        return {'total': 0, 'lines': 0, 'comments': 0, 'dbRefs': 0,
                'feeders': 0, 'ifs': 0, 'stet': 0, 'skip': 0}

    all_lines   = rules_text.split('\n')
    total       = len(all_lines)
    comments    = sum(1 for l in all_lines if l.strip().startswith('#'))
    blanks      = sum(1 for l in all_lines if l.strip() == '')
    rule_lines  = total - comments - blanks
    upper       = rules_text.upper()

    return {
        'total':    total,
        'lines':    rule_lines,
        'comments': comments,
        'dbRefs':   upper.count('DB('),
        'feeders':  sum(1 for l in all_lines if 'FEEDERS' in l.upper()),
        'ifs':      upper.count('\nIF(') + (1 if upper.startswith('IF(') else 0),
        'stet':     upper.count('STET'),
        'skip':     upper.count('SKIP'),
    }


def find_db_references(cube_name: str, rules_text: str) -> list[dict]:
    """Find all DB() calls in rules, classified as rule_calc or rule_feeder.

    Splits rules text at the FEEDERS; keyword — DB() calls before it are
    real data flow (rule_calc), DB() calls after are performance hints only
    (rule_feeder) and should not be treated as true lineage edges.
    """
    if not rules_text:
        return []

    # Split at FEEDERS; (case-insensitive) — take everything before as calc section
    feeders_split = re.split(r'FEEDERS\s*;', rules_text, maxsplit=1, flags=re.IGNORECASE)
    calc_section   = feeders_split[0]
    feeder_section = feeders_split[1] if len(feeders_split) > 1 else ''

    pattern = r'DB\s*\(\s*["\']([^"\']+)["\']'
    seen  = set()
    edges = []

    for section, edge_type in [(calc_section, 'rule_calc'), (feeder_section, 'rule_feeder')]:
        for target in re.findall(pattern, section, re.IGNORECASE):
            key = (cube_name, target, edge_type)
            if key not in seen and target.lower() != cube_name.lower():
                seen.add(key)
                edges.append({'source': target, 'target': cube_name, 'type': edge_type})

    return edges


def get_cube_attribute(tm1, cube_name: str, attr: str) -> str:
    """Safely read a cube attribute — returns '' if not found."""
    try:
        val = tm1.cubes.get_attribute(cube_name, attr)
        return val or ''
    except Exception:
        return ''


def classify_dimension_kind(dim_name: str) -> str:
    """Classify a dimension as global / measure / control / cst."""
    if dim_name.startswith('}'):
        return 'control'
    name_upper = dim_name.upper()
    if name_upper.startswith('GBL '):
        return 'global'
    if 'MEASURE' in name_upper:
        return 'measure'
    return 'cst'


# ── RAM extraction ────────────────────────────────────────────────────────────

def fetch_cube_ram(tm1, known_cubes: set) -> dict:
    """
    Check/enable Performance Monitor, then query }StatsByCube for per-cube RAM.
    Returns {cube_name: ram_mb} — empty dict if unavailable or PM just enabled.
    """
    # Ensure Performance Monitor is running — use }StatsByCube existence as proxy
    try:
        all_names = tm1.cubes.get_all_names()
        if '}StatsByCube' not in all_names:
            print("   }StatsByCube not found — enabling Performance Monitor...")
            tm1.server.start_performance_monitor()
            print("   ✅ Performance Monitor enabled — re-run in ~1 min for RAM data")
            return {}
    except Exception as e:
        print(f"   ⚠️  Performance Monitor check failed: {e}")

    # Query }StatsByCube — Memory Used is in bytes
    try:
        mdx = (
            "SELECT NON EMPTY {[}PerfCubes].Members} ON ROWS, "
            "{[}StatsByCubeStats].[Memory Used]} ON COLUMNS "
            "FROM [}StatsByCube] "
            "WHERE ([}TimeIntervals].[LATEST])"
        )
        cells = tm1.cells.execute_mdx(
            mdx,
            element_unique_names=False,
            skip_zeros=True,
        )
        result = {}
        for addr, cell in cells.items():
            cube_name = addr[0]
            value = cell.get('Value') if isinstance(cell, dict) else cell
            if cube_name in known_cubes and value:
                result[cube_name] = round(value / (1024 * 1024), 1)

        if result:
            print(f"   RAM data: {len(result)} cubes  (max {max(result.values()):.1f} MB)")
        else:
            print("   ⚠️  }StatsByCube returned no data — wait ~1 min for first collection")
        return result
    except Exception as e:
        print(f"   ⚠️  }}StatsByCube query failed: {e}")
        return {}


# ── Main extraction ───────────────────────────────────────────────────────────

def extract_model(prefix_filter: str = '') -> dict:
    print(f"\nConnecting to TM1 — {TM1_CONFIG['address']}:{TM1_CONFIG['port']}")
    print(f"Database: {TM1_CONFIG['database']}\n")

    with get_tm1_service() as tm1:
        print("✅ Connected\n")

        # 1. Get all cube names (exclude system cubes starting with })
        all_cube_names = [
            c for c in tm1.cubes.get_all_names()
            if not c.startswith('}')
        ]
        if prefix_filter:
            all_cube_names = [c for c in all_cube_names if c.upper().startswith(prefix_filter.upper())]

        print(f"Found {len(all_cube_names)} cubes{f' matching prefix \"{prefix_filter}\"' if prefix_filter else ''}\n")

        cubes_data = {}
        all_edges  = []

        for cube_name in all_cube_names:
            print(f"  Processing: {cube_name}")
            try:
                cube = tm1.cubes.get(cube_name)

                # Dimensions
                dims_raw = cube.dimensions  # list of dimension names in order
                dims = [
                    {'n': d, 'k': classify_dimension_kind(d)}
                    for d in dims_raw
                ]

                # Rules
                has_rules  = cube.has_rules
                rules_text = cube.rules.text if has_rules else ''
                rules_stats = analyse_rules(rules_text)

                # Description — try attributes first, then rules header, then blank
                desc1 = get_cube_attribute(tm1, cube_name, 'Description_1')
                desc2 = get_cube_attribute(tm1, cube_name, 'Description_2')
                desc3 = get_cube_attribute(tm1, cube_name, 'Description_3')
                desc_source = 'manual' if any([desc1, desc2, desc3]) else ''

                if not desc1:
                    # Try rules header
                    header = extract_rules_header(rules_text)
                    if header:
                        desc1 = header
                        desc_source = 'rules_header'
                    else:
                        desc1 = f'{cube_name} — description not yet set.'
                        desc_source = 'ai_inferred'

                description = ' '.join(filter(None, [desc1, desc2, desc3]))

                # Cube type classification
                cube_type = classify_cube_type(
                    cube_name, dims_raw, has_rules, rules_text
                )

                # DB() rule references → edges
                rule_edges = find_db_references(cube_name, rules_text)
                all_edges.extend(rule_edges)

                # Public views
                try:
                    views = tm1.views.get_all_names(cube_name, private=False)
                except Exception:
                    views = []

                # Measure elements — leaf elements of the measure dimension
                measures = []
                measure_dim = next(
                    (d for d in dims_raw if classify_dimension_kind(d) == 'measure'),
                    None
                )
                if measure_dim:
                    try:
                        measures = tm1.elements.get_leaf_element_names(measure_dim, measure_dim)
                    except Exception:
                        measures = []

                cubes_data[cube_name] = {
                    'type':       cube_type,
                    'desc':       description,
                    'descSource': desc_source,
                    'dims':       dims,
                    'rules':      rules_stats,
                    'rulesText':  rules_text,
                    'hasRules':   has_rules,
                    'ramMb':      None,
                    'views':      views,
                    'measures':   measures,
                    'from':       [],   # filled in below
                    'to':         [],   # filled in below
                }

            except Exception as e:
                print(f"    ⚠️  Error processing {cube_name}: {e}")
                continue

        # 2. Build from/to from edges (only edges where both cubes are in scope)
        in_scope = set(cubes_data.keys())
        for edge in all_edges:
            src, tgt = edge['source'], edge['target']
            etype = edge.get('type', 'rule_calc')
            if src in in_scope and tgt in in_scope:
                # Store as {name, type} objects so UI knows edge type
                if not any(e['n'] == tgt for e in cubes_data[src]['to']):
                    cubes_data[src]['to'].append({'n': tgt, 't': etype})
                if not any(e['n'] == src for e in cubes_data[tgt]['from']):
                    cubes_data[tgt]['from'].append({'n': src, 't': etype})

        # 3. Python ETL edges — scan registered scripts for cube read/write ops
        try:
            from cube_map.scan_python_edges import scan_all
            py_sources = Path(__file__).parent / 'python_sources.json'
            py_results = scan_all(str(py_sources), set(cubes_data.keys()))
            for r in py_results:
                label = r['scriptLabel']
                cubes_data[label] = {
                    'type':       'python',
                    'desc':       f"Python ETL script: {Path(r['scriptPath']).name}",
                    'descSource': 'auto',
                    'dims':       [],
                    'rules':      {'total': 0, 'lines': 0, 'comments': 0,
                                   'dbRefs': 0, 'feeders': 0, 'ifs': 0, 'stet': 0, 'skip': 0},
                    'ramMb':      None,
                    'from':       [{'n': n, 't': 'python'} for n in sorted(r['reads'])],
                    'to':         [{'n': n, 't': 'python'} for n in sorted(r['writes'])],
                    'scriptPath': r['scriptPath'],
                }
                for cube_name in r['reads']:
                    if cube_name in cubes_data:
                        if not any(e['n'] == label for e in cubes_data[cube_name]['to']):
                            cubes_data[cube_name]['to'].append({'n': label, 't': 'python'})
                for cube_name in r['writes']:
                    if cube_name in cubes_data:
                        if not any(e['n'] == label for e in cubes_data[cube_name]['from']):
                            cubes_data[cube_name]['from'].append({'n': label, 't': 'python'})

            # Script-to-script trigger edges (second pass — all python nodes now exist)
            for r in py_results:
                label = r['scriptLabel']
                for triggered in r.get('triggers', []):
                    if triggered in cubes_data:
                        if not any(e['n'] == triggered for e in cubes_data[label]['to']):
                            cubes_data[label]['to'].append({'n': triggered, 't': 'python_trigger'})
                        if not any(e['n'] == label for e in cubes_data[triggered]['from']):
                            cubes_data[triggered]['from'].append({'n': label, 't': 'python_trigger'})

            if py_results:
                print(f"   Python ETL nodes: {len(py_results)}")
        except Exception as e:
            print(f"   ⚠️  Python edge scan failed: {e}")

        # 4. TI process edges — scan all process code for cube read/write ops
        try:
            from cube_map.scan_ti_edges import scan_all_ti
            from core.tm1_connect import get_session as _get_raw
            _raw = _get_raw()
            procs_r = _raw.get(
                _raw.base_url +
                "/Processes?$select=Name,PrologProcedure,MetadataProcedure,"
                "DataProcedure,EpilogProcedure&$filter=not startswith(Name,'}')"
            )
            ti_processes = procs_r.json().get('value', [])
            ti_results = scan_all_ti(ti_processes, set(cubes_data.keys()))
            empty_rules = {'total': 0, 'lines': 0, 'comments': 0,
                           'dbRefs': 0, 'feeders': 0, 'ifs': 0, 'stet': 0, 'skip': 0}
            for r in ti_results:
                label = r['processName']
                cubes_data[label] = {
                    'type':       'ti',
                    'desc':       f"TI Process: {label}",
                    'descSource': 'auto',
                    'dims':       [],
                    'rules':      empty_rules,
                    'rulesText':  '',
                    'hasRules':   False,
                    'ramMb':      None,
                    'views':      [],
                    'tiCode':     r.get('code', {}),
                    'from':       [{'n': n, 't': 'ti'} for n in sorted(r['reads'])],
                    'to':         [{'n': n, 't': 'ti'} for n in sorted(r['writes'])],
                }
                for cube_name in r['reads']:
                    if cube_name in cubes_data:
                        if not any(e['n'] == label for e in cubes_data[cube_name]['to']):
                            cubes_data[cube_name]['to'].append({'n': label, 't': 'ti'})
                for cube_name in r['writes']:
                    if cube_name in cubes_data:
                        if not any(e['n'] == label for e in cubes_data[cube_name]['from']):
                            cubes_data[cube_name]['from'].append({'n': label, 't': 'ti'})
            if ti_results:
                print(f"   TI process nodes: {len(ti_results)}")
        except Exception as e:
            print(f"   ⚠️  TI edge scan failed: {e}")

        # 5. RAM usage from }StatsByCube
        print("\n   Fetching RAM usage...")
        tm1_cubes = {k for k, v in cubes_data.items() if v.get('type') != 'python'}
        ram_data = fetch_cube_ram(tm1, tm1_cubes)
        for cube_name, ram_mb in ram_data.items():
            if cube_name in cubes_data:
                cubes_data[cube_name]['ramMb'] = ram_mb

        # 5. Architecture score
        score = calculate_architecture_score(cubes_data, all_edges)

        model = {
            'meta': {
                'database':    TM1_CONFIG['database'],
                'server':      f"{TM1_CONFIG['address']}:{TM1_CONFIG['port']}",
                'extractedAt': datetime.now(timezone.utc).isoformat(),
                'cubeCount':   len(cubes_data),
                'archScore':   score,
            },
            'cubes': cubes_data,
        }

        print(f"\n✅ Extracted {len(cubes_data)} cubes")
        print(f"   Architecture score: {score}/100")
        return model


def calculate_architecture_score(cubes: dict, edges: list) -> int:
    """
    Score the model architecture 0-100.
    Penalises: undocumented cubes, very high complexity, circular-looking refs.
    Rewards:   clean left-to-right flow, documented cubes.
    """
    score = 100

    for name, c in cubes.items():
        # Penalise undocumented cubes
        if c['descSource'] == 'ai_inferred':
            score -= 3

        # Penalise very high complexity
        r = c['rules']
        complexity = r['lines'] + r['dbRefs']*5 + r['ifs']*3 + r['feeders']*2
        if complexity > 300:
            score -= 10
        elif complexity > 150:
            score -= 5
        elif complexity > 60:
            score -= 2

    # Penalise backwards edges (source appears after target alphabetically — rough heuristic)
    cube_names = list(cubes.keys())
    for edge in edges:
        src, tgt = edge['source'], edge['target']
        if src in cube_names and tgt in cube_names:
            if cube_names.index(src) > cube_names.index(tgt):
                score -= 3  # backwards reference

    return max(0, min(100, score))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract TM1 model to JSON for CubeMap diagram')
    parser.add_argument('--prefix', default='', help='Only extract cubes with this prefix (e.g. CST)')
    parser.add_argument('--out',    default='tm1_model.json', help='Output file path')
    args = parser.parse_args()

    model = extract_model(prefix_filter=args.prefix)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Written to: {args.out}")
    print(f"   Copy this file to the same folder as tm1_cube_lineage.html\n")

    # Quick summary
    print("── Cube summary ─────────────────────────────────────────")
    for name, c in model['cubes'].items():
        r = c['rules']
        conn = len(c['from']) + len(c['to'])
        print(f"  {name:<40} type={c['type']:<12} dims={len(c['dims'])}  "
              f"rules={r['lines']}  conn={conn}  src={c['descSource']}")
    print("─────────────────────────────────────────────────────────\n")

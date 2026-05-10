"""
app.py — TM1 CubeMap Flask Server
──────────────────────────────────
Serves the CubeMap diagram and provides a live refresh API
that pulls fresh data from TM1 V12 on demand.

Usage:
    cd ~/apps/tm1_governance
    ./run.sh

Then open: http://localhost:8082

Endpoints:
    GET  /                   → serves tm1_cube_lineage.html
    GET  /api/model          → returns cached tm1_model.json
    POST /api/refresh        → re-extracts from TM1, updates cache
    GET  /api/status         → server + last-refresh info
"""

import os
import re
import sys
import io
import csv
import json
import shutil
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, abort, request
from flask_compress import Compress

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
MODEL_FILE = BASE_DIR / 'cube_map' / 'tm1_model.json'

sys.path.insert(0, str(BASE_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('cubemap')

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(BASE_DIR))

Compress(app)

STATIC_EXTENSIONS = {'.html', '.js', '.css', '.json', '.ico', '.png', '.svg', '.woff', '.woff2'}

@app.after_request
def add_cache_headers(response):
    ext = Path(request.path).suffix.lower()
    if ext in STATIC_EXTENSIONS and not request.path.startswith('/api/'):
        response.cache_control.max_age = 2592000  # 30 days
        response.cache_control.public  = True
    return response

# Thread lock — prevents two simultaneous refreshes
_refresh_lock = threading.Lock()
_refresh_status = {
    'running':    False,
    'lastRun':    None,
    'lastResult': 'never',
    'error':      None,
}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/favicon.ico')
@app.route('/favicon.svg')
def favicon():
    """Suite-level fallback favicon — 2x2 app grid."""
    return send_from_directory(str(BASE_DIR / 'static'), 'favicon.svg', mimetype='image/svg+xml')

@app.route('/cube-map/favicon.svg')
def favicon_cube_map():
    return send_from_directory(str(BASE_DIR / 'cube_map' / 'static'), 'favicon.svg', mimetype='image/svg+xml')

@app.route('/paw-tree/favicon.svg')
def favicon_paw_tree():
    return send_from_directory(str(BASE_DIR / 'paw_tree' / 'static'), 'favicon.svg', mimetype='image/svg+xml')

@app.route('/health-monitor/favicon.svg')
def favicon_health_monitor():
    return send_from_directory(str(BASE_DIR / 'health_monitor' / 'static'), 'favicon.svg', mimetype='image/svg+xml')


@app.route('/')
def index():
    """Serve the CubeMap HTML diagram."""
    static_dir = BASE_DIR / 'cube_map' / 'static'
    if not (static_dir / 'tm1_cube_lineage.html').exists():
        abort(404, 'cube_map/static/tm1_cube_lineage.html not found')
    resp = send_from_directory(str(static_dir), 'tm1_cube_lineage.html')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/workbook-tree')
def workbook_tree():
    """Serve the PAW Workbook Tree governance explorer."""
    static_dir = BASE_DIR / 'paw_tree' / 'static'
    if not (static_dir / 'tm1_paw_tree.html').exists():
        abort(404, 'paw_tree/static/tm1_paw_tree.html not found')
    return send_from_directory(str(static_dir), 'tm1_paw_tree.html')


@app.route('/health-monitor')
def health_monitor():
    """Serve the Health Monitor dashboard."""
    static_dir = BASE_DIR / 'health_monitor' / 'static'
    if not (static_dir / 'tm1_health_monitor.html').exists():
        abort(404, 'health_monitor/static/tm1_health_monitor.html not found')
    return send_from_directory(str(static_dir), 'tm1_health_monitor.html')


@app.route('/api/model')
def api_model():
    """Return the cached TM1 model JSON."""
    if not MODEL_FILE.exists():
        return jsonify({'error': 'Model cache not found — POST /api/refresh to extract'}), 404
    with open(MODEL_FILE, encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """Re-extract the TM1 model and update the cache."""
    if _refresh_status['running']:
        return jsonify({'status': 'already_running'}), 409

    def do_refresh():
        with _refresh_lock:
            _refresh_status['running'] = True
            _refresh_status['error'] = None
            try:
                from cube_map.extract_tm1_model import extract_model
                import json as _json
                model = extract_model()
                with open(MODEL_FILE, 'w', encoding='utf-8') as _f:
                    _json.dump(model, _f, indent=2, ensure_ascii=False)
                _refresh_status['lastResult'] = 'success'
                log.info('Model refresh completed successfully')
            except Exception as e:
                _refresh_status['lastResult'] = 'error'
                _refresh_status['error'] = str(e)
                log.error(f'Model refresh failed: {e}')
            finally:
                _refresh_status['running'] = False
                _refresh_status['lastRun'] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=do_refresh, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/status')
def api_status():
    """Return server info and last-refresh status."""
    return jsonify({
        'status':      'ok',
        'baseDir':     str(BASE_DIR),
        'modelFile':   str(MODEL_FILE),
        'modelCached': MODEL_FILE.exists(),
        'refresh':     _refresh_status,
    })


LAYOUTS_DIR = BASE_DIR / 'cube_map' / 'layouts'
LAYOUTS_DIR.mkdir(exist_ok=True)

TAGS_FILE = BASE_DIR / 'cube_map' / 'tags.json'

@app.route('/api/tags', methods=['GET'])
def api_tags_get():
    if not TAGS_FILE.exists():
        return jsonify({'tagDefs': {}, 'cubeTags': {}})
    return jsonify(json.loads(TAGS_FILE.read_text()))

@app.route('/api/tags', methods=['POST'])
def api_tags_save():
    data = request.get_json(force=True)
    TAGS_FILE.write_text(json.dumps(data, indent=2))
    return jsonify({'status': 'ok'})

@app.route('/api/layouts', methods=['GET'])
def api_layouts_list():
    """List saved layout names."""
    names = sorted(p.stem for p in LAYOUTS_DIR.glob('*.json'))
    return jsonify({'layouts': names})

@app.route('/api/layouts/<name>', methods=['GET'])
def api_layout_get(name):
    """Return saved node positions for a named layout."""
    path = LAYOUTS_DIR / f'{name}.json'
    if not path.exists():
        return jsonify({'error': 'not found'}), 404
    return jsonify(json.loads(path.read_text()))

@app.route('/api/layouts/<name>', methods=['POST'])
def api_layout_save(name):
    """Save node positions. Body: {positions: [{id, x, y}, ...]}"""
    if not name or '/' in name or '..' in name:
        return jsonify({'error': 'invalid name'}), 400
    data = request.get_json(force=True)
    positions = data.get('positions', [])
    path = LAYOUTS_DIR / f'{name}.json'
    path.write_text(json.dumps({'name': name, 'positions': positions}, indent=2))
    log.info('Layout saved: %s (%d nodes)', name, len(positions))
    return jsonify({'status': 'ok', 'name': name, 'nodes': len(positions)})

@app.route('/api/layouts/<name>', methods=['DELETE'])
def api_layout_delete(name):
    """Delete a saved layout."""
    path = LAYOUTS_DIR / f'{name}.json'
    if path.exists():
        path.unlink()
    return jsonify({'status': 'ok'})


@app.route('/api/tm1/performance-monitor', methods=['GET', 'POST'])
def api_performance_monitor():
    """
    GET:  returns {enabled: bool, supported: bool}
          supported=False when TM1 instance doesn't expose PerformanceMonitorOn
          (e.g. V12 cloud).  supported=True on V11 on-prem.
    POST: {enabled: bool} — starts or stops Performance Monitor via TM1py.
          Returns 501 when not supported.
    """
    try:
        from core.tm1_connect import get_session
        session = get_session()

        # Support check: StaticConfiguration must expose PerformanceMonitorOn
        r_cfg = session.get(f"{session.base_url}/StaticConfiguration")
        admin_keys = r_cfg.json().get('Administration', {}).keys() if r_cfg.ok else []
        supported = 'PerformanceMonitorOn' in admin_keys

        if request.method == 'GET':
            if not supported:
                return jsonify({'enabled': False, 'supported': False})
            # PM is on if }StatsByCube exists
            r = session.get(f"{session.base_url}/Cubes?$filter=Name eq '}}StatsByCube'&$select=Name")
            enabled = len(r.json().get('value', [])) > 0
            return jsonify({'enabled': enabled, 'supported': True})

        # POST
        if not supported:
            return jsonify({'error': 'Performance Monitor not supported on this server'}), 501

        from core.tm1py_connect import get_tm1_service
        enabled = request.json.get('enabled', False)
        with get_tm1_service() as tm1:
            if enabled:
                tm1.server.start_performance_monitor()
            else:
                tm1.server.stop_performance_monitor()
        log.info('Performance Monitor %s', 'started' if enabled else 'stopped')
        return jsonify({'enabled': enabled, 'supported': True})

    except Exception as e:
        log.error('Performance Monitor toggle error: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/cubes')
def api_tm1_cubes():
    """Return all non-system cube names from TM1."""
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(f"{session.base_url}/Cubes?$select=Name")
        r.raise_for_status()
        cubes = sorted(
            c['Name'] for c in r.json().get('value', [])
            if not c['Name'].startswith('}')
        )
        return jsonify({'cubes': cubes})
    except Exception as e:
        log.error(f'TM1 cubes error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/views')
def api_tm1_views():
    """Return all non-system view names for a cube."""
    cube = request.args.get('cube', '').strip()
    if not cube:
        return jsonify({'error': 'cube parameter required'}), 400
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(f"{session.base_url}/Cubes('{cube}')/Views?$select=Name")
        r.raise_for_status()
        views = sorted(
            v['Name'] for v in r.json().get('value', [])
            if not v['Name'].startswith('}')
        )
        return jsonify({'views': views})
    except Exception as e:
        log.error(f'TM1 views error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/dimensions')
def api_tm1_dimensions():
    """Return all non-system dimension names for a cube."""
    cube = request.args.get('cube', '').strip()
    if not cube:
        return jsonify({'error': 'cube parameter required'}), 400
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(f"{session.base_url}/Cubes('{cube}')/Dimensions?$select=Name")
        r.raise_for_status()
        dims = sorted(
            d['Name'] for d in r.json().get('value', [])
            if not d['Name'].startswith('}')
        )
        return jsonify({'dimensions': dims})
    except Exception as e:
        log.error(f'TM1 dimensions error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/subsets')
def api_tm1_subsets():
    """Return all non-system subset names for a dimension."""
    cube      = request.args.get('cube', '').strip()
    dimension = request.args.get('dimension', '').strip()
    if not cube or not dimension:
        return jsonify({'error': 'cube and dimension parameters required'}), 400
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(
            f"{session.base_url}/Dimensions('{dimension}')/Hierarchies('{dimension}')/Subsets?$select=Name"
        )
        r.raise_for_status()
        subsets = sorted(
            s['Name'] for s in r.json().get('value', [])
            if not s['Name'].startswith('}')
        )
        return jsonify({'subsets': subsets})
    except Exception as e:
        log.error(f'TM1 subsets error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/subset_info')
def api_tm1_subset_info():
    """Return member count for a subset."""
    dimension = request.args.get('dimension', '').strip()
    subset    = request.args.get('subset', '').strip()
    if not dimension or not subset:
        return jsonify({'error': 'dimension and subset parameters required'}), 400
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(
            f"{session.base_url}/Dimensions('{dimension}')/Hierarchies('{dimension}')"
            f"/Subsets('{subset}')/Elements?$count=true&$top=0"
        )
        r.raise_for_status()
        return jsonify({'count': r.json().get('@odata.count', 0)})
    except Exception as e:
        log.error(f'TM1 subset_info error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/views_with_subset')
def api_tm1_views_with_subset():
    """Return view names that use a specific subset for a given dimension on a cube."""
    cube      = request.args.get('cube', '').strip()
    dimension = request.args.get('dimension', '').strip()
    subset    = request.args.get('subset', '').strip()
    if not cube or not dimension or not subset:
        return jsonify({'error': 'cube, dimension and subset parameters required'}), 400
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(
            f"{session.base_url}/Cubes('{cube}')/Views?$expand=Rows,Columns,Titles"
        )
        r.raise_for_status()
        dim_lc    = dimension.lower()
        subset_lc = subset.lower()
        matching  = []
        for view in r.json().get('value', []):
            name = view.get('Name', '')
            if name.startswith('}'):
                continue
            found = False
            for axis in ('Rows', 'Columns', 'Titles'):
                for entry in (view.get(axis) or []):
                    if (entry.get('DimensionName', '').lower() == dim_lc and
                            entry.get('SubsetName', '').lower() == subset_lc):
                        found = True
                        break
                if found:
                    break
            if found:
                matching.append(name)
        return jsonify({'views': matching})
    except Exception as e:
        log.error(f'TM1 views_with_subset error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/tm1/mdx')
def api_tm1_mdx():
    """Return the MDX query for a named view (MDX views only)."""
    cube = request.args.get('cube', '').strip()
    view = request.args.get('view', '').strip()
    if not cube or not view:
        return jsonify({'error': 'cube and view parameters required'}), 400
    try:
        from core.tm1_connect import get_session
        session = get_session()
        r = session.get(f"{session.base_url}/Cubes('{cube}')/Views('{view}')?$select=Name,MDX")
        r.raise_for_status()
        data = r.json()
        mdx  = data.get('MDX') or ''
        return jsonify({
            'mdx':     mdx or None,
            'type':    'MDXView' if mdx else 'NativeView',
            'message': None if mdx else 'Native view — no MDX query',
        })
    except Exception as e:
        log.error(f'TM1 MDX error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/config')
def api_config():
    """Return client-safe config values needed by the frontend."""
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
    return jsonify({
        'paw_host':       os.environ.get('PAW_HOST', ''),
        'paw_account_id': os.environ.get('PAW_ACCOUNT_ID', ''),
        'paw_tenant_id':  os.environ.get('PAW_TENANT_ID', ''),
    })


@app.route('/api/groups')
def api_groups():
    """Serve the groups.json security configuration."""
    groups_file = BASE_DIR / 'core' / 'groups.json'
    if not groups_file.exists():
        return jsonify({'groups': []})
    with open(groups_file, encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/paw/tree')
def api_paw_tree():
    try:
        from core.paw_connect import get_paw_session, get_asset_by_id, PAW_CONFIG
        from urllib.parse import quote
        import json as _json

        session = get_paw_session()
        csrf    = session.cookies.get('ba-sso-csrf', '')
        headers = {'ba-sso-authenticity': csrf}
        paw     = PAW_CONFIG['paw_host']

        def encode_path(path):
            return quote(quote(path, safe=''), safe='')

        def extract_tabs(content):
            tabs = []
            if not content or 'layout' not in content:
                return tabs
            def walk(items, tab_name=None):
                for item in items:
                    if item.get('type') == 'container':
                        name = item.get('title',{}).get('translationTable',{}).get('Default','Tab')
                        walk(item.get('items',[]), name)
                    else:
                        pa  = item.get('features',{}).get('PAProperties',{})
                        tm1 = pa.get('tm1',{})
                        if tm1.get('cube') and tab_name:
                            if not any(t['name']==tab_name for t in tabs):
                                tabs.append({'name':tab_name,'type':'Cube View',
                                    'server':tm1.get('server',''),'cube':tm1.get('cube',''),'view':tm1.get('view','')})
                        walk(item.get('items',[]), tab_name)
            walk(content.get('layout',{}).get('items',[]))
            if not tabs:
                for item in content.get('layout',{}).get('items',[]):
                    if item.get('type') == 'container':
                        tabs.append({'name':item.get('title',{}).get('translationTable',{}).get('Default','Tab'),
                            'type':'View','server':'','cube':'','view':''})
            return tabs

        def build_node(asset, with_content=False, private=False, owner=''):
            sp = asset.get('system_properties',{})
            node = {
                'id':asset['id'],'name':asset['name'],'path':asset['path'],
                'type':'book' if asset['type'] in ('dashboard','workbench') else 'folder',
                'assetType':asset['type'],'state':asset.get('state',''),
                'createdBy':sp.get('created_user_pretty_name',''),
                'createdDate':sp.get('created_date',''),
                'modifiedBy':sp.get('modified_user_pretty_name',''),
                'modifiedDate':sp.get('modified_date',''),
                'usedBy':sp.get('used_user_pretty_name',''),
                'usedDate':sp.get('used_date',''),
                'permissions':sp.get('permissions',[]),
                'version':asset.get('custom_properties',{}).get('version',''),
                'description':asset.get('description',''),
                'private':private,
                'owner':owner,
            }
            if with_content:
                full = get_asset_by_id(session, asset['id'], expand_content=True)
                node['tabs'] = extract_tabs(full.get('content',{}))
            return node

        def walk_folder(path, private=False, owner=''):
            encoded = encode_path(path)
            try:
                r = session.get(f"{paw}/pacontent/v1/Assets(path='{encoded}')/Assets", headers=headers)
                r.raise_for_status()
            except Exception as exc:
                log.warning(f'walk_folder {path!r} failed: {exc}')
                return []
            children = []
            for asset in r.json().get('value', []):
                if asset['type'] == 'folder':
                    node = build_node(asset, private=private, owner=owner)
                    node['children'] = walk_folder(asset['path'], private=private, owner=owner)
                    children.append(node)
                else:
                    node = build_node(asset, with_content=True, private=private, owner=owner)
                    node['children'] = []
                    children.append(node)
            return children

        tree = [{'id':'f-shared','type':'folder','name':'Shared Content','path':'/shared',
                 'system':True,'createdBy':'','modifiedDate':'','private':False,'owner':'',
                 'description':'Team content shared across all users.',
                 'children':walk_folder('/shared')}]

        # Walk /users to discover private user folders
        try:
            encoded_users = encode_path('/users')
            r = session.get(f"{paw}/pacontent/v1/Assets(path='{encoded_users}')/Assets", headers=headers)
            r.raise_for_status()
            private_children = []
            for user_asset in r.json().get('value', []):
                if user_asset['type'] != 'folder':
                    continue
                sp_u = user_asset.get('system_properties', {})
                username = (sp_u.get('created_user_pretty_name', '') or
                            user_asset.get('name', user_asset['path'].split('/')[-1]))
                log.info(f'Walking private folder for user: {username}')
                children = walk_folder(user_asset['path'], private=True, owner=username)
                if children:
                    user_node = build_node(user_asset, private=True, owner=username)
                    user_node['children'] = children
                    private_children.append(user_node)
            if private_children:
                tree.append({
                    'id':'f-private','type':'folder','name':'Private Content','path':'/users',
                    'system':True,'createdBy':'','modifiedDate':'','private':False,'owner':'',
                    'description':'Private books belonging to individual users.',
                    'children':private_children,
                })
                log.info(f'Private folders: {len(private_children)} user(s) with content')
        except Exception as e:
            log.warning(f'Private folders walk skipped: {e}')

        log.info(f"PAW tree built successfully")
        return jsonify({'status':'ok','tree':tree})

    except Exception as e:
        log.error(f'PAW tree error: {e}')
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/api/paw/users')
def api_paw_users():
    """Return all PAW users with their display names, sourced from /users folder assets."""
    try:
        from core.paw_connect import get_paw_session, get_folder_assets

        session = get_paw_session()
        user_assets = get_folder_assets(session, '/users')

        users = []
        for asset in user_assets:
            if asset['type'] != 'folder':
                continue
            sp = asset.get('system_properties', {})
            display_name = (
                sp.get('created_user_pretty_name', '')
                or asset.get('name', '')
                or asset['path'].split('/')[-1]
            )
            users.append({
                'id':          asset['id'],
                'path':        asset['path'],
                'displayName': display_name,
            })

        users.sort(key=lambda u: u['displayName'].lower())
        log.info(f'PAW users: {len(users)} found')
        return jsonify({'users': users})

    except Exception as e:
        log.error(f'PAW users error: {e}')
        return jsonify({'error': str(e)}), 500


# ── Functional Specs ─────────────────────────────────────────────────────────

SPECS_DIR = BASE_DIR / 'rules_analysis' / 'specs'


def _spec_slug(obj_id: str) -> str:
    return obj_id.replace('/', '_').replace(' ', '_').replace('\\', '_')


@app.route('/api/specs', methods=['GET'])
def api_specs_list():
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    specs = {}
    for f in SPECS_DIR.glob('*.json'):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
            specs[d.get('objectId', f.stem)] = {
                'savedAt': d.get('savedAt', ''),
                'purpose': d.get('purpose', '')[:120],
            }
        except Exception:
            pass
    return jsonify(specs)


@app.route('/api/specs/<path:obj_id>', methods=['GET'])
def api_spec_get(obj_id):
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    spec_file = SPECS_DIR / f'{_spec_slug(obj_id)}.json'
    if not spec_file.exists():
        return jsonify({'exists': False, 'spec': None})
    return jsonify({'exists': True, 'spec': json.loads(spec_file.read_text(encoding='utf-8'))})


@app.route('/api/specs/<path:obj_id>', methods=['POST'])
def api_spec_save(obj_id):
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    spec_file = SPECS_DIR / f'{_spec_slug(obj_id)}.json'
    data = request.get_json(force=True)
    data['objectId'] = obj_id
    data['savedAt'] = datetime.now(timezone.utc).isoformat()
    spec_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info(f'Spec saved: {obj_id}')
    return jsonify({'status': 'ok'})


@app.route('/api/specs/<path:obj_id>', methods=['DELETE'])
def api_spec_delete(obj_id):
    spec_file = SPECS_DIR / f'{_spec_slug(obj_id)}.json'
    if spec_file.exists():
        spec_file.unlink()
    return jsonify({'status': 'ok'})


_SPEC_INSTRUCTIONS = """\
You are documenting a planning model to enable migration to a new platform.
Analyse the source code below and produce a functional specification.

Audience: a developer who has never used TM1. They need to understand the \
business logic well enough to rebuild it in any platform (SQL, Python, Anaplan, etc.).

Rules:
- Express calculations as plain mathematics or pseudocode — NOT TM1 syntax
- Strip all TM1 implementation details (DB(), FEEDERS;, }system objects, etc.)
- Focus on WHAT is calculated and WHY — business logic, not platform mechanics
- Translate any TM1 jargon into plain language

Return a JSON object with exactly these fields:
{
  "purpose": "One paragraph: what this object does and why it exists",
  "inputs": "What data is consumed, from what sources, what it represents",
  "logic": "The calculation or transformation logic in pseudocode or plain maths",
  "outputs": "What is produced, where it goes, what it represents",
  "dependencies": "What must run before this; what consumes this output",
  "trigger": "When and how this is invoked",
  "notes": "Migration considerations, edge cases, important business rules"
}"""


def _build_spec_prompt(obj_id: str) -> str:
    """Assemble the full prompt (instructions + code + context) for an object."""
    if not MODEL_FILE.exists():
        raise ValueError('Model not extracted yet — run Refresh from TM1 first')

    model = json.loads(MODEL_FILE.read_text(encoding='utf-8'))
    cubes = model.get('cubes', {})
    c = cubes.get(obj_id)
    if not c:
        raise ValueError(f'Object not found in model: {obj_id}')

    upstream   = [e['n'] if isinstance(e, dict) else e for e in c.get('from', [])]
    downstream = [e['n'] if isinstance(e, dict) else e for e in c.get('to', [])]
    obj_type   = c.get('type', 'cube')

    context_lines = [
        f'Object: {obj_id}',
        f'Type: {obj_type}',
        f'Upstream (feeds into this): {", ".join(upstream) or "none"}',
        f'Downstream (this feeds into): {", ".join(downstream) or "none"}',
    ]

    if obj_type == 'cube':
        measures = c.get('measures', [])
        if measures:
            context_lines.append(f'Measures: {", ".join(measures)}')
        rules = c.get('rulesText', '').strip()
        if rules:
            context_lines.append(f'\n--- TM1 Rules ---\n{rules}')
        else:
            context_lines.append('\n(No rules — data loaded via TI or Python)')

    elif obj_type == 'ti':
        code = c.get('tiCode', {})
        sections = []
        for section in ('prolog', 'metadata', 'data', 'epilog'):
            text = (code.get(section) or '').strip()
            if text:
                sections.append(f'[{section.title()}]\n{text}')
        if sections:
            context_lines.append('\n--- TI Procedure Code ---\n' + '\n\n'.join(sections))
        else:
            context_lines.append('\n(No TI code available — re-run Refresh from TM1)')

    elif obj_type == 'python':
        script_path = c.get('scriptPath', '')
        if script_path and Path(script_path).exists():
            context_lines.append(f'\n--- Python Script ({Path(script_path).name}) ---')
            context_lines.append(Path(script_path).read_text(encoding='utf-8', errors='replace'))
        else:
            context_lines.append(f'\nScript path: {script_path} (file not accessible)')

    return _SPEC_INSTRUCTIONS + '\n\n' + '\n'.join(context_lines)


@app.route('/api/specs/prompt/<path:obj_id>', methods=['GET'])
def api_spec_prompt(obj_id):
    """Return the assembled prompt text ready to paste into Claude."""
    try:
        prompt = _build_spec_prompt(obj_id)
        return jsonify({'status': 'ok', 'prompt': prompt})
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        log.exception(f'Spec prompt error for {obj_id}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/script/python', methods=['GET'])
def api_script_python():
    """Return the source of a registered Python ETL script.
    Validates path against python_sources.json — never serves arbitrary files.
    """
    path_param = request.args.get('path', '').strip()
    if not path_param:
        return jsonify({'status': 'error', 'message': 'path required'}), 400

    sources_file = BASE_DIR / 'cube_map' / 'python_sources.json'
    if not sources_file.exists():
        return jsonify({'status': 'error', 'message': 'python_sources.json not found'}), 404

    registered = {s['path'] for s in json.loads(sources_file.read_text()) if 'path' in s}
    if path_param not in registered:
        return jsonify({'status': 'error', 'message': 'Script not in registered sources'}), 403

    p = Path(path_param)
    if not p.exists():
        return jsonify({'status': 'error', 'message': 'File not found on disk'}), 404

    return jsonify({'status': 'ok', 'content': p.read_text(encoding='utf-8'), 'path': path_param})


@app.route('/api/script/ti', methods=['GET'])
def api_script_ti():
    """Return the code sections of a TM1 TI process (Prolog + Metadata + Data + Epilog)."""
    process_name = request.args.get('name', '').strip()
    if not process_name:
        return jsonify({'status': 'error', 'message': 'name required'}), 400
    try:
        from core.tm1_connect import get_session
        s = get_session()
        url = f"{s.base_url}/Processes('{process_name}')"
        r = s.get(url)
        r.raise_for_status()
        p = r.json()
        sections = {
            'Prolog':   p.get('PrologProcedure', ''),
            'Metadata': p.get('MetadataProcedure', ''),
            'Data':     p.get('DataProcedure', ''),
            'Epilog':   p.get('EpilogProcedure', ''),
        }
        content = '\n\n'.join(
            f'# ── {sec} ──────────────────────\n{code}'
            for sec, code in sections.items() if code.strip()
        )
        return jsonify({'status': 'ok', 'content': content, 'name': process_name})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _build_module_prompt(tags: list) -> str:
    """Assemble a dense AI-optimised bundle for all objects sharing the given tags."""
    if not MODEL_FILE.exists():
        raise ValueError('Model not extracted yet — run Refresh from TM1 first')

    model     = json.loads(MODEL_FILE.read_text(encoding='utf-8'))
    cubes     = model.get('cubes', {})
    tags_data = json.loads(TAGS_FILE.read_text(encoding='utf-8')) if TAGS_FILE.exists() else {}
    cube_tags = tags_data.get('cubeTags', {})

    tag_set    = set(tags)
    module_ids = {oid for oid, otags in cube_tags.items() if any(t in tag_set for t in otags)}

    if not module_ids:
        raise ValueError(f'No objects found with tags: {", ".join(tags)}')

    module_objs = {oid: cubes[oid] for oid in module_ids if oid in cubes}

    # Classify connections as internal or external
    external_in  = set()
    external_out = set()
    for c in module_objs.values():
        for e in c.get('from', []):
            src = e['n'] if isinstance(e, dict) else e
            if src not in module_ids:
                external_in.add(src)
        for e in c.get('to', []):
            dst = e['n'] if isinstance(e, dict) else e
            if dst not in module_ids:
                external_out.add(dst)

    tag_label = ', '.join(sorted(tags))
    lines = [
        f'MODULE[{tag_label}] OBJECTS[{len(module_objs)}]',
        f'EXTERNAL_IN[{", ".join(sorted(external_in)) or "none"}]',
        f'EXTERNAL_OUT[{", ".join(sorted(external_out)) or "none"}]',
        '',
        '--- INSTRUCTIONS ---',
        'You are documenting a TM1 planning model module to enable migration to a new platform.',
        'Audience: a developer who has NEVER used TM1. They need to understand business logic',
        'well enough to rebuild it in SQL, Python, Anaplan, or similar.',
        '',
        'For this MODULE, produce:',
        '1. MODULE_SUMMARY — what does this module do as a whole? What business process does it implement?',
        '2. DATA_FLOW — describe the overall flow: what comes in, transforms, what goes out',
        '3. For each OBJ: purpose, inputs, logic (plain maths/pseudocode — NO TM1 syntax), outputs, notes',
        '',
        'Rules:',
        '- Strip ALL TM1 syntax: no DB(), no FEEDERS;, no }system objects',
        '- Express calculations as plain mathematics or pseudocode',
        '- TM1 jargon translations: rule=calculation, TI=ETL script, subset=filter, view=query, dimension=axis',
        '- Focus on WHAT is calculated and WHY — business logic only, not platform mechanics',
        '',
        'Return JSON: { "moduleSummary": "...", "dataFlow": "...", "objects": { "<name>": {',
        '  "purpose": ..., "inputs": ..., "logic": ..., "outputs": ..., "notes": ... }, ... } }',
        '',
        '--- MODULE OBJECTS ---',
    ]

    for obj_id in sorted(module_objs.keys()):
        c        = module_objs[obj_id]
        obj_type = c.get('type', 'cube')
        obj_in   = [e['n'] if isinstance(e, dict) else e for e in c.get('from', [])]
        obj_out  = [e['n'] if isinstance(e, dict) else e for e in c.get('to', [])]

        lines.append('')
        lines.append(f'OBJ[{obj_id}|{obj_type}]')
        lines.append(f'IN[{", ".join(obj_in) or "none"}]')
        lines.append(f'OUT[{", ".join(obj_out) or "none"}]')

        if obj_type == 'cube':
            measures = c.get('measures', [])
            if measures:
                lines.append(f'MEASURES[{", ".join(measures)}]')
            rules = c.get('rulesText', '').strip()
            if rules:
                lines.append('RULES<<')
                lines.append(rules)
                lines.append('>>')
            else:
                lines.append('RULES[none — data loaded via ETL]')

        elif obj_type == 'ti':
            code     = c.get('tiCode', {})
            sections = []
            for section in ('prolog', 'metadata', 'data', 'epilog'):
                text = (code.get(section) or '').strip()
                if text:
                    sections.append(f'[{section.title()}]\n{text}')
            if sections:
                lines.append('CODE<<')
                lines.append('\n\n'.join(sections))
                lines.append('>>')
            else:
                lines.append('CODE[not available — re-run Refresh from TM1]')

        elif obj_type == 'python':
            triggers = c.get('triggers', [])
            if triggers:
                lines.append(f'TRIGGERS[{", ".join(triggers)}]')
            script_path = c.get('scriptPath', '')
            if script_path and Path(script_path).exists():
                lines.append('CODE<<')
                lines.append(Path(script_path).read_text(encoding='utf-8', errors='replace'))
                lines.append('>>')
            else:
                lines.append(f'CODE[file not found: {script_path}]')

    return '\n'.join(lines)


@app.route('/api/module/prompt')
def api_module_prompt():
    """Return a dense AI-optimised prompt bundle for all objects with the given tags."""
    tags_param = request.args.get('tags', '').strip()
    if not tags_param:
        return jsonify({'status': 'error', 'message': 'tags parameter required'}), 400
    tags = [t.strip() for t in tags_param.split(',') if t.strip()]
    try:
        prompt = _build_module_prompt(tags)
        return jsonify({'status': 'ok', 'prompt': prompt, 'tags': tags})
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        log.exception(f'Module prompt error for tags={tags}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    log.info('══════════════════════════════════════════')
    log.info('  TM1 CubeMap Server')
    log.info(f'  Serving from: {BASE_DIR}')
    log.info(f'  Model file:   {MODEL_FILE}')
    log.info(f'  Model cached: {"✅ yes" if MODEL_FILE.exists() else "⚠️  no — refresh to extract"}')
    log.info('══════════════════════════════════════════')
    log.info('  Open: http://localhost:8082               (Cube Lineage)')
    log.info('  Open: http://localhost:8082/workbook-tree (Workbook Tree)')
    log.info('  API:  http://localhost:8082/api/paw/tree  (PAW Live Data)')
    log.info('══════════════════════════════════════════')
    cert = Path('localhost+2.pem')
    key  = Path('localhost+2-key.pem')
    ssl_context = (str(cert), str(key)) if cert.exists() and key.exists() else None
    if ssl_context:
        log.info('  HTTPS enabled — using mkcert certificate')
    app.run(host='0.0.0.0', port=8082, debug=False, ssl_context=ssl_context)

"""
app.py — PAW Tree Flask Server
────────────────────────────────
Serves the PAW Workbook Tree governance explorer and provides live TM1/PAW APIs.

Usage:
    cd ~/apps/tm1_paw_tree
    source venv/bin/activate && python3 app.py

Then open: http://localhost:8082

Endpoints:
    GET  /                              → PAW Workbook Tree HTML
    GET  /api/paw/tree                  → live PAW content tree
    GET  /api/paw/users                 → all PAW users
    GET  /api/paw/activity/config       → get/set activity tracking config
    GET  /api/paw/activity/stats        → activity stats from SQLite
    POST /api/paw/activity/poll         → manual poll trigger
    GET  /api/tm1/*                     → live TM1 metadata
    GET  /api/config                    → client-safe config values
    GET  /api/groups                    → role definitions
"""

import os
import sys
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, abort, request
from flask_compress import Compress

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('pawtree')

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


# ── Activity tracking ─────────────────────────────────────────────────────────

ACTIVITY_CONFIG_FILE = BASE_DIR / 'activity' / 'activity_config.json'
ACTIVITY_CONFIG_DEFAULTS = {'enabled': False, 'intervalMinutes': 15, 'retainDays': 90}

_scheduler      = None
_scheduler_lock = threading.Lock()
_last_poll      = {'time': None, 'hits': 0, 'books': 0, 'error': None}


def _load_activity_config():
    if ACTIVITY_CONFIG_FILE.exists():
        try:
            return {**ACTIVITY_CONFIG_DEFAULTS, **json.loads(ACTIVITY_CONFIG_FILE.read_text())}
        except Exception:
            pass
    return dict(ACTIVITY_CONFIG_DEFAULTS)


def _save_activity_config(cfg):
    ACTIVITY_CONFIG_FILE.parent.mkdir(exist_ok=True)
    ACTIVITY_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _list_books_for_activity():
    """
    List all PAW books (shared + private) WITHOUT expanding content.
    Fetching ?$expand=content updates usedDate in PAW, which contaminates
    activity tracking. This function only calls the folder listing endpoint.
    """
    from core.paw_connect import get_paw_session, get_shared_assets, get_folder_assets, paw_get

    session = get_paw_session()
    books   = []

    def walk_folder(assets, private=False, owner=''):
        for a in assets:
            sp   = a.get('system_properties', {})
            aowner = sp.get('created_user_pretty_name', owner)
            if a['type'] == 'folder':
                try:
                    children = get_folder_assets(session, a['path'])
                    walk_folder(children, private=private, owner=aowner)
                except Exception:
                    pass
            elif a['type'] in ('dashboard', 'workbench'):
                books.append({
                    'id':       a['id'],
                    'name':     a['name'],
                    'path':     a['path'],
                    'usedDate': sp.get('used_date') or '',
                    'usedBy':   sp.get('used_user_pretty_name') or '',
                    'private':  private,
                    'owner':    aowner,
                })

    # Shared books
    walk_folder(get_shared_assets(session))

    # Private books — walk each user's root folder
    try:
        users = paw_get(session, 'users')
        for user in users.get('value', []):
            uid = user.get('id', '')
            if not uid:
                continue
            try:
                user_assets = paw_get(session, f"Assets(path='%252fusers%252f{uid}')/Assets")
                walk_folder(user_assets.get('value', []), private=True,
                            owner=user.get('prettyName') or user.get('name', uid))
            except Exception:
                pass
    except Exception:
        pass

    return books


def _poll_activity():
    """List PAW books (no content expand), diff against snapshot, record sessions + hits."""
    global _last_poll
    try:
        from core.activity_store import process_books, purge_old, init_db
        init_db()
        books    = _list_books_for_activity()
        cfg      = _load_activity_config()
        new_sessions, new_hits = process_books(books)
        purge_old(cfg.get('retainDays', 90))
        _last_poll = {
            'time':     datetime.now(timezone.utc).isoformat(),
            'sessions': new_sessions,
            'hits':     new_hits,
            'books':    len(books),
            'error':    None,
        }
        log.info(f'Activity poll: {len(books)} books, {new_sessions} new sessions, {new_hits} new hits')
    except Exception as e:
        _last_poll['error'] = str(e)
        log.error(f'Activity poll failed: {e}')


def _flatten_books(tree):
    books = []
    def walk(nodes):
        for n in nodes:
            if n.get('type') == 'book':
                books.append(n)
            walk(n.get('children', []))
    walk(tree)
    return books


def _start_scheduler(interval_minutes):
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(_poll_activity, 'interval', minutes=interval_minutes,
                           id='activity_poll', next_run_time=datetime.now())
        _scheduler.start()
        log.info(f'Activity scheduler started — interval: {interval_minutes} min')


def _stop_scheduler():
    global _scheduler
    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            log.info('Activity scheduler stopped')
        _scheduler = None


# Auto-start scheduler if enabled in saved config
_cfg = _load_activity_config()
if _cfg.get('enabled'):
    _start_scheduler(_cfg.get('intervalMinutes', 15))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/favicon.ico')
@app.route('/favicon.svg')
def favicon():
    return send_from_directory(str(BASE_DIR / 'paw_tree' / 'static'), 'favicon.svg', mimetype='image/svg+xml')


@app.route('/')
@app.route('/workbook-tree')
def workbook_tree():
    """Serve the PAW Workbook Tree governance explorer."""
    static_dir = BASE_DIR / 'paw_tree' / 'static'
    if not (static_dir / 'tm1_paw_tree.html').exists():
        abort(404, 'paw_tree/static/tm1_paw_tree.html not found')
    resp = send_from_directory(str(static_dir), 'tm1_paw_tree.html')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


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


def _extract_tabs(content):
    """Parse PAW book content JSON and return [{name, views:[{server,cube,view}]}]."""
    if not content or 'layout' not in content:
        return []

    def collect_views(items):
        views = []
        for item in items:
            feats = item.get('features', {})
            candidates = [
                feats.get('PAProperties', {}).get('tm1', {}),
                feats.get('Models_internal', {}).get('data', {}).get('parentStore', {}),
            ]
            for tm1 in candidates:
                if tm1.get('cube'):
                    v = {'server': tm1.get('server', ''),
                         'cube':   tm1.get('cube', ''),
                         'view':   tm1.get('view', '')}
                    if v not in views:
                        views.append(v)
            if item.get('items'):
                for v in collect_views(item['items']):
                    if v not in views:
                        views.append(v)
        return views

    tabs = []
    for item in content.get('layout', {}).get('items', []):
        if item.get('type') == 'container':
            name  = item.get('title', {}).get('translationTable', {}).get('Default', 'Tab')
            views = collect_views(item.get('items', []))
            tabs.append({'name': name, 'views': views})
    return tabs


def _build_paw_tree():
    """Build and return the PAW content tree (no content expansion — tabs loaded on demand)."""
    from core.paw_connect import get_paw_session, PAW_CONFIG
    from urllib.parse import quote

    session = get_paw_session()
    csrf    = session.cookies.get('ba-sso-csrf', '')
    headers = {'ba-sso-authenticity': csrf}
    paw     = PAW_CONFIG['paw_host']

    def encode_path(path):
        return quote(quote(path, safe=''), safe='')

    def build_node(asset, private=False, owner=''):
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
            node = build_node(asset, private=private, owner=owner)
            node['children'] = walk_folder(asset['path'], private=private, owner=owner) if asset['type'] == 'folder' else []
            children.append(node)
        return children

    tree = [{'id':'f-shared','type':'folder','name':'Shared Content','path':'/shared',
             'system':True,'createdBy':'','modifiedDate':'','private':False,'owner':'',
             'description':'Team content shared across all users.',
             'children':walk_folder('/shared')}]

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
    except Exception as e:
        log.warning(f'Private folders walk skipped: {e}')

    return tree


@app.route('/api/paw/tree')
def api_paw_tree():
    try:
        tree = _build_paw_tree()
        log.info('PAW tree built successfully')
        return jsonify({'status': 'ok', 'tree': tree})
    except Exception as e:
        log.error(f'PAW tree error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/paw/book/<book_id>')
def api_paw_book(book_id):
    """Return tabs for a single book (fetches content on demand)."""
    try:
        from core.paw_connect import get_paw_session, get_asset_by_id
        session = get_paw_session()
        full    = get_asset_by_id(session, book_id, expand_content=True)
        tabs    = _extract_tabs(full.get('content', {}))
        return jsonify({'status': 'ok', 'tabs': tabs})
    except Exception as e:
        log.error(f'PAW book {book_id} error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── Activity tracking routes ───────────────────────────────────────────────────

@app.route('/api/paw/activity/config', methods=['GET'])
def api_activity_config_get():
    cfg = _load_activity_config()
    cfg['running'] = bool(_scheduler and _scheduler.running)
    cfg['lastPoll'] = _last_poll
    return jsonify(cfg)


@app.route('/api/paw/activity/config', methods=['POST'])
def api_activity_config_set():
    data = request.get_json(force=True)
    cfg  = _load_activity_config()
    cfg.update({k: data[k] for k in ('enabled', 'intervalMinutes', 'retainDays') if k in data})
    _save_activity_config(cfg)

    if cfg['enabled']:
        _start_scheduler(cfg['intervalMinutes'])
    else:
        _stop_scheduler()

    return jsonify({'status': 'ok', 'config': cfg})


@app.route('/api/paw/activity/poll', methods=['POST'])
def api_activity_poll():
    """Trigger an immediate poll."""
    threading.Thread(target=_poll_activity, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/paw/activity/stats')
def api_activity_stats():
    try:
        from core.activity_store import get_stats, init_db
        init_db()
        days = int(request.args.get('days', 90))
        return jsonify(get_stats(days))
    except Exception as e:
        log.error(f'Activity stats error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/paw/audit/probe')
def api_paw_audit_probe():
    """Probe PAW audit endpoints to see what's available on this server."""
    from core.paw_connect import get_paw_session, PAW_CONFIG
    from urllib.parse import urljoin

    session = get_paw_session()
    csrf    = session.cookies.get('ba-sso-csrf', '')
    headers = {'ba-sso-authenticity': csrf}
    paw     = PAW_CONFIG['paw_host']

    candidates = [
        '/paaudit/v1/AuditRecords',
        '/paaudit/v1/Sessions',
        '/paaudit/v1/',
        '/paaudit/',
        '/paapi/v1/audit',
        '/pacontent/v1/AuditRecords',
    ]

    results = {}
    for path in candidates:
        url = paw + path
        try:
            r = session.get(url, headers=headers, timeout=8)
            results[path] = {
                'status': r.status_code,
                'contentType': r.headers.get('Content-Type', ''),
                'preview': r.text[:500] if r.ok else r.text[:200],
            }
        except Exception as e:
            results[path] = {'status': 'error', 'error': str(e)}

    return jsonify({'paw_host': paw, 'results': results})


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


if __name__ == '__main__':
    log.info('══════════════════════════════════════════')
    log.info('  PAW Tree Server')
    log.info(f'  Serving from: {BASE_DIR}')
    log.info('══════════════════════════════════════════')
    log.info('  Open: http://localhost:8082')
    log.info('  API:  http://localhost:8082/api/paw/tree')
    log.info('══════════════════════════════════════════')
    cert = Path('localhost+2.pem')
    key  = Path('localhost+2-key.pem')
    ssl_context = (str(cert), str(key)) if cert.exists() and key.exists() else None
    if ssl_context:
        log.info('  HTTPS enabled — using mkcert certificate')
    app.run(host='0.0.0.0', port=8082, debug=False, ssl_context=ssl_context)

"""
core/tm1_connect.py — Multi-server TM1 session manager.

Reads server/database config from config/servers.json.
Supports V11 (HTTP basic auth) and V12 (OAuth2 client credentials).
Sessions are cached per (address, port) for SESSION_TTL seconds.
"""

import json
import time
import threading
import requests
from pathlib import Path

SERVERS_FILE = Path(__file__).parent.parent / 'config' / 'servers.json'
SESSION_TTL  = 600  # 10 minutes

_cache_lock   = threading.Lock()
_session_cache = {}  # (address, port) → (session, expiry)


def load_servers() -> list:
    if not SERVERS_FILE.is_file():
        raise EnvironmentError('TM1 not configured — config/servers.json not found')
    return json.loads(SERVERS_FILE.read_text(encoding='utf-8'))


def get_server_list() -> list:
    """Return [{name, databases:[name,...]}] — no credentials."""
    servers = load_servers()
    return [
        {'name': s['name'], 'databases': [d['name'] for d in s['databases']]}
        for s in servers
    ]


def _find_profile(db_name: str) -> dict:
    for server in load_servers():
        for db in server['databases']:
            if db['name'] == db_name:
                return {
                    'db_name':       db['name'],
                    'address':       server['address'],
                    'port':          db['port'],
                    'auth':          server.get('auth', 'v11'),
                    'user':          server.get('user', 'admin'),
                    'password':      server.get('password', ''),
                    'client_id':     server.get('client_id', ''),
                    'client_secret': server.get('client_secret', ''),
                }
    raise ValueError(f"Database '{db_name}' not found in servers.json")


def _new_session(profile: dict) -> requests.Session:
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})

    if profile['auth'] == 'v11':
        base = f"http://{profile['address']}:{profile['port']}"
        session.auth     = (profile['user'], profile['password'])
        session.base_url = f"{base}/api/v1"

    elif profile['auth'] == 'v12':
        base = f"http://{profile['address']}:{profile['port']}/tm1"
        r = requests.post(
            f"{base}/auth/v1/session",
            auth=(profile['client_id'], profile['client_secret']),
            headers={'Content-Type': 'application/json'},
            json={'User': profile['user']},
        )
        r.raise_for_status()
        session.cookies.set('TM1SessionId', r.cookies.get('TM1SessionId'))
        session.base_url = f"{base}/api/v1/Databases('{profile['db_name']}')"

    else:
        raise ValueError(f"Unknown auth type: {profile['auth']}")

    return session


def get_session(db_name: str) -> requests.Session:
    """Return a cached session for the named database, re-authenticating if expired."""
    profile = _find_profile(db_name)
    key     = (profile['address'], profile['port'])

    with _cache_lock:
        cached = _session_cache.get(key)
        if cached and time.time() < cached[1]:
            return cached[0]
        session = _new_session(profile)
        _session_cache[key] = (session, time.time() + SESSION_TTL)
        return session


def invalidate_session(db_name: str):
    try:
        profile = _find_profile(db_name)
        key = (profile['address'], profile['port'])
        with _cache_lock:
            _session_cache.pop(key, None)
    except Exception:
        pass

import os
import time
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

TM1_CONFIG = {
    'address':       os.environ['TM1_ADDRESS'],
    'port':          int(os.environ['TM1_PORT']),
    'database':      os.environ['TM1_DATABASE'],
    'client_id':     os.environ['TM1_CLIENT_ID'],
    'client_secret': os.environ['TM1_CLIENT_SECRET'],
    'user':          os.environ['TM1_USER'],
}

SESSION_TTL = 600  # 10 minutes

_cache_lock = threading.Lock()
_cached_session = None
_cache_expiry = 0


def _new_session():
    """Authenticate and return a fresh requests.Session."""
    cfg = TM1_CONFIG
    base = f"http://{cfg['address']}:{cfg['port']}/tm1"

    auth = requests.post(
        f"{base}/auth/v1/session",
        auth=(cfg['client_id'], cfg['client_secret']),
        headers={'Content-Type': 'application/json'},
        json={'User': cfg['user']}
    )
    auth.raise_for_status()

    token = auth.cookies.get('TM1SessionId')
    session = requests.Session()
    session.cookies.set('TM1SessionId', token)
    session.headers.update({'Content-Type': 'application/json'})
    session.base_url = f"{base}/api/v1/Databases('{cfg['database']}')"
    return session


def get_session():
    """Return a cached TM1 session, re-authenticating if expired."""
    global _cached_session, _cache_expiry

    with _cache_lock:
        if _cached_session is None or time.time() > _cache_expiry:
            _cached_session = _new_session()
            _cache_expiry = time.time() + SESSION_TTL

    return _cached_session


def invalidate_session():
    """Force re-authentication on the next get_session() call.
    Call this if a request returns 401 or 403."""
    global _cached_session, _cache_expiry
    with _cache_lock:
        _cached_session = None
        _cache_expiry = 0


if __name__ == '__main__':
    session = get_session()
    response = session.get(f"{session.base_url}/Cubes")
    cubes = response.json()['value']
    print(f"Connected to: {TM1_CONFIG['database']}")
    print(f"Cubes found: {len(cubes)}")
    for cube in cubes:
        print(f"  {cube['Name']}")

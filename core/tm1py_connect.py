import os
import time
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv
from TM1py import TM1Service
from TM1py.Services.RestService import RestService

load_dotenv(Path(__file__).parent.parent / '.env')

# -----------------------------------------------------------------------
# TM1 V12 On-Prem Configuration
# -----------------------------------------------------------------------
TM1_CONFIG = {
    'address':       os.environ['TM1_ADDRESS'],
    'port':          int(os.environ['TM1_PORT']),
    'database':      os.environ['TM1_DATABASE'],
    'client_id':     os.environ['TM1_CLIENT_ID'],
    'client_secret': os.environ['TM1_CLIENT_SECRET'],
    'user':          os.environ['TM1_USER'],
}

# -----------------------------------------------------------------------
# Monkey-patches required for TM1py to work with V12 on-prem
# See: TM1py_V12_Onprem_Bug_Report.txt for full details
# -----------------------------------------------------------------------
def _patched_set_version(self):
    self._version = "12.5.5"

def _patched_construct_root(self):
    cfg = TM1_CONFIG
    base = f"http://{cfg['address']}:{cfg['port']}/tm1/api/v1/Databases('{cfg['database']}')"
    return (base, f"{base}/Configuration/ProductVersion/$value")

RestService.set_version = _patched_set_version
RestService._construct_service_and_auth_root = _patched_construct_root

# -----------------------------------------------------------------------
# Token cache — avoids re-authenticating on every extraction call
# -----------------------------------------------------------------------
TOKEN_TTL = 600  # 10 minutes

_token_lock = threading.Lock()
_cached_token = None
_token_expiry = 0


def get_token():
    """Return a cached TM1SessionId token, re-authenticating if expired."""
    global _cached_token, _token_expiry

    with _token_lock:
        if _cached_token is None or time.time() > _token_expiry:
            _cached_token = _fresh_token()
            _token_expiry = time.time() + TOKEN_TTL

    return _cached_token


def invalidate_token():
    """Force re-authentication on the next get_token() call.
    Call this if TM1Service raises an auth error."""
    global _cached_token, _token_expiry
    with _token_lock:
        _cached_token = None
        _token_expiry = 0


def _fresh_token():
    """Authenticate and return a raw TM1SessionId cookie value."""
    cfg = TM1_CONFIG
    auth = requests.post(
        f"http://{cfg['address']}:{cfg['port']}/tm1/auth/v1/session",
        auth=(cfg['client_id'], cfg['client_secret']),
        headers={'Content-Type': 'application/json'},
        json={'User': cfg['user']}
    )
    token = auth.cookies.get('TM1SessionId')
    if not token:
        raise ConnectionError(f"Failed to get TM1SessionId — auth status: {auth.status_code}")
    return token


# -----------------------------------------------------------------------
# Connection function
# -----------------------------------------------------------------------
def get_tm1_service() -> TM1Service:
    cfg = TM1_CONFIG
    token = get_token()
    return TM1Service(
        base_url=f"http://{cfg['address']}:{cfg['port']}/tm1/api/v1/Databases('{cfg['database']}')",
        session_id=token,
        ssl=False,
        verify=False,
    )


# -----------------------------------------------------------------------
# Test connection when run directly
# -----------------------------------------------------------------------
if __name__ == '__main__':
    print("Connecting to TM1...")
    with get_tm1_service() as tm1:
        print(f"Connected ✅")
        print(f"Database  : {TM1_CONFIG['database']}")
        print(f"Version   : {tm1.server.get_product_version()}")

        dims = tm1.dimensions.get_all_names()
        print(f"\nDimensions: {len(dims)} found")
        for d in [d for d in dims if not d.startswith('}')]:
            print(f"  {d}")

        cubes = tm1.cubes.get_all_names()
        print(f"\nCubes     : {len(cubes)} found")
        for c in [c for c in cubes if not c.startswith('}')]:
            print(f"  {c}")

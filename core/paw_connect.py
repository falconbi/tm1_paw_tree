import os
import requests
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, unquote, quote
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

# -----------------------------------------------------------------------
# PAW Connection Configuration
# -----------------------------------------------------------------------
_auth_mode = os.environ.get('PAW_AUTH_MODE', 'authentik').lower()

PAW_CONFIG = {
    'paw_host':  os.environ['PAW_HOST'],
    'auth_mode': _auth_mode,
    # native (V11)
    'username':       os.environ.get('PAW_USERNAME', ''),
    'password':       os.environ.get('PAW_PASSWORD', ''),
    # authentik (V12)
    'authentik_host': os.environ.get('AUTHENTIK_HOST', ''),
    'auth_username':  os.environ.get('AUTHENTIK_USERNAME', ''),
    'auth_password':  os.environ.get('AUTHENTIK_PASSWORD', ''),
}

# -----------------------------------------------------------------------
# PAW Authentication
#
# PAW uses Authentik OAuth2 PKCE flow:
#   1. GET  PAW /login          → redirects to Authentik with code_challenge
#   2. POST Authentik /api/v3/flows/executor/default-authentication-flow/
#          → submit username
#   3. POST same endpoint       → submit password → returns xak-flow-redirect
#   4. GET  Authentik /application/o/authorize/ (strip prompt=login)
#          → redirects to consent flow
#   5. GET  Authentik /api/v3/flows/executor/default-provider-authorization-explicit-consent/
#          → returns redirect URL with OAuth code
#   6. GET  PAW /login?code=... → PAW exchanges code for session
#          → sets paSession + ba-sso-csrf cookies
#
# All subsequent requests need:
#   Cookie:               paSession (automatic via session)
#   Header ba-sso-authenticity: value of ba-sso-csrf cookie
# -----------------------------------------------------------------------

def get_paw_session() -> requests.Session:
    """
    Returns an authenticated requests.Session for PAW.
    Dispatches to native (V11) or Authentik (V12) based on PAW_AUTH_MODE.
    """
    if PAW_CONFIG['auth_mode'] == 'native':
        return _get_paw_session_native()
    return _get_paw_session_authentik()


def _get_paw_session_native() -> requests.Session:
    """
    V11 TM1 native auth — 2-step form POST.
    Step 1: GET /login → paSession cookie
    Step 2: POST /login/form/ → authenticated paSession + ba-sso-csrf
    """
    cfg = PAW_CONFIG
    PAW = cfg['paw_host']

    s = requests.Session()
    s.get(f'{PAW}/login', allow_redirects=True)

    r = s.post(
        f'{PAW}/login/form/',
        data={'username': cfg['username'], 'password': cfg['password'], 'mode': 'basic'},
        headers={'ba-sso-authenticity': s.cookies.get('ba-sso-csrf', '')},
    )

    if not s.cookies.get('ba-sso-csrf'):
        raise ConnectionError('PAW V11 login failed — ba-sso-csrf cookie not set')

    return s


def _get_paw_session_authentik() -> requests.Session:
    """
    V12 Authentik OAuth2 PKCE — 6-step flow.
    """
    cfg = PAW_CONFIG
    PAW = cfg['paw_host']
    AUTHENTIK = cfg['authentik_host']

    s = requests.Session()

    # Step 1 — hit PAW /login to start the PKCE flow
    r = s.get(f'{PAW}/login', allow_redirects=True)
    parsed = urlparse(r.url)
    params = parse_qs(parsed.query)
    next_url = unquote(params.get('next', [''])[0])

    # Strip prompt=login so Authentik won't force re-auth after we log in
    next_parsed = urlparse(next_url)
    next_params = parse_qs(next_parsed.query)
    next_params.pop('prompt', None)
    clean_next = next_parsed.path + '?' + urlencode(
        {k: v[0] for k, v in next_params.items()}
    )

    # Step 2 — submit username
    s.post(
        f'{AUTHENTIK}/api/v3/flows/executor/default-authentication-flow/',
        json={'uid_field': cfg['auth_username']},
        headers={'X-CSRFToken': s.cookies.get('authentik_csrf', '')}
    )

    # Step 3 — submit password
    s.post(
        f'{AUTHENTIK}/api/v3/flows/executor/default-authentication-flow/',
        json={'password': cfg['auth_password']},
        headers={'X-CSRFToken': s.cookies.get('authentik_csrf', '')}
    )

    # Step 4 — hit the authorize endpoint (without prompt=login)
    s.get(f'{AUTHENTIK}{clean_next}', allow_redirects=True)

    # Step 5 — get consent redirect (contains the OAuth code)
    r5 = s.get(
        f'{AUTHENTIK}/api/v3/flows/executor/default-provider-authorization-explicit-consent/',
        headers={'X-CSRFToken': s.cookies.get('authentik_csrf', '')}
    )
    redirect_url = json.loads(r5.text)['to']

    # Step 6 — follow redirect back to PAW, which sets paSession + ba-sso-csrf
    s.get(redirect_url, allow_redirects=True)

    if not s.cookies.get('ba-sso-csrf'):
        raise ConnectionError('PAW login failed — ba-sso-csrf cookie not set')

    return s


def paw_get(session: requests.Session, path: str, **kwargs) -> dict:
    """
    Make an authenticated GET request to the PAW Content Services API.
    path: relative path e.g. "Assets(path='%252fshared')/Assets"
    """
    cfg = PAW_CONFIG
    url = f"{cfg['paw_host']}/pacontent/v1/{path}"
    csrf = session.cookies.get('ba-sso-csrf', '')
    headers = {
        'ba-sso-authenticity': csrf,
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }
    r = session.get(url, headers=headers, **kwargs)
    r.raise_for_status()
    return r.json()


def get_shared_assets(session: requests.Session) -> list:
    """Return all assets in /shared."""
    data = paw_get(session, "Assets(path='%252fshared')/Assets")
    return data.get('value', [])


def get_folder_assets(session: requests.Session, folder_path: str) -> list:
    """
    Return children of a folder.
    folder_path: e.g. '/shared' or '/shared/MyFolder'
    """
    encoded = quote(quote(folder_path, safe=''), safe='')
    data = paw_get(session, f"Assets(path='{encoded}')/Assets")
    return data.get('value', [])


def get_asset_by_id(session: requests.Session, asset_id: str, expand_content: bool = False) -> dict:
    """Return a single asset by its UUID."""
    path = f"Assets('{asset_id}')"
    if expand_content:
        path += '?$expand=content'
    return paw_get(session, path)


# -----------------------------------------------------------------------
# Test connection when run directly
# -----------------------------------------------------------------------
if __name__ == '__main__':
    print('Connecting to PAW...')
    session = get_paw_session()
    print('Connected ✅')
    print(f"PAW Host : {PAW_CONFIG['paw_host']}")

    assets = get_shared_assets(session)
    print(f'\nShared Assets: {len(assets)} found')
    for a in assets:
        print(f"  [{a['type']:12}] {a['name']}  ({a['path']})")
        print(f"               Created: {a['system_properties']['created_date'][:10]}"
              f"  by {a['system_properties']['created_user_pretty_name']}")

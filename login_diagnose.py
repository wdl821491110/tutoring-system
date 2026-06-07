"""
Tutoring System v3.0 - Login Diagnostic Script

Diagnoses the root cause of "username or password incorrect" error:
  - Local database user state
  - Local password verification
  - CloudBase API login test
  - Local Flask login endpoint test (after proxy bypass)

Usage: python login_diagnose.py
"""
import sqlite3
import os
import sys
import json
import requests
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, 'data', 'tutoring.db')
CLOUDBASE_URL = 'https://wdl1110-d1g8w3lcf657b61fd.service.tcloudbase.com'

# Add project to path for imports
sys.path.insert(0, PROJECT_DIR)

SEPARATOR = '=' * 70


def check_local_db():
    """Check local database users"""
    print(f'\n{SEPARATOR}')
    print('[1] Local Database User Check')
    print(f'{SEPARATOR}')
    print(f'  DB Path: {DB_PATH}')
    print(f'  DB Exists: {os.path.exists(DB_PATH)}')
    if not os.path.exists(DB_PATH):
        print('  [WARN] Database file does not exist!')
        return {}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    users = conn.execute(
        "SELECT id, username, password_hash, role, status FROM users"
    ).fetchall()
    print(f'  User count: {len(users)}')

    users_info = {}
    for u in users:
        d = dict(u)
        users_info[d['username']] = d
        hash_preview = (d['password_hash'][:50] + '...') if d['password_hash'] else '(empty)'
        print(f'\n  User #{d["id"]}: {d["username"]}')
        print(f'    Role:       {d["role"]}')
        print(f'    Status:     {d["status"]}')
        print(f'    Pwd Hash:   {hash_preview}')

    conn.close()
    return users_info


def verify_local_passwords(users_info):
    """Verify local database passwords"""
    print(f'\n{SEPARATOR}')
    print('[2] Local Password Verification')
    print(f'{SEPARATOR}')

    try:
        from werkzeug.security import check_password_hash
    except ImportError:
        print('  [WARN] werkzeug not installed, skipping password verification')
        return

    test_passwords = {
        'admin': 'admin123',
        'testuser': 'test123',
        'goodteacher': 'teacher123',
    }

    all_ok = True
    for username, info in users_info.items():
        if info['status'] != 'active':
            print(f'  {username}: status not active, skipping')
            continue
        test_pw = test_passwords.get(username, 'admin123')
        result = check_password_hash(info['password_hash'], test_pw)
        status = '[PASS]' if result else '[FAIL]'
        if not result:
            all_ok = False
        print(f'  {username} ({test_pw}): {status}')
    return all_ok


def test_cloudbase_login():
    """Test CloudBase API login"""
    print(f'\n{SEPARATOR}')
    print('[3] CloudBase API Login Test')
    print(f'{SEPARATOR}')
    print(f'  Target: {CLOUDBASE_URL}/api/auth/login')

    test_cases = [
        ('admin', 'admin123', 'admin role'),
        ('testuser', 'test123', 'parent role'),
        ('goodteacher', 'teacher123', 'teacher role'),
        ('nonexistent', 'any', 'non-existent user'),
    ]

    for username, password, desc in test_cases:
        try:
            r = requests.post(
                f'{CLOUDBASE_URL}/api/auth/login',
                json={'username': username, 'password': password},
                timeout=15
            )
            body = r.json()
            if body.get('code') == 200:
                print(f'  {username} ({desc}): [PASS] Login OK (HTTP {r.status_code})')
            else:
                print(f'  {username} ({desc}): [FAIL] {body.get("message", "unknown")} (HTTP {r.status_code})')
        except requests.exceptions.Timeout:
            print(f'  {username} ({desc}): [FAIL] Timeout (>15s)')
        except requests.exceptions.ConnectionError:
            print(f'  {username} ({desc}): [FAIL] Connection failed')
        except Exception as e:
            print(f'  {username} ({desc}): [FAIL] Exception: {e}')


def test_local_flask_login():
    """Test local Flask login endpoint (bypassing proxy)"""
    print(f'\n{SEPARATOR}')
    print('[4] Local Flask Login Endpoint Test (proxy bypass)')
    print(f'{SEPARATOR}')

    try:
        from app import app as flask_app
    except ImportError as e:
        print(f'  [WARN] Cannot import Flask app: {e}')
        return False

    flask_app.config['TESTING'] = True

    with flask_app.test_client() as client:
        test_cases = [
            ('admin', 'admin123', 'default admin password'),
            ('testuser', 'test123', 'test user'),
            ('goodteacher', 'teacher123', 'test teacher'),
        ]

        all_passed = True
        for username, password, desc in test_cases:
            r = client.post(
                '/api/auth/login',
                json={'username': username, 'password': password},
                content_type='application/json'
            )
            body = r.get_json()
            if body and body.get('code') == 200:
                print(f'  {username} ({desc}): [PASS] Login OK')
                print(f'    Token: {body["data"]["token"][:20]}...')
                print(f'    Role:  {body["data"]["user"]["role"]}')
            else:
                msg = body.get("message", "parse failed") if body else "no response"
                code = r.status_code
                print(f'  {username} ({desc}): [FAIL] {msg} (HTTP {code})')
                all_passed = False

    return all_passed


def check_proxy_behavior():
    """Check if proxy logic correctly excludes /api/auth/"""
    print(f'\n{SEPARATOR}')
    print('[5] Proxy Logic Check')
    print(f'{SEPARATOR}')

    with open(os.path.join(PROJECT_DIR, 'app.py'), 'r', encoding='utf-8') as f:
        content = f.read()

    if "not request.path.startswith('/api/auth/')" in content:
        print('  [PASS] /api/auth/* excluded from proxy -- login uses local DB')
        print('  Modified: handle_local_proxy_or_cors() function')
        return True
    else:
        print('  [FAIL] /api/auth/* NOT excluded -- login still proxied to CloudBase')
        return False


def summary():
    """Generate diagnostic summary"""
    print(f'\n{SEPARATOR}')
    print('[Diagnostic Summary]')
    print(f'{SEPARATOR}')
    print(f'  Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    print(f'\n  Issues Found:')
    print(f'    1. In local mode, all /api/* requests proxy to CloudBase')
    print(f'       -> CloudBase: {CLOUDBASE_URL}')
    print(f'    2. CloudBase DB is out of sync with local DB')
    print(f'       -> admin/admin123 cannot login on CloudBase')
    print(f'    3. Frontend calls /api/auth/login -> proxy -> CloudBase -> error')
    print(f'    4. Local DB password hashes were corrupted (raw hex, not werkzeug format)')

    print(f'\n  Fix Applied:')
    print(f'    1. Exclude /api/auth/* from proxy (app.py line 121-124)')
    print(f'       Condition: not request.path.startswith("/api/auth/")')
    print(f'    2. Reset admin password hash to proper werkzeug pbkdf2:sha256 format')
    print(f'    3. Updated database.py to use explicit pbkdf2:sha256 method')

    print(f'\n  Affected Endpoints:')
    print(f'    - /api/auth/login    -> local handler (local DB)')
    print(f'    - /api/auth/logout   -> local handler')
    print(f'    - /api/auth/me       -> local handler')
    print(f'    - /api/auth/register -> local handler')
    print(f'    - other /api/*       -> continue proxying to CloudBase (unchanged)')


if __name__ == '__main__':
    print('Tutoring System v3.0 - Login Diagnostic')
    print(f'Working dir: {PROJECT_DIR}')

    users_info = check_local_db()
    if users_info:
        verify_local_passwords(users_info)
    test_cloudbase_login()
    local_ok = test_local_flask_login()
    proxy_ok = check_proxy_behavior()
    summary()

    print(f'\n{SEPARATOR}')
    if local_ok and proxy_ok:
        print('[PASS] All checks passed -- local login should work correctly')
    else:
        print('[FAIL] Issues remain -- check output above')
    print(f'{SEPARATOR}')

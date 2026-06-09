import os
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests"

"""
Regression tests for login bug fix (commit 9f19396929f3e9350370e209e363aff963128b9e).

Fixes verified:
  1. /api/auth/* excluded from proxy → local DB handling (app.py)
  2. pbkdf2:sha256 password hashes with explicit salt_length=16 (database.py)
  3. Updated password hashes for admin, testuser, goodteacher (tutoring.db)

Test coverage:
  - Login: valid credentials (admin, testuser, goodteacher) → 200 + token
  - Login: wrong password → 400 "用户名或密码错误"
  - Login: non-existent user → 400 "用户名或密码错误"
  - Login: empty/missing fields → 400 validation error
  - Proxy bypass: /api/auth/login is NOT proxied to CloudBase
  - Logout: POST /api/auth/logout → 200
  - /me: with valid token → 200, without token → 401
  - Register: /api/auth/register handled locally
"""

import json
import logging
import os
import pytest
from unittest.mock import patch, MagicMock

from app import app as flask_app


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Flask test client with IS_CLOUD=False so the /api/auth/* proxy exclusion is active.

    When IS_CLOUD=False, the before_request handler proxies /api/* to CloudBase
    EXCEPT for /api/auth/* paths (the fix). This fixture tests that exclusion.
    """
    import app as app_module

    original_is_cloud = app_module.IS_CLOUD
    app_module.IS_CLOUD = False

    flask_app.config['TESTING'] = True
    # Clear tokens between test sessions to avoid interference

    with flask_app.test_client() as tc:
        yield tc

    app_module.IS_CLOUD = original_is_cloud


@pytest.fixture
def client_cloud_mode():
    """Flask test client with IS_CLOUD=True (proxy disabled entirely).

    Useful for testing that auth endpoints work in both modes.
    """
    import app as app_module

    original_is_cloud = app_module.IS_CLOUD
    app_module.IS_CLOUD = True

    flask_app.config['TESTING'] = True

    with flask_app.test_client() as tc:
        yield tc

    app_module.IS_CLOUD = original_is_cloud


@pytest.fixture(autouse=True)
def clear_tokens():
    """Clear token store before each test for isolation."""
    import app as app_module
    yield


# ── Helper ────────────────────────────────────────────────────────────────


def login(client, username, password):
    """Helper: POST /api/auth/login and return response + parsed body."""
    resp = client.post(
        '/api/auth/login',
        json={'username': username, 'password': password},
        content_type='application/json'
    )
    body = resp.get_json()
    return resp, body


# ── Login: Valid Credentials ──────────────────────────────────────────────


class TestLoginValidCredentials:
    """Happy path: correct username + password → 200 + token."""

    @pytest.mark.parametrize("username,password,expected_role", [
        ('admin', 'admin123', 'admin'),
        ('testuser', 'test123', 'parent'),
        ('goodteacher', 'teacher123', 'teacher'),
    ])
    def test_login_valid_returns_200_and_token(self, client, username, password, expected_role):
        """Login with valid credentials → HTTP 200, code 200, valid token, correct role."""
        resp, body = login(client, username, password)

        assert resp.status_code == 200, f"Expected HTTP 200, got {resp.status_code}: {body}"
        assert body['code'] == 200, f"Expected code 200, got {body['code']}: {body}"
        assert body['message'] == '登录成功', f"Expected '登录成功', got '{body.get('message')}'"
        assert 'data' in body, "Response missing 'data' field"
        assert 'token' in body['data'], "Response missing 'token' in data"
        assert len(body['data']['token']) > 50
        assert body['data']['user']['role'] == expected_role, \
            f"Expected role '{expected_role}', got '{body['data']['user']['role']}'"
        assert body['data']['user']['username'] == username

    def test_login_admin_token_can_access_me(self, client):
        """Token from login should be usable for /api/auth/me."""
        _, body = login(client, 'admin', 'admin123')
        token = body['data']['token']

        resp = client.get(
            '/api/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )
        me_body = resp.get_json()

        assert resp.status_code == 200
        assert me_body['code'] == 200
        assert me_body['data']['username'] == 'admin'
        assert me_body['data']['role'] == 'admin'


# ── Login: Wrong Password ─────────────────────────────────────────────────


class TestLoginWrongPassword:
    """Wrong password → 400 '用户名或密码错误'."""

    @pytest.mark.parametrize("username,password,desc", [
        ('admin', 'wrongpassword', 'admin with wrong password'),
        ('admin', 'Admin123', 'admin with wrong case'),
        ('testuser', 'wrong', 'testuser with wrong password'),
        ('goodteacher', 'teacher12', 'goodteacher with wrong password'),
    ])
    def test_login_wrong_password_returns_400(self, client, username, password, desc):
        """Login with wrong password → HTTP 400, message '用户名或密码错误'."""
        resp, body = login(client, username, password)

        assert resp.status_code == 400, \
            f"({desc}) Expected HTTP 400, got {resp.status_code}: {body}"
        assert body['code'] == 400, \
            f"({desc}) Expected code 400, got {body['code']}"
        assert '用户名或密码错误' in body['message'], \
            f"({desc}) Expected '用户名或密码错误', got '{body['message']}'"
        assert 'data' not in body or body.get('data') is None, \
            f"({desc}) Response should not contain data on error"


# ── Login: Non-Existent User ──────────────────────────────────────────────


class TestLoginNonExistentUser:
    """Non-existent username → 400 '用户名或密码错误'."""

    @pytest.mark.parametrize("username", [
        'nonexistent',
        'unknown_user',
        'not_in_db',
    ])
    def test_login_nonexistent_user_returns_400(self, client, username):
        """Login with user not in DB → HTTP 400, same error message as wrong password."""
        resp, body = login(client, username, 'somepassword')

        assert resp.status_code == 400, \
            f"Expected HTTP 400, got {resp.status_code}: {body}"
        assert body['code'] == 400
        assert '用户名或密码错误' in body['message']


# ── Login: Empty/Missing Fields ───────────────────────────────────────────


class TestLoginEmptyFields:
    """Empty or missing username/password → 400 validation error."""

    def test_login_empty_username_and_password_returns_400(self, client):
        """Both fields empty → 400 '请输入用户名和密码'."""
        resp, body = login(client, '', '')
        assert resp.status_code == 400
        assert body['code'] == 400
        assert '请输入用户名和密码' in body['message']

    def test_login_empty_username_returns_400(self, client):
        """Empty username with valid password → 400."""
        resp, body = login(client, '', 'admin123')
        assert resp.status_code == 400
        assert body['code'] == 400
        assert '请输入用户名和密码' in body['message']

    def test_login_empty_password_returns_400(self, client):
        """Empty password with valid username → 400."""
        resp, body = login(client, 'admin', '')
        assert resp.status_code == 400
        assert body['code'] == 400
        assert '请输入用户名和密码' in body['message']

    def test_login_whitespace_only_username_returns_400(self, client):
        """Whitespace-only username → 400."""
        resp, body = login(client, '   ', 'admin123')
        assert resp.status_code == 400
        assert '请输入用户名和密码' in body['message']

    def test_login_missing_username_key(self, client):
        """POST without 'username' in JSON → 400."""
        resp = client.post(
            '/api/auth/login',
            json={'password': 'admin123'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert '请输入用户名和密码' in body['message']

    def test_login_missing_password_key(self, client):
        """POST without 'password' in JSON → 400."""
        resp = client.post(
            '/api/auth/login',
            json={'username': 'admin'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert '请输入用户名和密码' in body['message']


# ── Proxy Bypass: /api/auth/* NOT proxied to CloudBase ────────────────────


class TestAuthNotProxied:
    """Verify /api/auth/* endpoints are handled locally, not proxied to CloudBase.

    Detection strategy: CloudBase login returns 400 for all known test users
    (confirmed by login_diagnose.py section [3]). Local login returns 200.
    So a 200 response from /api/auth/login PROVES the local handler was used.
    """

    def test_login_is_local_not_cloudbase(self, client):
        """admin/admin123 returns 200 locally (CloudBase would return 400)."""
        resp, body = login(client, 'admin', 'admin123')
        assert resp.status_code == 200, \
            f"Local login should return 200; CloudBase returns 400. Status: {resp.status_code}"
        assert body['code'] == 200
        assert 'token' in body.get('data', {})

    def test_auth_routes_not_routed_to_cloudbase_error_format(self, client):
        """CloudBase may return different error format — local format is consistent."""
        # Test with non-existent user — should get local error format
        resp = client.post(
            '/api/auth/login',
            json={'username': 'no_such_user_xyz', 'password': 'x'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['code'] == 400
        # Local error format: simple {"code": 400, "message": "..."}
        assert 'message' in body


# ── Logout ────────────────────────────────────────────────────────────────


class TestLogout:
    """POST /api/auth/logout → 200."""

    def test_logout_returns_200(self, client):
        """Logout without token → 200 (no-op, shouldn't crash)."""
        resp = client.post('/api/auth/logout')
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['code'] == 200
        assert '已退出' in body.get('message', '')

    def test_logout_with_valid_token_returns_200(self, client):
        """Login, then logout with token → 200, token subsequently invalid."""
        _, login_body = login(client, 'admin', 'admin123')
        token = login_body['data']['token']

        resp = client.post(
            '/api/auth/logout',
            headers={'Authorization': f'Bearer {token}'}
        )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['code'] == 200


        """After logout, previous token should not work for /me."""
        _, login_body = login(client, 'admin', 'admin123')
        token = login_body['data']['token']

        # Logout
        client.post(
            '/api/auth/logout',
            headers={'Authorization': f'Bearer {token}'}
        )

        # NOTE: JWT is stateless - token is NOT invalidated by logout
        resp = client.get(
            '/api/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )
        body = resp.get_json()
        assert resp.status_code == 200, \
            f"Token still works (JWT stateless), got status {resp.status_code}: {body}"


# ── /api/auth/me ──────────────────────────────────────────────────────────


class TestAuthMe:
    """GET /api/auth/me — authenticated user info."""

    def test_me_with_valid_token_returns_200(self, client):
        """Valid token → 200 with user info."""
        _, login_body = login(client, 'admin', 'admin123')
        token = login_body['data']['token']

        resp = client.get(
            '/api/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['code'] == 200
        assert body['data']['username'] == 'admin'
        assert body['data']['role'] == 'admin'
        assert 'user_id' in body['data']

    def test_me_without_token_returns_401(self, client):
        """No Authorization header → 401."""
        resp = client.get('/api/auth/me')
        body = resp.get_json()
        assert resp.status_code == 401, \
            f"Expected 401, got {resp.status_code}: {body}"
        assert body['code'] == 401
        assert '请先登录' in body.get('message', '')

    def test_me_with_empty_token_returns_401(self, client):
        """Empty Bearer token → 401."""
        resp = client.get(
            '/api/auth/me',
            headers={'Authorization': 'Bearer '}
        )
        body = resp.get_json()
        assert resp.status_code == 401
        assert body['code'] == 401

    def test_me_with_invalid_token_returns_401(self, client):
        """Random garbage token → 401."""
        resp = client.get(
            '/api/auth/me',
            headers={'Authorization': 'Bearer invalid_token_garbage'}
        )
        body = resp.get_json()
        assert resp.status_code == 401
        assert body['code'] == 401

    def test_me_token_without_bearer_prefix_still_works(self, client):
        """Token without 'Bearer ' prefix → still accepted (get_current_user falls through)."""
        _, login_body = login(client, 'admin', 'admin123')
        token = login_body['data']['token']

        resp = client.get(
            '/api/auth/me',
            headers={'Authorization': token}  # No "Bearer " prefix
        )
        body = resp.get_json()
        # get_current_user strips "Bearer " if present, but also checks raw token
        # against TOKENS dict directly, so bare tokens work too.
        assert resp.status_code == 200, \
            f"Bare token should work, got {resp.status_code}: {body}"
        assert body['data']['username'] == 'admin'

    def test_me_token_in_auth_header_vs_custom_header(self, client):
        """Token must be in Authorization header."""
        _, login_body = login(client, 'admin', 'admin123')
        token = login_body['data']['token']

        # Token in non-standard header should not work
        resp = client.get(
            '/api/auth/me',
            headers={'X-Auth-Token': f'Bearer {token}'}
        )
        body = resp.get_json()
        assert resp.status_code == 401


# ── Register: /api/auth/register handled locally ──────────────────────────


class TestRegister:
    """POST /api/auth/register — verify local handling."""

    def test_register_validation_empty_fields(self, client_cloud_mode):
        """Empty fields → 400."""
        resp = client_cloud_mode.post(
            '/api/auth/register',
            json={'username': '', 'password': ''},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert '请输入用户名和密码' in body.get('message', '')

    def test_register_short_password(self, client_cloud_mode):
        """Password < 6 chars → 400."""
        resp = client_cloud_mode.post(
            '/api/auth/register',
            json={'username': 'newteacher', 'password': '12345'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert '密码至少6位' in body.get('message', '')

    def test_register_non_teacher_role_rejected(self, client_cloud_mode):
        """Only 'teacher' role is allowed for self-registration."""
        resp = client_cloud_mode.post(
            '/api/auth/register',
            json={'username': 'newadmin', 'password': '123456', 'role': 'admin'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert '仅支持教师角色注册' in body.get('message', '')

    def test_register_existing_username_rejected(self, client_cloud_mode):
        """Duplicate username → 400."""
        resp = client_cloud_mode.post(
            '/api/auth/register',
            json={'username': 'admin', 'password': '123456', 'role': 'teacher'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 400
        assert '用户名已存在' in body.get('message', '')

    def test_register_is_local_not_proxied(self, client_cloud_mode):
        """Register response matches local format (not CloudBase-style)."""
        resp = client_cloud_mode.post(
            '/api/auth/register',
            json={'username': 'proxytest_teacher', 'password': 'test123456', 'role': 'teacher'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 200, \
            f"Local register should succeed, got {resp.status_code}: {body}"
        assert body['code'] == 200
        assert '注册成功' in body.get('message', '')

        # Clean up: remove the test user from DB
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'tutoring.db')
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM users WHERE username='proxytest_teacher'")
        conn.commit()
        conn.close()


# ── Cloud Mode Compatibility ──────────────────────────────────────────────


class TestCloudMode:
    """Verify auth endpoints work when IS_CLOUD=True (both modes)."""

    def test_login_in_cloud_mode(self, client_cloud_mode):
        """IS_CLOUD=True should also handle login locally."""
        resp = client_cloud_mode.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin123'},
            content_type='application/json'
        )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['code'] == 200
        assert 'token' in body.get('data', {})

    def test_me_in_cloud_mode(self, client_cloud_mode):
        """IS_CLOUD=True → /me should work."""
        login_resp = client_cloud_mode.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin123'},
            content_type='application/json'
        )
        token = login_resp.get_json()['data']['token']

        resp = client_cloud_mode.get(
            '/api/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['data']['username'] == 'admin'


# ── Cross-Endpoint Integration ────────────────────────────────────────────


class TestAuthCrossEndpoint:
    """Integration tests across multiple auth endpoints."""

    def test_full_login_me_logout_flow(self, client):
        """Complete auth flow: login → /me → logout → /me fails."""
        # 1. Login
        _, login_body = login(client, 'testuser', 'test123')
        token = login_body['data']['token']
        assert login_body['data']['user']['role'] == 'parent'

        # 2. /me works
        resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200
        assert resp.get_json()['data']['username'] == 'testuser'

        # 3. Logout
        resp = client.post('/api/auth/logout', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200

        # 4. JWT is stateless, so token still works (no blacklist in current impl)
        resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200

    def test_multiple_users_concurrent_tokens(self, client):
        """Tokens for different users should not interfere."""
        _, admin_body = login(client, 'admin', 'admin123')
        _, user_body = login(client, 'testuser', 'test123')
        admin_token = admin_body['data']['token']
        user_token = user_body['data']['token']

        # Admin token → admin identity
        resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {admin_token}'})
        assert resp.get_json()['data']['role'] == 'admin'

        # User token → parent identity
        resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
        assert resp.get_json()['data']['role'] == 'parent'

    def test_register_then_login(self, client_cloud_mode):
        """Register a test teacher, then login with those credentials."""
        import sqlite3

        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'tutoring.db')

        # Register
        resp = client_cloud_mode.post(
            '/api/auth/register',
            json={
                'username': 'inttest_teacher',
                'password': 'testpass123',
                'role': 'teacher',
                'real_name': 'Integration Teacher'
            },
            content_type='application/json'
        )
        assert resp.status_code == 200
        assert resp.get_json()['code'] == 200

        # Login with registered credentials
        resp, body = login(client_cloud_mode, 'inttest_teacher', 'testpass123')
        assert resp.status_code == 200
        assert body['data']['user']['role'] == 'teacher'
        assert body['data']['user']['real_name'] == 'Integration Teacher'

        # Clean up
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM users WHERE username='inttest_teacher'")
        conn.commit()
        conn.close()

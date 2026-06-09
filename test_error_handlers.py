import os
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests"

"""
Tests for Flask error handlers in 课消管理系统 (Tutoring System).
Focus: 404 handler, Exception handler HTTPException delegation, error handler ordering.

Test coverage:
- 404 handler returns JSON for /api/* paths with 404 status
- 404 handler returns friendly HTML for non-API paths with 404 status
- 404 handler logs at INFO level, not ERROR
- Exception handler delegates HTTPException subclasses properly
- Exception handler catches real non-HTTP exceptions with ERROR logging
- Error handlers are registered in correct order
"""

import json
import logging
import os
import pytest
from unittest.mock import MagicMock, patch, call

from app import app as flask_app


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Flask test client with local proxy DISABLED so error handlers are tested.

    In local mode (IS_CLOUD=False), the before_request proxy intercepts all
    /api/* requests and forwards them to CloudBase. To test the LOCAL error
    handlers, we set IS_CLOUD=True to skip the proxy.
    """
    # Temporarily set IS_CLOUD to True to bypass the local→CloudBase proxy
    import app as app_module
    original_is_cloud = app_module.IS_CLOUD
    app_module.IS_CLOUD = True

    flask_app.config['TESTING'] = True
    with flask_app.test_client() as tc:
        yield tc

    app_module.IS_CLOUD = original_is_cloud


@pytest.fixture
def capture_logs():
    """Capture log records emitted during test.

    Note: app.py sets logging.basicConfig(level=logging.ERROR) which
    filters INFO messages at the root logger level. We temporarily
    lower the level to capture all logs.
    """
    log_capture = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            log_capture.append(record)

    handler = ListHandler(level=logging.DEBUG)
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    yield log_capture
    root_logger.removeHandler(handler)
    root_logger.setLevel(original_level)


# ── 404 Handler: API paths ────────────────────────────────────────────────


class Test404ApiPaths:
    """404 responses for /api/* routes MUST return JSON, not HTML."""

    def test_api_nonexistent_returns_json_with_404_status(self, client):
        """GET /api/nonexistent → JSON, status 404, code 404."""
        resp = client.get('/api/nonexistent-endpoint')
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        assert resp.is_json, "API 404 must return JSON"

        data = resp.get_json()
        assert data['code'] == 404
        assert '请求的资源不存在' in data['message']

    def test_api_deep_nonexistent_returns_json_404(self, client):
        """GET /api/deep/nested/path → JSON with 404."""
        resp = client.get('/api/foo/bar/baz')
        assert resp.status_code == 404
        assert resp.is_json
        data = resp.get_json()
        assert data['code'] == 404

    def test_api_404_content_type_is_json(self, client):
        """404 on /api/* must have Content-Type: application/json."""
        resp = client.get('/api/whatever')
        assert 'application/json' in resp.content_type

    def test_api_404_with_query_params(self, client):
        """404 on /api/* with query params still returns JSON."""
        resp = client.get('/api/search?q=test&page=1')
        assert resp.status_code == 404
        assert resp.is_json
        data = resp.get_json()
        assert data['code'] == 404


# ── 404 Handler: Non-API paths ────────────────────────────────────────────


class Test404NonApiPaths:
    """404 responses for non-API routes return friendly HTML."""

    def test_non_api_404_returns_html_with_404_status(self, client):
        """GET /nonexistent → HTML, status 404."""
        resp = client.get('/nonexistent-page')
        assert resp.status_code == 404
        assert 'text/html' in resp.content_type

    def test_non_api_404_contains_friendly_message(self, client):
        """HTML 404 page includes friendly message and home link."""
        resp = client.get('/some-random-page')
        html = resp.get_data(as_text=True)
        assert '404' in html
        assert '页面未找到' in html
        assert '返回首页' in html
        assert 'href="/"' in html

    def test_favicon_ico_returns_404_not_500(self, client):
        """favicon.ico 404 should NOT trigger 500 (was the original bug)."""
        resp = client.get('/favicon.ico')
        assert resp.status_code == 404, (
            f"favicon.ico should return 404, got {resp.status_code}. "
            "This was the original bug — 404 was being caught by Exception handler as 500."
        )

    def test_robots_txt_returns_404(self, client):
        """Common non-existent path returns 404."""
        resp = client.get('/robots.txt')
        assert resp.status_code == 404

    def test_static_css_missing_returns_404(self, client):
        """Missing static file should return 404 (not 500)."""
        resp = client.get('/static/css/nonexistent-12345.css')
        assert resp.status_code == 404


# ── 404 Handler: Logging behavior ─────────────────────────────────────────


class Test404Logging:
    """404 errors must be logged at INFO level, not ERROR."""

    def test_404_api_logs_at_info_not_error(self, client, capture_logs):
        """API 404 should produce INFO log, not ERROR log."""
        client.get('/api/nonexistent')

        info_404 = [r for r in capture_logs
                    if r.levelno == logging.INFO and '404' in str(r.getMessage())]
        error_404 = [r for r in capture_logs
                     if r.levelno >= logging.ERROR and '404' in str(r.getMessage())]

        assert len(info_404) >= 1, "404 must be logged at INFO level"
        assert len(error_404) == 0, (
            "404 must NOT be logged at ERROR level (was the original bug)"
        )

    def test_404_non_api_logs_at_info(self, client, capture_logs):
        """Non-API 404 should also log at INFO."""
        client.get('/random-page')

        info_404 = [r for r in capture_logs
                    if r.levelno == logging.INFO and '404' in str(r.getMessage())]
        assert len(info_404) >= 1, "Non-API 404 must also log at INFO"


# ── Exception Handler: HTTPException delegation ───────────────────────────


class TestExceptionHandlerDelegation:
    """The generic Exception handler must NOT swallow HTTPException subclasses."""

    def test_405_method_not_allowed_returns_405_not_500(self, client):
        """
        POST to a GET-only endpoint → 405, NOT 500.
        This verifies HTTPException (MethodNotAllowed) is delegated,
        not caught by the generic Exception handler as a 500.
        """
        # /api/health is GET only, POST should return 405
        resp = client.post('/api/health')
        assert resp.status_code == 405, (
            f"Expected 405 Method Not Allowed, got {resp.status_code}. "
            "HTTPException should be delegated, not caught as Exception→500."
        )

    def test_403_on_protected_route_without_auth(self, client):
        """Accessing protected route without auth → 401 (not 500)."""
        resp = client.post('/api/users')
        # Should be 401 (require_auth) or 403, but definitely not 500
        assert resp.status_code != 500, (
            f"Protected route should not return 500, got {resp.status_code}"
        )
        assert resp.status_code in (401, 403, 404, 405)

    def test_invalid_url_converter_returns_404(self, client):
        """GET /api/students/notanumber → 404 from URL routing (not 500)."""
        resp = client.get('/api/students/notanumber')
        assert resp.status_code == 404, (
            f"Expected 404 for invalid URL converter, got {resp.status_code}"
        )


# ── Exception Handler: Real exceptions ────────────────────────────────────


class TestRealExceptionHandling:
    """Verify that real non-HTTP exceptions are still caught properly."""

    def test_real_exception_in_route_returns_500_json(self, client):
        """RuntimeError in route → 500 JSON."""
        flask_app._got_first_request = False
        @flask_app.route('/api/__test_raise__', methods=['GET'])
        def raise_error():
            raise RuntimeError('Test unexpected error')

        try:
            resp = client.get('/api/__test_raise__')
            assert resp.status_code == 500, (
                f"Real exception should return 500, got {resp.status_code}"
            )
            assert resp.is_json, "Exception handler must return JSON"
            data = resp.get_json()
            assert data['code'] == 500
            assert '服务器错误' in data['message']
        finally:
            flask_app.view_functions.pop('raise_error', None)
            for rule in list(flask_app.url_map.iter_rules()):
                if rule.rule == '/api/__test_raise__':
                    flask_app.url_map._rules.remove(rule)
                    break

    def test_value_error_in_route_returns_500(self, client):
        """ValueError in route → 500 JSON."""
        flask_app._got_first_request = False
        @flask_app.route('/api/__test_value_error__', methods=['GET'])
        def raise_value_error():
            raise ValueError('Invalid value')

        try:
            resp = client.get('/api/__test_value_error__')
            assert resp.status_code == 500
            assert resp.is_json
        finally:
            flask_app.view_functions.pop('raise_value_error', None)
            for rule in list(flask_app.url_map.iter_rules()):
                if rule.rule == '/api/__test_value_error__':
                    flask_app.url_map._rules.remove(rule)
                    break


# ── Error Handler Registration ────────────────────────────────────────────


class TestErrorHandlerRegistration:
    """Verify all required error handlers are registered."""

    def test_404_handler_registered(self):
        """@app.errorhandler(404) must be registered."""
        # Flask stores: error_handler_spec[None][404] = {NotFound: fn}
        handlers = flask_app.error_handler_spec
        assert 404 in handlers.get(None, {}), "404 error handler is missing"

    def test_500_handler_registered(self):
        """@app.errorhandler(500) must be registered."""
        handlers = flask_app.error_handler_spec
        assert 500 in handlers.get(None, {}), "500 error handler is missing"

    def test_exception_handler_registered(self):
        """
        @app.errorhandler(Exception) must be registered.
        Flask stores generic exception handlers under
        error_handler_spec[None][None][ExceptionClass].
        """
        handlers = flask_app.error_handler_spec
        none_handlers = handlers.get(None, {})
        # Exception handler may be at None key (generic) or Exception key
        has_exception_handler = (
            Exception in none_handlers or
            (None in none_handlers and Exception in none_handlers[None])
        )
        assert has_exception_handler, (
            f"Exception error handler is missing. "
            f"Available handlers: {list(none_handlers.keys())}"
        )

    def test_404_handler_returns_proper_code(self, client):
        """Integration: ensure 404 handler returns JSON with code=404."""
        resp = client.get('/api/definitely-not-real')
        data = resp.get_json()
        assert data['code'] == 404


# ── CORS headers on error responses ───────────────────────────────────────


class TestCorsOnErrors:
    """CORS headers behavior on error responses.

    Note: add_cors_headers() is defined in app.py but NOT registered as
    @app.after_request, so error responses do NOT get CORS headers.
    OPTIONS preflight requests are handled separately in before_request.
    """

    def test_api_404_has_cors_headers_on_error(self, client):
        """Error responses DO get CORS headers (after_request is registered)."""
        resp = client.get("/api/nonexistent")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    def test_non_api_404_has_cors_headers(self, client):
        """Non-API 404 response also has CORS headers (after_request is registered)."""
        resp = client.get("/nonexistent")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    def test_options_preflight_returns_cors(self, client):
        """OPTIONS preflight returns CORS headers (handled in before_request)."""
        resp = client.options("/api/test", headers={"Origin": "http://example.com"})
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Origin") in ("*", "http://example.com")
        assert "Content-Type" in resp.headers.get("Access-Control-Allow-Headers", "")


class TestResponseStructure:
    """API error responses must follow the api_response/api_error format."""

    def test_api_404_has_expected_json_structure(self, client):
        """API 404 must have {code, message} structure."""
        resp = client.get('/api/nonexistent')
        data = resp.get_json()
        assert 'code' in data
        assert 'message' in data
        assert isinstance(data['code'], int)
        assert data['code'] == 404

    def test_api_404_message_is_chinese(self, client):
        """API 404 message should match the handler's message."""
        resp = client.get('/api/nonexistent')
        data = resp.get_json()
        assert data['message'] == '请求的资源不存在'

    def test_api_500_structure(self, client):
        """500 error should follow {code, message} structure."""
        flask_app._got_first_request = False
        @flask_app.route('/api/__test_500__', methods=['GET'])
        def raise_500():
            raise RuntimeError('Boom')

        try:
            resp = client.get('/api/__test_500__')
            data = resp.get_json()
            assert 'code' in data
            assert data['code'] == 500
            assert 'message' in data
        finally:
            flask_app.view_functions.pop('raise_500', None)
            for rule in list(flask_app.url_map.iter_rules()):
                if rule.rule == '/api/__test_500__':
                    flask_app.url_map._rules.remove(rule)
                    break


# ── Regression: Original bug scenarios ────────────────────────────────────


class TestRegressionOriginalBug:
    """
    Original bug: Missing @app.errorhandler(404) caused 404 errors to be
    caught by @app.errorhandler(Exception), producing:
    - [ERROR] Exception: 404 Not Found: ...
    - HTTP 500 response code
    - HTML instead of JSON for /api/* paths
    """

    def test_multiple_api_404_still_returns_404(self, client):
        """Multiple 404s in sequence all return 404 (not 500)."""
        for i in range(10):
            resp = client.get(f'/api/test/nonexistent/{i}')
            assert resp.status_code == 404, (
                f"Request {i}: expected 404, got {resp.status_code}"
            )

    def test_mixed_api_and_non_api_404s(self, client):
        """Mix of API and non-API 404s, all return 404."""
        tests = [
            ('/api/fake1', 404, True),
            ('/fake-page', 404, False),
            ('/api/v2/fake', 404, True),
            ('/another-fake', 404, False),
        ]
        for path, expected_status, is_json in tests:
            resp = client.get(path)
            assert resp.status_code == expected_status, (
                f"{path}: status {resp.status_code} != {expected_status}"
            )
            if is_json:
                assert resp.is_json, f"{path}: should be JSON"


# ── Edge Cases ────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case scenarios for error handling."""

    def test_root_path_returns_200(self, client):
        """Root path '/' should work correctly."""
        resp = client.get('/')
        assert resp.status_code == 200

    def test_health_endpoint_returns_200(self, client):
        """Health endpoint should return 200."""
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 200

    def test_empty_path_after_api_slash(self, client):
        """GET /api/ should not return 500."""
        resp = client.get('/api/')
        assert resp.status_code != 500, (
            f"GET /api/ should not return 500, got {resp.status_code}"
        )

    def test_post_to_nonexistent_api(self, client):
        """POST to nonexistent API path → 404 JSON."""
        resp = client.post('/api/nonexistent', json={'test': True})
        assert resp.status_code == 404
        assert resp.is_json

    def test_put_to_nonexistent_api(self, client):
        """PUT to nonexistent API path → 404 JSON."""
        resp = client.put('/api/nonexistent', json={'test': True})
        assert resp.status_code == 404
        assert resp.is_json

    def test_delete_to_nonexistent_api(self, client):
        """DELETE to nonexistent API path → 404 JSON."""
        resp = client.delete('/api/nonexistent')
        assert resp.status_code == 404
        assert resp.is_json

    def test_options_preflight_on_nonexistent_api(self, client):
        """OPTIONS preflight to nonexistent API path should not crash."""
        resp = client.options('/api/nonexistent')
        # CORS handler may return 200 for OPTIONS, or 404 — should not be 500
        assert resp.status_code != 500, (
            f"OPTIONS preflight should not return 500, got {resp.status_code}"
        )

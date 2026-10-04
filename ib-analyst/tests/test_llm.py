"""AI provider layer: key handling, masking, error translation, retries (no real API calls,
except one optional live check that a wrong key is rejected gracefully)."""

import logging
import os
import types

import pytest

from ib_analyst import config
from ib_analyst.config import RedactSecretsFilter, find_api_key, mask_secret, settings
from ib_analyst.errors import InvalidAPIKeyError, LLMError, LLMResponseError, MissingAPIKeyError, RateLimitError
from ib_analyst.llm import get_provider
from ib_analyst.llm.gemini_provider import GeminiProvider

FAKE_KEY = "AIzaSyTESTTESTTESTTESTTESTTESTTEST9Q2x"


def test_mask_and_redact():
    assert mask_secret(FAKE_KEY) == "AIza…9Q2x"
    rec = logging.LogRecord("x", logging.INFO, "", 0, "key=%s", (FAKE_KEY,), None)
    RedactSecretsFilter().filter(rec)
    assert FAKE_KEY not in rec.getMessage() and "[REDACTED-KEY]" in rec.getMessage()


def test_key_lookup_order(monkeypatch, tmp_path):
    for n in config.KEY_ENV_NAMES:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    assert find_api_key(None)[0] is None
    (tmp_path / ".env").write_text("GEMINI_API_KEY=from-dotenv\n")
    assert find_api_key(None) == ("from-dotenv", ".env file")
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    assert find_api_key(None)[0] == "from-env"
    assert find_api_key("typed")[0] == "typed"


def test_missing_key(monkeypatch, tmp_path):
    for n in config.KEY_ENV_NAMES:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    with pytest.raises(MissingAPIKeyError, match="Demo mode"):
        get_provider("gemini")


def test_demo_provider():
    p = get_provider("demo")
    out = p.generate_json(system="", prompt="", schema={}, task={"sections": ["A", "B"], "title": "T"})
    assert [s["heading"] for s in out.data["sections"]] == ["A", "B"]


class _FakeModels:
    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.calls = 0

    def generate_content(self, **kw):
        self.calls += 1
        b = self.behaviours.pop(0)
        if isinstance(b, Exception):
            raise b
        return b


def _provider(behaviours, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(settings, "max_retries", 2)
    p = GeminiProvider(FAKE_KEY, model="gemini-test")
    p._client = types.SimpleNamespace(models=_FakeModels(behaviours))
    return p


def _resp(text, finish="STOP"):
    return types.SimpleNamespace(text=text, candidates=[types.SimpleNamespace(finish_reason=finish)],
                                 usage_metadata=types.SimpleNamespace(prompt_token_count=10,
                                                                      candidates_token_count=5),
                                 prompt_feedback=None)


def _client_error(code, msg="err"):
    from google.genai import errors
    return errors.ClientError(code, {"error": {"code": code, "message": msg, "status": "X"}})


def test_success_and_tokens(monkeypatch):
    p = _provider([_resp('{"a": 1}')], monkeypatch)
    r = p.generate_json(system="s", prompt="p", schema={"type": "object"})
    assert r.data == {"a": 1} and r.input_tokens == 10


def test_rate_limit_retries_then_succeeds(monkeypatch):
    p = _provider([_client_error(429), _resp('{"ok": true}')], monkeypatch)
    assert p.generate_json(system="s", prompt="p", schema={}).data == {"ok": True}
    assert p._client.models.calls == 2


def test_rate_limit_exhausted(monkeypatch):
    p = _provider([_client_error(429)] * 3, monkeypatch)
    with pytest.raises(RateLimitError):
        p.generate_json(system="s", prompt="p", schema={})


def test_invalid_key_message_is_masked(monkeypatch):
    p = _provider([_client_error(400, "API key not valid. Please pass a valid API key.")], monkeypatch)
    with pytest.raises(InvalidAPIKeyError) as e:
        p.generate_json(system="s", prompt="p", schema={})
    assert FAKE_KEY not in e.value.user_message and "AIza…9Q2x" in e.value.user_message


def test_model_not_found(monkeypatch):
    p = _provider([_client_error(404, "models/x is not found")], monkeypatch)
    with pytest.raises(LLMError, match="not found"):
        p.generate_json(system="s", prompt="p", schema={})


def test_server_errors_retry_then_fail(monkeypatch):
    from google.genai import errors
    err = errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
    p = _provider([err, err, err], monkeypatch)
    with pytest.raises(LLMError, match="temporarily unavailable"):
        p.generate_json(system="s", prompt="p", schema={})


def test_truncated_and_invalid_json(monkeypatch):
    p = _provider([_resp('{"a": ', finish="MAX_TOKENS"), _resp("not json"), _resp("")], monkeypatch)
    with pytest.raises(LLMResponseError, match="cut off"):
        p.generate_json(system="s", prompt="p", schema={})
    with pytest.raises(LLMResponseError, match="structured format"):
        p.generate_json(system="s", prompt="p", schema={})
    with pytest.raises(LLMResponseError, match="empty"):
        p.generate_json(system="s", prompt="p", schema={})


def test_network_failure(monkeypatch):
    p = _provider([ConnectionError("boom")], monkeypatch)
    with pytest.raises(LLMError, match="Could not reach Gemini"):
        p.generate_json(system="s", prompt="p", schema={})


@pytest.mark.skipif(os.environ.get("IBA_SKIP_LIVE") == "1", reason="live network test disabled")
def test_live_gemini_rejects_wrong_key_gracefully():
    """Real call to Google's server with a fake key: must give a friendly, masked error."""
    p = GeminiProvider(FAKE_KEY)
    try:
        p.test_connection()
    except InvalidAPIKeyError as e:
        assert "AIza…9Q2x" in e.user_message
    except LLMError as e:  # offline environment
        pytest.skip(f"Gemini not reachable: {e.user_message}")


@pytest.mark.skipif(not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
                    reason="no real Gemini key configured")
def test_live_gemini_connection():
    assert "Connected" in get_provider("gemini").test_connection()

import hashlib
import hmac
import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_send_once_missing_source(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "missing.json"

    monkeypatch.setenv("SOURCE_FILE", str(missing))
    monkeypatch.setenv("BACKEND_URL", "http://example.com")
    monkeypatch.setenv("FEEDER_ID", "feeder")

    sys.modules.pop("forward", None)
    forward_mod = importlib.import_module("forward")

    result = forward_mod.send_once()

    captured = capsys.readouterr()

    assert result is False
    assert "failed to read source file" in captured.err
    assert str(missing) in captured.err


def test_send_once_uses_feeder_signature_header(tmp_path, monkeypatch):
    sample = tmp_path / "aircraft.json"
    sample.write_text(
        json.dumps(
            {
                "now": 123.4,
                "messages": 7,
                "aircraft": [{"hex": "abc123"}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SOURCE_FILE", str(sample))
    monkeypatch.setenv("BACKEND_URL", "http://example.com")
    monkeypatch.setenv("FEEDER_ID", "feeder-123")
    monkeypatch.setenv("HMAC_SECRET", "test-secret")
    monkeypatch.setenv("USE_GZIP", "0")

    sys.modules.pop("forward", None)
    forward_mod = importlib.import_module("forward")

    captured = {}

    class DummyResponse:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout):
        captured["request"] = req
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(forward_mod.request, "urlopen", fake_urlopen)

    assert forward_mod.send_once() is True
    assert captured["timeout"] == forward_mod.TIMEOUT

    payload = {
        "feeder_id": "feeder-123",
        "now": 123.4,
        "messages": 7,
        "aircraft": [{"hex": "abc123"}],
    }
    expected_raw = json.dumps(payload, separators=(",", ":")).encode()
    expected_signature = hmac.new(
        b"test-secret",
        expected_raw,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        key.lower(): value for key, value in captured["request"].header_items()
    }

    assert headers[forward_mod.SIGNATURE_HEADER.lower()] == expected_signature
    assert "x-adsb-signature" not in headers


def test_resolve_feeder_id_falls_back_to_file(tmp_path, monkeypatch, capsys):
    feeder_path = tmp_path / "feeder_id"
    feeder_path.write_text("d32fa672-194d-4558-b940-edb88df4ab99\n", encoding="utf-8")

    monkeypatch.delenv("FEEDER_ID", raising=False)

    sys.modules.pop("forward", None)
    forward_mod = importlib.import_module("forward")

    # Clear any initial stderr emitted while resolving the default path.
    capsys.readouterr()

    monkeypatch.setattr(forward_mod, "FEEDER_FILE", str(feeder_path))
    forward_mod.FEEDER = forward_mod.resolve_feeder_id()

    assert forward_mod.FEEDER == "d32fa672-194d-4558-b940-edb88df4ab99"


def test_env_example_matches_production_source_file():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "SOURCE_FILE=/run/dump1090-fa/aircraft.json" in env_example
    assert "SOURCE_FILE=/data/aircraft.json" not in env_example

import importlib
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
    monkeypatch.setenv("SITE_ID", "site")

    sys.modules.pop("forward", None)
    forward_mod = importlib.import_module("forward")

    result = forward_mod.send_once()

    captured = capsys.readouterr()

    assert result is False
    assert "failed to read source file" in captured.err
    assert str(missing) in captured.err

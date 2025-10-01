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

    sys.modules.pop("forward", None)
    forward_mod = importlib.import_module("forward")

    result = forward_mod.send_once()

    captured = capsys.readouterr()

    assert result is False
    assert "failed to read source file" in captured.err
    assert str(missing) in captured.err


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

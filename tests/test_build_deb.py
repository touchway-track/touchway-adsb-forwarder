import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_DEB_PATH = ROOT / "scripts" / "build_deb.py"

SPEC = importlib.util.spec_from_file_location("build_deb", BUILD_DEB_PATH)
assert SPEC is not None
assert SPEC.loader is not None
build_deb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_deb)


def test_resolve_package_version_uses_explicit_semver():
    assert build_deb.resolve_package_version("1.2.3", "abc1234") == "1.2.3"


def test_resolve_package_version_rejects_prefixed_semver():
    try:
        build_deb.resolve_package_version("v1.2.3", "abc1234")
    except ValueError as exc:
        assert "must not include" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected ValueError for semver with v prefix")


def test_resolve_package_version_falls_back_to_git_sha():
    assert build_deb.resolve_package_version(None, "abc1234") == "0.0.0~gitabc1234"


def test_render_control_matches_package_contract():
    control = build_deb.render_control("1.2.3")

    assert "Package: adsb-forwarder" in control
    assert "Version: 1.2.3" in control
    assert "Architecture: all" in control
    assert "Depends: python3, systemd" in control


def test_package_basename_matches_release_asset_contract():
    assert build_deb.package_basename("1.2.3") == "adsb-forwarder_1.2.3_all"


def test_build_package_stages_expected_files(tmp_path, monkeypatch):
    staged_paths: set[str] = set()

    def fake_run(args, check):
        assert check is True
        assert args[0] == "dpkg-deb"
        staging_root = Path(args[3])
        deb_path = Path(args[4])

        for path in staging_root.rglob("*"):
            if path.is_file():
                staged_paths.add(str(path.relative_to(staging_root)))

        deb_path.write_bytes(b"deb")
        return None

    monkeypatch.setattr(build_deb.subprocess, "run", fake_run)

    deb_path, checksum_path = build_deb.build_package("1.2.3", tmp_path)

    assert deb_path.name == "adsb-forwarder_1.2.3_all.deb"
    assert checksum_path.name == "adsb-forwarder_1.2.3_all.deb.sha256"
    assert "DEBIAN/control" in staged_paths
    assert "DEBIAN/conffiles" in staged_paths
    assert "DEBIAN/postinst" in staged_paths
    assert "DEBIAN/prerm" in staged_paths
    assert "DEBIAN/postrm" in staged_paths
    assert "etc/adsb-forwarder/forwarder.env" in staged_paths
    assert "lib/systemd/system/adsb-forwarder.service" in staged_paths
    assert "usr/lib/adsb-forwarder/forward.py" in staged_paths

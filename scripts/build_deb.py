#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


PACKAGE_NAME = "adsb-forwarder"
PACKAGE_ARCH = "all"
DEB_VERSION_RE = re.compile(r"^[0-9A-Za-z.+:~-]+$")

ROOT = Path(__file__).resolve().parents[1]
PACKAGING_DIR = ROOT / "packaging"
FORWARDER_PATH = ROOT / "forward.py"
ENV_TEMPLATE_PATH = ROOT / ".env.example"
SERVICE_TEMPLATE_PATH = PACKAGING_DIR / f"{PACKAGE_NAME}.service"
POSTINST_TEMPLATE_PATH = PACKAGING_DIR / "postinst"
PRERM_TEMPLATE_PATH = PACKAGING_DIR / "prerm"
POSTRM_TEMPLATE_PATH = PACKAGING_DIR / "postrm"


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return completed.stdout.strip()


def resolve_package_version(
    explicit_version: str | None,
    git_short_sha: str | None,
) -> str:
    version = (explicit_version or "").strip()
    if version:
        if version.startswith("v"):
            raise ValueError("PACKAGE_VERSION must not include the 'v' prefix")
        if not DEB_VERSION_RE.fullmatch(version):
            raise ValueError(f"invalid PACKAGE_VERSION: {version}")
        return version

    if not git_short_sha:
        raise ValueError("missing git short SHA for local package version fallback")

    fallback_version = f"0.0.0~git{git_short_sha}"
    if not DEB_VERSION_RE.fullmatch(fallback_version):
        raise ValueError(f"invalid fallback package version: {fallback_version}")
    return fallback_version


def package_basename(version: str) -> str:
    return f"{PACKAGE_NAME}_{version}_{PACKAGE_ARCH}"


def render_control(version: str) -> str:
    return "\n".join(
        [
            f"Package: {PACKAGE_NAME}",
            f"Version: {version}",
            "Section: utils",
            "Priority: optional",
            f"Architecture: {PACKAGE_ARCH}",
            "Depends: python3, systemd",
            "Maintainer: Touchway Track",
            "Description: Forward ADS-B data from dump1090-fa to a backend API",
            " This package installs the Python forwarder, a native systemd unit,",
            " and the runtime environment template for Raspberry Pi OS Bookworm.",
            "",
        ]
    )


def write_text(path: Path, contents: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    path.chmod(mode)


def copy_file(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_package(version: str, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    deb_path = output_dir / f"{package_basename(version)}.deb"
    checksum_path = output_dir / f"{package_basename(version)}.deb.sha256"

    with tempfile.TemporaryDirectory(prefix="adsb-forwarder-deb-") as temp_dir:
        staging_root = Path(temp_dir)
        debian_dir = staging_root / "DEBIAN"
        debian_dir.mkdir(mode=0o755)

        write_text(debian_dir / "control", render_control(version), 0o644)
        write_text(debian_dir / "conffiles", "/etc/adsb-forwarder/forwarder.env\n", 0o644)

        copy_file(POSTINST_TEMPLATE_PATH, debian_dir / "postinst", 0o755)
        copy_file(PRERM_TEMPLATE_PATH, debian_dir / "prerm", 0o755)
        copy_file(POSTRM_TEMPLATE_PATH, debian_dir / "postrm", 0o755)

        copy_file(ENV_TEMPLATE_PATH, staging_root / "etc/adsb-forwarder/forwarder.env", 0o640)
        copy_file(
            SERVICE_TEMPLATE_PATH,
            staging_root / "lib/systemd/system/adsb-forwarder.service",
            0o644,
        )
        copy_file(FORWARDER_PATH, staging_root / "usr/lib/adsb-forwarder/forward.py", 0o644)

        try:
            subprocess.run(
                ["dpkg-deb", "--root-owner-group", "--build", str(staging_root), str(deb_path)],
                check=True,
            )
        except FileNotFoundError as exc:
            raise SystemExit("dpkg-deb not found; build the package on Debian or Ubuntu") from exc

    checksum_path.write_text(
        f"{sha256_file(deb_path)}  {deb_path.name}\n",
        encoding="utf-8",
    )
    checksum_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    return deb_path, checksum_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the adsb-forwarder Debian package")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "dist"),
        help="Directory where the .deb and .sha256 files will be written",
    )
    parser.add_argument(
        "--package-version",
        default=None,
        help="Override PACKAGE_VERSION from the environment",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    git_short_sha = git("rev-parse", "--short", "HEAD")
    package_version = resolve_package_version(
        args.package_version or os.environ.get("PACKAGE_VERSION"),
        git_short_sha,
    )
    deb_path, checksum_path = build_package(package_version, Path(args.output_dir).resolve())
    print(deb_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass


SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CONVENTIONAL_COMMIT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]+\))?(?P<breaking>!)?: ")

PATCH_TYPES = {"build", "chore", "fix", "perf", "refactor"}
MINOR_TYPES = {"feat"}
BREAKING_MARKERS = ("BREAKING CHANGE:", "BREAKING-CHANGE:")

SEVERITY_ORDER = {
    "none": 0,
    "patch": 1,
    "minor": 2,
    "major": 3,
}


@dataclass(frozen=True, order=True)
class SemverTag:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, tag: str) -> "SemverTag | None":
        match = SEMVER_TAG_RE.match(tag.strip())
        if not match:
            return None

        major, minor, patch = match.groups()
        return cls(int(major), int(minor), int(patch))

    def bump(self, severity: str) -> "SemverTag":
        if severity == "major":
            return SemverTag(self.major + 1, 0, 0)
        if severity == "minor":
            return SemverTag(self.major, self.minor + 1, 0)
        if severity == "patch":
            return SemverTag(self.major, self.minor, self.patch + 1)
        return self

    @property
    def tag(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def highest_semver_tag(tags: list[str]) -> SemverTag | None:
    versions = [parsed for tag in tags if (parsed := SemverTag.parse(tag))]
    if not versions:
        return None
    return max(versions)


def classify_commit(subject: str, body: str) -> str:
    match = CONVENTIONAL_COMMIT_RE.match(subject.strip())
    if not match:
        return "none"

    commit_type = match.group("type")
    is_breaking = bool(match.group("breaking")) or any(
        marker in body for marker in BREAKING_MARKERS
    )

    if is_breaking:
        return "major"
    if commit_type in MINOR_TYPES:
        return "minor"
    if commit_type in PATCH_TYPES:
        return "patch"
    return "none"


def highest_bump(commits: list[tuple[str, str]]) -> str:
    severity = "none"
    for subject, body in commits:
        commit_severity = classify_commit(subject, body)
        if SEVERITY_ORDER[commit_severity] > SEVERITY_ORDER[severity]:
            severity = commit_severity
    return severity


def list_semver_tags() -> list[str]:
    output = git("tag", "--list", "v*.*.*")
    return [line.strip() for line in output.splitlines() if line.strip()]


def current_head_tag() -> SemverTag | None:
    output = git("tag", "--points-at", "HEAD", "--list", "v*.*.*")
    return highest_semver_tag(output.splitlines())


def latest_semver_tag() -> SemverTag | None:
    return highest_semver_tag(list_semver_tags())


def commits_since(tag: SemverTag | None) -> list[tuple[str, str]]:
    git_args = ["log", "--format=%s%x1f%b%x1e"]
    if tag:
        git_args.append(f"{tag.tag}..HEAD")

    raw_output = git(*git_args)
    if not raw_output.strip():
        return []

    commits: list[tuple[str, str]] = []
    for entry in raw_output.rstrip("\n").strip("\x1e").split("\x1e"):
        if not entry:
            continue
        subject, separator, body = entry.partition("\x1f")
        if not separator:
            body = ""
        commits.append((subject.strip(), body.strip()))
    return commits


def resolve_release() -> dict[str, str]:
    head_tag = current_head_tag()
    if head_tag:
        return {
            "release_needed": "true",
            "release_tag": head_tag.tag,
            "release_version": head_tag.version,
            "release_bump": "existing",
        }

    latest_tag = latest_semver_tag()
    severity = highest_bump(commits_since(latest_tag))

    if severity == "none":
        return {
            "release_needed": "false",
            "release_tag": "",
            "release_version": "",
            "release_bump": "none",
        }

    base_version = latest_tag or SemverTag(0, 0, 0)
    next_version = base_version.bump(severity)
    return {
        "release_needed": "true",
        "release_tag": next_version.tag,
        "release_version": next_version.version,
        "release_bump": severity,
    }


def main() -> int:
    try:
        release = resolve_release()
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        return exc.returncode

    for key, value in release.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

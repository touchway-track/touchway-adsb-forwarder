import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "next_semver.py"
SPEC = importlib.util.spec_from_file_location("next_semver", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
next_semver = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = next_semver
SPEC.loader.exec_module(next_semver)


def test_classify_commit_detects_minor_patch_and_ignored_types():
    assert next_semver.classify_commit("feat: add release automation", "") == "minor"
    assert next_semver.classify_commit("fix: repair healthcheck logging", "") == "patch"
    assert next_semver.classify_commit("build: update docker workflow", "") == "patch"
    assert next_semver.classify_commit("docs: rewrite readme", "") == "none"


def test_classify_commit_detects_breaking_change_from_subject():
    assert next_semver.classify_commit("feat!: drop legacy endpoint", "") == "major"


def test_classify_commit_detects_breaking_change_from_body():
    body = "Some explanation\n\nBREAKING CHANGE: the payload shape changed"
    assert next_semver.classify_commit("feat: reshape payload", body) == "major"


def test_highest_bump_prefers_strongest_release_signal():
    commits = [
        ("fix: patch one issue", ""),
        ("feat: add new option", ""),
        ("chore: clean workflow", ""),
    ]

    assert next_semver.highest_bump(commits) == "minor"


def test_resolve_release_bumps_from_zero_when_no_prior_tags(monkeypatch):
    monkeypatch.setattr(next_semver, "current_head_tag", lambda: None)
    monkeypatch.setattr(next_semver, "latest_semver_tag", lambda: None)
    monkeypatch.setattr(
        next_semver,
        "commits_since",
        lambda tag: [("feat: initial native package release", "")],
    )

    release = next_semver.resolve_release()

    assert release["release_needed"] == "true"
    assert release["release_tag"] == "v0.1.0"
    assert release["release_bump"] == "minor"


def test_resolve_release_reuses_existing_tag_on_head(monkeypatch):
    monkeypatch.setattr(next_semver, "current_head_tag", lambda: next_semver.SemverTag(1, 4, 2))

    release = next_semver.resolve_release()

    assert release["release_needed"] == "true"
    assert release["release_tag"] == "v1.4.2"
    assert release["release_bump"] == "existing"


def test_resolve_release_skips_when_no_releasable_commits(monkeypatch):
    monkeypatch.setattr(next_semver, "current_head_tag", lambda: None)
    monkeypatch.setattr(next_semver, "latest_semver_tag", lambda: next_semver.SemverTag(1, 2, 3))
    monkeypatch.setattr(
        next_semver,
        "commits_since",
        lambda tag: [("docs: refresh deployment notes", ""), ("ci: tweak workflow name", "")],
    )

    release = next_semver.resolve_release()

    assert release["release_needed"] == "false"
    assert release["release_tag"] == ""
    assert release["release_bump"] == "none"

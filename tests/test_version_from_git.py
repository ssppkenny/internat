import subprocess
import sys
from pathlib import Path

import pytest

from tools import version_from_git
from tools.version_from_git import commit_increment, format_version, parse_base

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "version_from_git.py"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def git(repo: Path, *args: str) -> str:
    result = run(["git", *args], repo)
    assert result.returncode == 0, result.stderr
    return result.stdout


def init_repo(repo: Path) -> None:
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")


def commit(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def test_parse_base_and_format_version() -> None:
    assert parse_base("0.1") == 10
    assert format_version(10) == "0.1"
    assert format_version(60) == "0.6"
    assert format_version(187) == "1.87"
    assert format_version(611) == "6.11"


def test_commit_increment() -> None:
    assert commit_increment(1, 0) == 50
    assert commit_increment(2, 3) == 50
    assert commit_increment(0, 1) == 1
    assert commit_increment(0, 0) == 0


def test_computes_version_from_history(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / "VERSION").write_text("0.1\n", encoding="utf-8")
    chapter = repo / "internat" / "outline" / "0-part" / "0-ch.md"
    chapter.parent.mkdir(parents=True)
    chapter.write_text("one\n", encoding="utf-8")
    commit(repo, "initial")
    chapter2 = chapter.parent / "1-ch.md"
    chapter2.write_text("two\n", encoding="utf-8")
    commit(repo, "add chapter")
    chapter.write_text("one edited\n", encoding="utf-8")
    commit(repo, "edit chapter")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    commit(repo, "unrelated")
    result = run([sys.executable, str(SCRIPT)], repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.61"


def test_quoted_unicode_paths_added_and_renamed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    git(repo, "config", "core.quotePath", "true")
    (repo / "VERSION").write_text("0.1\n", encoding="utf-8")
    commit(repo, "initial")
    chapter = repo / "internat" / "outline" / "0-Часть 1" / "Новая глава.md"
    chapter.parent.mkdir(parents=True)
    chapter.write_text("one\n", encoding="utf-8")
    commit(repo, "add quoted chapter")
    renamed = chapter.with_name("Другая глава.md")
    git(repo, "mv", str(chapter.relative_to(repo)), str(renamed.relative_to(repo)))
    commit(repo, "rename quoted chapter")
    result = run([sys.executable, str(SCRIPT)], repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.61"


def test_missing_version_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / "file.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "initial")
    result = run([sys.executable, str(SCRIPT)], repo)
    assert result.returncode == 1
    assert result.stderr.startswith("error:")


def test_missing_git_reports_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_missing(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("No such file or directory: 'git'")

    monkeypatch.setattr(version_from_git.subprocess, "run", raise_missing)
    assert version_from_git.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")

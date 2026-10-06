import subprocess
import sys
from pathlib import Path

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


def test_missing_version_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / "file.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "initial")
    result = run([sys.executable, str(SCRIPT)], repo)
    assert result.returncode == 1
    assert result.stderr.startswith("error:")

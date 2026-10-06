# Auto Version Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the book version automatically from chapter-changing commits (+0.5 per commit that adds a chapter, +0.01 per commit that only edits chapters) and show it on the landing page and the PDF title page.

**Architecture:** A new stdlib script `tools/version_from_git.py` walks `git log --name-status` over `internat/outline/` since the commit that introduced `VERSION`, adds the increments to the committed base version, and prints the result. In CI (checkout with full history) a one-line step redirects it into `VERSION` just before the converter runs; the converter, tests, and the committed `VERSION` file stay as they are.

**Tech Stack:** Python 3 standard library (`subprocess`, `decimal`), pytest, GitHub Actions.

## Global Constraints

- Counting rule, exact: for each commit touching `internat/outline/*.md` — if it adds at least one `.md` file → +0.5; else if it modifies, deletes, or renames at least one `.md` file → +0.01; one increment per commit regardless of file count; commits touching no `.md` (Photos-only, code, docs, `folder.txt`-only) → no change.
- Base = the committed `VERSION` content (`0.1`), read via `git show HEAD:VERSION`; anchor = oldest commit that added `VERSION` (auto-discovered, currently `a499491`); range is `anchor..HEAD` (excludes the anchor itself).
- Arithmetic is exact in hundredths; display trims trailing zeros: `0.1`, `0.6`, `0.11`, `1.87`. With current history (3 chapter-adding commits, 27 chapter-editing commits) the computed value is `1.87`, and re-running never compounds.
- `tools/version_from_git.py` runs from the repo root and uses git in the current working directory; on any failure it prints `error: ...` to stderr and exits 1. It never writes files itself (CI redirects its stdout).
- Workflow changes are exactly two: `actions/checkout@v4` gains `with: fetch-depth: 0`; a new step `Compute version` with `run: python3 tools/version_from_git.py > VERSION` is inserted immediately before `Generate site sources`. No other workflow step changes.
- Never modify `internat/outline/` or `Photos/`; do not stage the user's modified `internat/settings.txt`; generated `site/` and `build/` stay untracked.
- Tests run as `python3 -m pytest tests/ -v` from the repo root; expected total after this plan: 30 passed (26 existing + 4 new).
- Commit messages are short and imperative; push and live verification require explicit user confirmation.

---

### Task 1: Version script and tests

**Files:**
- Create: `tools/version_from_git.py`
- Test: `tests/test_version_from_git.py`

**Interfaces:**
- Consumes: nothing from earlier tasks; reads the repo's git history at test time.
- Produces: module-level `parse_base(text: str) -> int`, `commit_increment(added: int, changed: int) -> int`, `format_version(hundredths: int) -> str`, `compute() -> str`, `main() -> int`. Task 2's CI step calls the module as a script.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_version_from_git.py` with this exact content:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_version_from_git.py -v`
Expected: collection error / FAIL — `ModuleNotFoundError: No module named 'tools.version_from_git'`.

- [ ] **Step 3: Write the script**

Create `tools/version_from_git.py` with this exact content:

```python
#!/usr/bin/env python3
"""Print the book version computed from chapter history.

Run from the repo root. Base is the committed VERSION content; each commit
since the one that introduced VERSION adds 0.5 when it adds a chapter file
(internat/outline/*.md), else 0.01 when it only edits/deletes/renames one.
"""
import subprocess
import sys
from decimal import Decimal, InvalidOperation


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def parse_base(text: str) -> int:
    return int(Decimal(text.strip()) * 100)


def commit_increment(added: int, changed: int) -> int:
    if added > 0:
        return 50
    if changed > 0:
        return 1
    return 0


def format_version(hundredths: int) -> str:
    return format(Decimal(hundredths) / 100, "f")


def anchor_commit() -> str:
    output = git("log", "--diff-filter=A", "--format=%H", "--", "VERSION")
    commits = output.split()
    if not commits:
        raise RuntimeError("no commit introduced VERSION")
    return commits[-1]


def compute() -> str:
    hundredths = parse_base(git("show", "HEAD:VERSION"))
    anchor = anchor_commit()
    output = git(
        "log", "--no-merges", "--name-status", "--format=%x00",
        f"{anchor}..HEAD", "--", "internat/outline",
    )
    for block in output.split("\x00"):
        files = [line for line in block.splitlines() if line.strip()]
        if not files:
            continue
        added = sum(
            1 for line in files
            if line.split("\t")[0] == "A" and line.endswith(".md")
        )
        changed = sum(
            1 for line in files
            if line.split("\t")[0] != "A" and line.endswith(".md")
        )
        hundredths += commit_increment(added, changed)
    return format_version(hundredths)


def main() -> int:
    try:
        print(compute())
    except (InvalidOperation, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_version_from_git.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/version_from_git.py tests/test_version_from_git.py
git commit -m "Compute version from chapter history"
```

---

### Task 2: Wire version computation into CI

**Files:**
- Modify: `.github/workflows/pages.yml`

**Interfaces:**
- Consumes: `tools/version_from_git.py` from Task 1 (module invoked as script).
- Produces: CI-built `VERSION` (workspace only) consumed unchanged by `tools/build_site.py` and the `-V date="Версия $(cat VERSION)"` PDF step.

- [ ] **Step 1: Give checkout full history**

Replace:

```yaml
      - uses: actions/checkout@v4
```

with:

```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
```

- [ ] **Step 2: Add the Compute version step**

Insert immediately before the `Generate site sources` step:

```yaml
      - name: Compute version
        run: python3 tools/version_from_git.py > VERSION
```

- [ ] **Step 3: Validate the workflow**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml')); print('yaml-ok')"`
Expected: `yaml-ok`.

- [ ] **Step 4: Verify locally end to end**

Run:
```bash
python3 tools/version_from_git.py
python3 tools/version_from_git.py
```
Expected: both print `1.87` (idempotent; no file changes).

Run:
```bash
python3 tools/version_from_git.py > VERSION && python3 tools/build_site.py && grep 'Версия 1.87' site/src/README.md && git checkout -- VERSION
```
Expected: `Wrote 25 chapters ...`; grep prints `Версия 1.87`; `VERSION` restored to `0.1` (`git status --short VERSION` empty).

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest tests/ -v`
Expected: 30 passed.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "Increment version from git history"
```

---

### Task 3: Push and verify live

**Files:**
- No file changes; ops only.

**Interfaces:**
- Consumes: green local verification from Tasks 1–2.
- Produces: deployed site and PDF showing `Версия 1.87`.

- [ ] **Step 1: Ask the user for push confirmation**

State exactly what will be pushed (this plan's commits) and wait for an explicit yes.

- [ ] **Step 2: Push and watch the run**

```bash
git push origin master
gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

- [ ] **Step 3: Verify live**

```bash
curl -s https://ssppkenny.github.io/internat/ | grep -o 'Версия [0-9.]*'
curl -s -o /tmp/opencode/live.pdf -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.pdf
pdftotext -f 1 -l 1 /tmp/opencode/live.pdf - | grep -o 'Версия [0-9.]*'
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.epub
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/part1/postuplenie.html
```
Expected: `Версия 1.87` on the landing page and page 1 of the PDF; PDF/EPUB/chapter all `200`; `Обновлено` still present on the landing page.

---

## Self-Review

- Spec coverage: rule and per-commit increments → Task 1 `commit_increment`/`compute`; base and anchor → `parse_base`/`anchor_commit`; exact arithmetic and trimmed display → `format_version` + tests; CI `fetch-depth: 0` and Compute version step → Task 2; failure = exit 1 → `main` + `test_missing_version_fails`; idempotence → `HEAD:VERSION` read + twice-run check; live verification → Task 3. No gaps.
- Placeholder scan: all steps contain exact code, commands, and expected output.
- Type consistency: `parse_base`/`commit_increment`/`format_version`/`compute`/`main` names and signatures match between Task 1 tests, implementation, and Task 2 usage.

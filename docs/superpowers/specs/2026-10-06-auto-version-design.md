# Auto-incrementing version on the landing page — Design

## Goal

The version shown on the landing page (and the PDF title page) grows automatically with the book's
development, derived from git history at build time. No manual editing, no bot commits.

Today the version feature exposes a static base in the `VERSION` file (`0.1`). The landing page shows
`Версия 0.1` and the PDF title page shows the same value via `-V date="Версия $(cat VERSION)"`.

## Increment rule (binding)

A *chapter file* is any `*.md` file under `internat/outline/` (part directories and `folder.txt` do not
count). A commit's increment is computed from the name-status entries of its diff restricted to that path:

- If at least one entry has status `A` (added) → **+0.5** (once per commit, even if other files are also
  modified).
- Otherwise, if at least one `.md` entry exists (`M`, `D`, `R`, `C`, `T`) → **+0.01** (once per commit,
  regardless of how many files).
- If the commit touches no chapter file → **+0**.

The version is:

```
version = base + sum(increment for each commit in ANCHOR..HEAD)
```

- `base` = the content of `VERSION` **as committed at HEAD** (`git show HEAD:VERSION`), parsed as an exact
  decimal. Committed value: `0.1`.
- `ANCHOR` = the commit that first added the `VERSION` file, discovered dynamically as the oldest commit
  from `git log --diff-filter=A --format=%H -- VERSION` (currently `a499491`).
- Arithmetic is exact decimal hundredths (no floats).

With the current history: 3 added-chapter commits (+1.5) and 27 chapter-editing commits (+0.27) →
`1.87`.

Display format trims trailing zeros: base `0.1`; `+0.01` → `0.11`; `+0.5` → `0.6`; full history → `1.87`.

## Architecture

New stdlib-only script `tools/version_from_git.py`:

- `parse_base(text: str) -> Decimal` — parses the base, raises `ValueError` on invalid content.
- `commit_increment(statuses: list[str]) -> Decimal` — pure classifier over name-status codes:
  `["A"]` → `0.5`; `["M", "M"]` → `0.01`; `["D"]` → `0.01`; `[]` → `0`.
- `format_version(value: Decimal) -> str` — trailing-zero-trimmed display string.
- `compute() -> str` — in the current working directory: discovers `ANCHOR`, reads `HEAD:VERSION`, runs
  `git log --format=@%H --name-status ANCHOR..HEAD -- internat/outline`, sums per-commit increments,
  returns the formatted version.
- `main() -> int` — prints the version to stdout; on any failure prints an error to stderr and returns 1.

The script never writes `VERSION` itself; it prints, and the caller redirects.

`tools/build_site.py` and its tests are unchanged.

## CI change (`.github/workflows/pages.yml`)

- `actions/checkout@v4` gains `fetch-depth: 0` (the log must reach `ANCHOR`).
- New step immediately before `Generate site sources`:

```yaml
- name: Compute version
  run: python3 tools/version_from_git.py > VERSION
```

Everything downstream is unchanged: `tools/build_site.py` reads the computed `VERSION`, and the PDF step's
`-V date="Версия $(cat VERSION)"` picks up the same number. The EPUB has no version line (unchanged scope).

## Failure handling

Missing git, no anchor commit, unreadable/invalid `VERSION` at HEAD, or a git error → message on stderr and
exit code 1, which fails the workflow step loudly. The build never deploys a silently wrong version.

## Testing

New `tests/test_version_from_git.py` (pytest):

1. `parse_base("0.1") == Decimal("0.1")`; `parse_base("abc")` raises `ValueError`.
2. `commit_increment`: `["A"]` → 0.5; `["A", "M"]` → 0.5; `["M"]` → 0.01; `["M", "M", "D"]` → 0.01;
   `[]` → 0.
3. `format_version`: `Decimal("0.1")` → `"0.1"`; `Decimal("0.11")` → `"0.11"`; `Decimal("0.6")` → `"0.6"`;
   `Decimal("1.87")` → `"1.87"`.
4. Integration test in a temporary git repo (skipped if `git` is unavailable): commit a chapter + `VERSION`
   (add commit), edit the chapter (edit commit), commit an unrelated file (ignored) → expected `0.61`;
   running twice yields the same result (idempotent).

Existing 26 tests stay green.

## Local verification

1. In the real repo: `python3 tools/version_from_git.py` prints `1.87`.
2. `python3 tools/version_from_git.py > VERSION && python3 tools/build_site.py` → generated
   `site/src/README.md` contains `Версия 1.87`; then `git checkout -- VERSION` restores the committed base.
3. `mdbook build site` → built landing page contains `Версия 1.87`.
4. `python3 -m pytest tests/ -v` → 26 existing + 4 new pass.
5. After push: live landing page shows the computed number; the live PDF title page shows the same number.

## Risks and out of scope

- Rewriting git history changes the computed number; the number is monotonic only for append-only history.
- Only chapter commits count; infrastructure/doc commits do not (by design, matching the accepted rule).
- The `VERSION` file remains the manual base and can be bumped deliberately; all increments apply on top.
- The "Обновлено <date>" landing line keeps its current `date.today()` behavior.

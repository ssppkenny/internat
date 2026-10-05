# Landing Page Date and «Читать» Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a build-date line on the site's landing page and label its next-chapter arrow «Читать».

**Architecture:** The converter (`tools/build_site.py`) gains a `last_changed` date parameter and writes an «Обновлено …» line into the generated `README.md`; `site/theme/custom.css` gains landing-page-scoped rules that prepend «Читать» to the next-chapter arrow. No other output changes.

**Tech Stack:** Python 3 stdlib (`datetime`), pytest, mdBook v0.5.4 theme CSS.

## Global Constraints

- Landing page (`README.md` → `index.html`) only; chapter pages, EPUB, and PDF behavior must not change.
- Date semantics: build/deploy date — `last_changed` defaults to `date.today()`.
- Russian genitive months, day without leading zero: exact month list `января февраля марта апреля мая июня июля августа сентября октября ноября декабря`.
- Exact README line: `Обновлено 5 октября 2026`, placed after the `Версия {version}` line with blank lines around.
- CSS appended to `site/theme/custom.css` exactly as specified below; no other CSS changes.
- Stdlib-only converter; short imperative commit messages; push to master and live verification require explicit user confirmation.

---

### Task 1: Date line and «Читать» label

**Files:**
- Modify: `tools/build_site.py` (imports; helper near `read_version`; `build()` signature/body; README write at lines 263-271)
- Modify: `tests/test_build_site.py` (imports; one new test at end)
- Modify: `site/theme/custom.css` (append)

**Interfaces:**
- Consumes: existing `build(outline_dir, site_src, build_dir, photos_dir, version)` and the README block at `tools/build_site.py:263-271`.
- Produces: `format_date_ru(d: date) -> str`; `build(..., last_changed: date | None = None)`. Task 2 relies on the generated line and CSS only.

- [ ] **Step 1: Write the failing test**

In `tests/test_build_site.py`, add `from datetime import date` next to the other stdlib imports (`import shutil` area), then append:

```python
def test_readme_has_update_date(outline: Path, tmp_path: Path) -> None:
    build(
        outline,
        tmp_path / "src",
        tmp_path / "build",
        photos_dir=tmp_path / "Photos",
        last_changed=date(2026, 10, 5),
    )
    readme = (tmp_path / "src" / "README.md").read_text(encoding="utf-8")
    assert "Версия 0.1\n\nОбновлено 5 октября 2026\n\n" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_build_site.py::test_readme_has_update_date -v`
Expected: FAIL with `TypeError: build() got an unexpected keyword argument 'last_changed'`

- [ ] **Step 3: Implement the converter changes**

In `tools/build_site.py`, add after `import tempfile`:

```python
from datetime import date
```

After the `read_version()` function, add:

```python
MONTHS_RU = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def format_date_ru(d: date) -> str:
    return f"{d.day} {MONTHS_RU[d.month - 1]} {d.year}"
```

Change the `build` signature to add `last_changed` after `version`, and resolve it next to the version resolution:

```python
    version: str | None = None,
    last_changed: date | None = None,
) -> None:
    if version is None:
        version = read_version()
    if last_changed is None:
        last_changed = date.today()
```

In the README write, add the line between the version line and the blurb:

```python
        f"Версия {version}\n\n"
        f"Обновлено {format_date_ru(last_changed)}\n\n"
        "Воспоминания о годах учёбы в ФМШ №18 при МГУ.\n\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/ -v`
Expected: `26 passed`.

- [ ] **Step 5: Append the CSS label rules**

Append to `site/theme/custom.css`:

```css

.nav-wide-wrapper:not(:has(.nav-chapters.previous)) .nav-chapters.next {
    flex-direction: row;
    align-items: center;
    gap: 0.25em;
}

.nav-wide-wrapper:not(:has(.nav-chapters.previous)) .nav-chapters.next::before,
.nav-wrapper:not(:has(.mobile-nav-chapters.previous)) .mobile-nav-chapters.next::before {
    content: "Читать";
    font-size: 0.4em;
}
```

- [ ] **Step 6: Verify the real build**

Run: `python3 tools/build_site.py && rg 'Обновлено' site/src/README.md && (cd site && /tmp/opencode/mdbook-dist/mdbook build) && rg 'Обновлено' site/book/index.html && rg 'Читать' site/book/theme/ && rg 'nav-chapters previous' site/book/part1/postuplenie.html`

Expected: converter prints `Wrote <N> chapters` (N is the current chapter count); README and built `index.html` show `Обновлено <today, e.g. 5 октября 2026>`; the hashed theme CSS contains `Читать`; a chapter page contains a `nav-chapters previous` anchor (so the label scope does not match there).

- [ ] **Step 7: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py site/theme/custom.css
git commit -m "Add update date and landing read label"
```

---

### Task 2: Push and live verification (user confirmation required)

**Files:** none (ops only).

- [ ] **Step 1: Full test run**

Run: `python3 -m pytest tests/ -v`
Expected: `26 passed`.

- [ ] **Step 2: Ask the user for confirmation, then push**

Push `master` to `origin`, then watch the workflow run (same pattern as previous features):
`gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status`

- [ ] **Step 3: Live checks**

- `curl -s https://ssppkenny.github.io/internat/ | rg 'Обновлено'` shows today's Russian date.
- Fetch the live CSS from the `theme/custom-*.css` href in the live index and `rg 'Читать'` → present.
- `curl -sI https://ssppkenny.github.io/internat/part1/postuplenie.html` → 200, and its HTML contains `nav-chapters previous` (label scope does not apply to chapter pages).
- `/internat.pdf` and `/internat.epub` still 200.

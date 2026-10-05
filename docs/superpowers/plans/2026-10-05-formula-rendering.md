# Formula Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formulas render as vector SVG images in the EPUB, as MathJax on the site, and keep working in the PDF.

**Architecture:** `tools/build_site.py` gains a module-level `render_math_svg()` that compiles a minimal standalone LaTeX document and converts the DVI to a path-only SVG with `dvisvgm --no-fonts --exact-bbox`, plus `replace_math()` that rewrites `$$...$$` and `$...$` in the EPUB source (`build/book.md`) to `![](build/math/eq-<hash>.svg)` image refs. Site sources and `build/book-raw.md` (the PDF source) keep raw math; the site gets client-side MathJax via `site/book.toml`, and CI installs the `dvisvgm` package.

**Tech Stack:** Python 3 stdlib (`hashlib`, `re`, `subprocess`, `tempfile`) + pytest; LaTeX (`latex`) and `dvisvgm`; mdBook v0.5.4; pandoc 3.7.0.2.

## Global Constraints

- Never modify anything under `internat/outline/` or `Photos/`.
- Formula syntax (from the spec): display math is `$$...$$` and may span lines; inline math is single-line `$...$` whose opening `$` is not followed by a space and whose closing `$` is not preceded by a space.
- Currency must stay text: `Стоит $5 и $7.` is not math (the closing-candidate `$` before `7` is preceded by a space).
- `site/src/` sources and `build/book-raw.md` keep raw math unchanged; only `build/book.md` gets `![](build/math/eq-<sha1[:12]>.svg)` refs.
- Renderer recipe: LaTeX document is exactly `\documentclass[border=1pt]{standalone}`, body `$...$` (display math wrapped as `$\displaystyle ...$`), then `dvisvgm --no-fonts --exact-bbox`. The SVG must be path-based (no font/text dependency).
- Module-level interfaces (tests monkeypatch them): `render_math_svg(expr: str, display: bool, out_dir: Path) -> Path` and `replace_math(body: str, math_dir: Path) -> str`.
- Render failure raises `ValueError`; `main()` already converts that to `error: ...` and exit 1.
- `site/book.toml`: add `mathjax-support = true` under the existing `[output.html]` table; change nothing else.
- `.github/workflows/pages.yml`: append `dvisvgm` to the existing `--no-install-recommends` apt list, and move the `Install TeX Live` step before `Generate site sources` (the converter invokes `latex`/`dvisvgm`); no other workflow change.
- Tests: `python3 -m pytest tests/ -v` from the repo root; expected `25 passed` (20 existing + 5 new).
- Commit messages are short and imperative. Push to `master` and live verification require explicit user confirmation.

---

### Task 1: Render formulas as SVG in the converter

**Files:**
- Modify: `tools/build_site.py`
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: existing `build(outline_dir, site_src, build_dir, photos_dir, version)` and the chapter loop that already produces `body` (post-verse-conversion) for `build/book.md`.
- Produces: module constants `MATH_REF_PREFIX`, `DISPLAY_MATH_RE`, `INLINE_MATH_RE`; functions `render_math_svg(expr, display, out_dir)` and `replace_math(body, math_dir)`; generated `build/math/eq-<sha1[:12]>.svg` files; `build/book.md` uses `![](build/math/eq-<hash>.svg)`. Task 2's CI installs `dvisvgm` (this task requires it locally to pass the real-render test).

- [ ] **Step 1: Write the failing tests**

In `tests/test_build_site.py`, add `import shutil` after `from pathlib import Path` (line 3 becomes a blank line-separated import group):

```python
import shutil
from pathlib import Path
```

Then append these five tests at the end of the file:

```python
def test_display_math_becomes_svg_ref(
    outline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_render(expr: str, display: bool, out_dir: Path) -> Path:
        calls.append((expr, display))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "eq-stub.svg"
        path.write_text("<svg/>", encoding="utf-8")
        return path

    monkeypatch.setattr(build_site, "render_math_svg", fake_render)
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "До.\n\n$$ x^2 $$\n\nПосле.",
    )
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "![](build/math/eq-stub.svg)" in book
    assert "$" not in book
    assert calls == [("x^2", True)]
    raw = (tmp_path / "build" / "book-raw.md").read_text(encoding="utf-8")
    assert "$$ x^2 $$" in raw
    site = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    assert "$$ x^2 $$" in site


def test_inline_math_becomes_svg_ref(
    outline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_render(expr: str, display: bool, out_dir: Path) -> Path:
        calls.append((expr, display))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "eq-inline.svg"
        path.write_text("<svg/>", encoding="utf-8")
        return path

    monkeypatch.setattr(build_site, "render_math_svg", fake_render)
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "Текст $x^2$ ещё.",
    )
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "Текст ![](build/math/eq-inline.svg) ещё." in book
    assert calls == [("x^2", False)]
    raw = (tmp_path / "build" / "book-raw.md").read_text(encoding="utf-8")
    assert "Текст $x^2$ ещё." in raw
    site = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    assert "Текст $x^2$ ещё." in site


def test_currency_amounts_are_not_math(
    outline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(expr: str, display: bool, out_dir: Path) -> Path:
        raise AssertionError(f"renderer called for {expr!r}")

    monkeypatch.setattr(build_site, "render_math_svg", boom)
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "Стоит $5 и $7.",
    )
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "Стоит $5 и $7." in book


def test_math_render_failure_fails_build(
    outline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(expr: str, display: bool, out_dir: Path) -> Path:
        raise ValueError(f"math render failed for {expr!r}: boom")

    monkeypatch.setattr(build_site, "render_math_svg", fail)
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "$$ x $$",
    )
    with pytest.raises(ValueError, match="math render failed"):
        build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")


@pytest.mark.skipif(
    shutil.which("latex") is None or shutil.which("dvisvgm") is None,
    reason="latex or dvisvgm not installed",
)
def test_real_math_render_produces_svg(outline: Path, tmp_path: Path) -> None:
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "$$ \\frac{1}{\\sqrt{n}} $$",
    )
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    svgs = sorted((tmp_path / "build" / "math").glob("*.svg"))
    assert len(svgs) == 1
    text = svgs[0].read_text(encoding="utf-8")
    assert "<svg" in text
    assert "<path" in text
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert f"![](build/math/{svgs[0].name})" in book
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_build_site.py -v`
Expected: 5 failures/errors — `AttributeError: ... has no attribute 'render_math_svg'` for the four monkeypatch tests, and `assert 0 == 1` for the real-render test (no `build/math` output yet).

- [ ] **Step 3: Implement the converter changes**

In `tools/build_site.py`, extend the import block (lines 6-10) to:

```python
import hashlib
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
```

After `STANDALONE_IMAGE_RE = ...` (line 30) add:

```python
MATH_REF_PREFIX = "build/math"
DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\$)")
```

After `render_image_figures` (after line 111) add:

```python
def render_math_svg(expr: str, display: bool, out_dir: Path) -> Path:
    digest = hashlib.sha1(f"{int(display)}:{expr}".encode("utf-8")).hexdigest()[:12]
    out_path = out_dir / f"eq-{digest}.svg"
    if out_path.is_file():
        return out_path

    body = f"$\\displaystyle {expr}$" if display else f"${expr}$"
    document = (
        "\\documentclass[border=1pt]{standalone}\n"
        "\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "formula.tex").write_text(document, encoding="utf-8")
        commands = [
            ["latex", "-interaction=nonstopmode", "-halt-on-error", "formula.tex"],
            [
                "dvisvgm",
                "--no-fonts",
                "--exact-bbox",
                "formula.dvi",
                "-o",
                str(out_path.resolve()),
            ],
        ]
        for command in commands:
            try:
                result = subprocess.run(
                    command, cwd=tmp_dir, capture_output=True, text=True
                )
            except FileNotFoundError as error:
                raise ValueError(
                    f"math render failed for {expr!r}: {command[0]} not found"
                ) from error
            if result.returncode != 0:
                tail = "\n".join((result.stdout + result.stderr).splitlines()[-5:])
                raise ValueError(f"math render failed for {expr!r}: {tail}")
    if not out_path.is_file():
        raise ValueError(f"math render failed for {expr!r}: no SVG produced")
    return out_path


def replace_math(body: str, math_dir: Path) -> str:
    def render_display(match: re.Match[str]) -> str:
        path = render_math_svg(match.group(1).strip(), True, math_dir)
        return f"![]({MATH_REF_PREFIX}/{path.name})"

    def render_inline(match: re.Match[str]) -> str:
        path = render_math_svg(match.group(1), False, math_dir)
        return f"![]({MATH_REF_PREFIX}/{path.name})"

    body = DISPLAY_MATH_RE.sub(render_display, body)
    return INLINE_MATH_RE.sub(render_inline, body)
```

In `build()`, after `body = convert_verse_blocks(body)` (line 176) add:

```python
            epub_body = replace_math(body, build_dir / "math")
```

and change the EPUB accumulator line (line 191) from:

```python
            book_lines += [f"## {chapter_title}", "", body, ""]
```

to:

```python
            book_lines += [f"## {chapter_title}", "", epub_body, ""]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/ -v`
Expected: `25 passed`.

- [ ] **Step 5: Verify against the real corpus**

Run:

```bash
python3 tools/build_site.py
grep -c 'begin{verse}' build/book-raw.md
grep -c 'begin{verse}' build/book.md
grep -c '\$\$' build/book-raw.md
grep -c '\$\$' build/book.md
ls build/math/
grep -o '!\[\](build/math/eq-[0-9a-f]*\.svg)' build/book.md
grep -c '\$\$' site/src/part1/postuplenie.md
```

Expected: `Wrote 25 chapters ...`; `11`; `0` (or grep exit 1); `1`; `0` (or grep exit 1); one file `eq-<12 hex>.svg`; exactly one ref line `![](build/math/eq-<12 hex>.svg)`; `1` (site keeps the raw formula).

- [ ] **Step 6: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py
git commit -m "Render formulas as SVG in EPUB"
```

---

### Task 2: Enable MathJax on the site and install dvisvgm in CI

**Files:**
- Modify: `site/book.toml`
- Modify: `.github/workflows/pages.yml`

**Interfaces:**
- Consumes: Task 1's SVG refs in `build/book.md` (SVG files are generated into `build/math/`, which is already gitignored via `build/`).
- Produces: MathJax-enabled mdBook output for the site; `dvisvgm` available in CI so the `Build EPUB` step succeeds with formulas.

- [ ] **Step 1: Add MathJax to the mdBook config**

Change `site/book.toml` to exactly:

```toml
[book]
title = "Интернат"
authors = ["Сергей Михно"]
language = "ru"
src = "src"

[output.html]
site-url = "https://ssppkenny.github.io/internat/"
additional-css = ["theme/custom.css"]
mathjax-support = true
```

- [ ] **Step 2: Install dvisvgm in CI**

In `.github/workflows/pages.yml`, change the apt list line (line 52) from:

```yaml
            texlive-fonts-recommended texlive-lang-cyrillic lmodern cm-super
```

to:

```yaml
            texlive-fonts-recommended texlive-lang-cyrillic lmodern cm-super dvisvgm
```

Also move the `Install TeX Live` step before `Generate site sources`, since the converter invokes `latex`/`dvisvgm`; the earlier append-only constraint is superseded by this ordering requirement. No other workflow change.

- [ ] **Step 3: Validate YAML and verify both outputs locally**

Run:

```bash
python3 -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('.github/workflows/pages.yml').read_text())"
python3 tools/build_site.py
/tmp/opencode/mdbook-dist/mdbook build site
grep -c 'MathJax' site/book/part1/postuplenie.html
grep -c '\$\$' site/book/part1/postuplenie.html
~/.local/bin/pandoc build/book.md -o /tmp/opencode/formula-check.epub --toc \
  --metadata title="Интернат" --metadata author="Сергей Михно" --metadata lang=ru
unzip -l /tmp/opencode/formula-check.epub | grep -ci svg
unzip -p /tmp/opencode/formula-check.epub | grep -c 'frac' || true
```

Expected: YAML check silent (exit 0); `Wrote 25 chapters ...`; mdBook build exit 0; MathJax count ≥ 1; raw `$$` count ≥ 1 (site keeps the source for MathJax); pandoc produces no `Could not convert TeX math` warning; `unzip -l` SVG count ≥ 1; `frac` count `0` (no raw TeX left in the EPUB).

- [ ] **Step 4: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: `25 passed` (config-only change; included so the committed state is verified).

- [ ] **Step 5: Commit**

```bash
git add site/book.toml .github/workflows/pages.yml
git commit -m "Enable MathJax and install dvisvgm"
```

---

### Task 3: Push and verify live (requires user confirmation)

**Files:**
- No file changes.

- [ ] **Step 1: Confirm with the user** that `master` may be pushed and the site redeployed. Do not push before explicit approval.

- [ ] **Step 2: Run the full suite once more, then push**

Run:

```bash
python3 -m pytest tests/ -v
git push origin master
gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

Expected: `25 passed`; push succeeds; the watched run exits 0.

- [ ] **Step 3: Verify live**

Run:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/
curl -s https://ssppkenny.github.io/internat/part1/postuplenie.html | grep -c 'MathJax'
curl -s -o /tmp/opencode/live.epub -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.epub
unzip -l /tmp/opencode/live.epub | grep -ci svg
unzip -p /tmp/opencode/live.epub | grep -c 'frac' || true
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.pdf
```

Expected: `200`; MathJax count ≥ 1; EPUB `200`; SVG count ≥ 1; `frac` count `0`; PDF `200` (PDF path is unchanged by this feature).

# EPUB Math PNG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SVG formula images in the EPUB with 600-dpi transparent PNGs sized correctly for e-readers.

**Architecture:** `tools/build_site.py` already renders each formula through `latex` + `dvisvgm` and references it from the EPUB source only (`build/book.md`). We swap the second tool for `dvipng`, read the PNG's pixel width from its IHDR header, and emit an explicit `{width=<n>pt}` attribute so pandoc writes a physical CSS width. Site (MathJax) and PDF (raw LaTeX) paths are untouched.

**Tech Stack:** Python 3 stdlib (hashlib, subprocess, tempfile, struct-free PNG header parse), pytest, LaTeX + dvipng, pandoc, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-26-epub-math-png-design.md`

## Global Constraints

- Python standard library only; no new dependencies.
- Rendering must stay offline (no external services).
- Only the EPUB source changes: `build/book.md`. `build/book-raw.md` (PDF) keeps raw `$$...$$`; `site/src` keeps raw math for MathJax.
- DPI is exactly 600; width in points = `round(px * 72 / 600, 2)`.
- Tests run with `python3 -m pytest` (27+ existing tests must stay green).
- Nothing is pushed without the user's explicit confirmation.

## Review Focus

- `dvipng` missing on the build machine → the converter must raise `ValueError` naming `dvipng`, not a traceback.
- A truncated/corrupt PNG in the cache → must fail loudly, never emit `width=0`.
- An inline formula inside a sentence → surrounding text preserved and the image carries its width attribute.
- Currency amounts (`$5`) must not be mistaken for math.
- Invalid LaTeX → the build fails with the log tail, not a half-written EPUB.

---

### Task 1: PNG renderer, sizing, CI package

**Files:**
- Modify: `tools/build_site.py` (renderer + reference emission, constants near line 35)
- Modify: `tests/test_build_site.py` (math tests, ~lines 240-355)
- Modify: `.github/workflows/pages.yml` (apt list, "Install TeX Live" step)

**Interfaces:**
- Consumes: `MATH_REF_PREFIX = "build/math"`, `hashlib`, `subprocess`, `tempfile` already imported.
- Produces:
  - `MATH_DPI: int = 600`
  - `_png_width(path: Path) -> int`
  - `render_math_png(expr: str, display: bool, out_dir: Path) -> Path`
  - `replace_math(body: str, math_dir: Path) -> str` (signature unchanged; emits `{width=...pt}`)

- [ ] **Step 1: Rewrite the math tests (failing)**

In `tests/test_build_site.py`, replace the four math tests and the real-render test so they target PNG. Add `import struct` at the top. Add a helper:

```python
def _write_png(path: Path, width: int) -> None:
    ihdr = struct.pack(">IIBBBBB", width, 40, 8, 6, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk + struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0))
```

- `test_display_math_becomes_png_ref(outline, tmp_path)`: stub `render_math_png` writes `eq-stub.png` with width 1206 via `_write_png`; assert
  `"![](build/math/eq-stub.png){width=144.72pt}"` in `(tmp_path / "build" / "book.md").read_text(...)`.
- `test_inline_math_becomes_png_ref(outline, tmp_path)`: stub writes `eq-inline.png` at width 600 (→ 72.0pt); assert
  `"Текст ![](build/math/eq-inline.png){width=72.0pt} ещё."` in the book.
- `test_currency_amounts_are_not_math`: keep, but monkeypatch `render_math_png` with a raising stub; assert `$5` text unchanged and stub not called.
- `test_math_render_failure_fails_build`: monkeypatch `render_math_png` to raise `ValueError("math render failed for ...: boom")`; assert `build()` raises `ValueError` matching `"math render failed"`.
- `test_png_width_rejects_corrupt_file(tmp_path)`: write `bad.png` with `b"not a png"`; `with pytest.raises(ValueError, match="invalid PNG"): build_site._png_width(bad)`.
- `test_render_reports_missing_dvipng(monkeypatch, tmp_path)`: monkeypatch `subprocess.run` so the `latex` call returns `SimpleNamespace(returncode=0, stdout="", stderr="")` (and creates nothing) and any `dvipng` call raises `FileNotFoundError`; assert `pytest.raises(ValueError, match="dvipng not found")` from `render_math_png("x", True, tmp_path)`.
- `test_real_math_render_produces_png(outline, tmp_path)`: skip unless both `shutil.which("latex")` and `shutil.which("dvipng")`; assert exactly one `*.png` in `build/math`, it starts with `b"\x89PNG\r\n\x1a\n"`, its width from `_png_width` is `> 0`, and the book contains `f"![](build/math/{png.name}){{width="`.

- [ ] **Step 2: Run the math tests to verify they fail**

Run: `python3 -m pytest tests/test_build_site.py -k "math or png or currency" -v`
Expected: failures/errors because `render_math_png`, `_png_width`, and width attributes do not exist.

- [ ] **Step 3: Implement the renderer and sizing in `tools/build_site.py`**

Add `MATH_DPI = 600` next to `MATH_REF_PREFIX`. Replace `render_math_svg` with `render_math_png` keeping today's document body (`standalone`, `border=1pt`, `$\displaystyle …$` for display, `$…$` for inline), the same SHA-1 digest `f"{int(display)}:{expr}"` (filename `eq-<digest>.png`), the same cache check and error-handling pattern, and this second command:

```python
["dvipng", "-T", "tight", "-D", str(MATH_DPI), "-bg", "Transparent",
 "-o", str(out_path.resolve()), "formula.dvi"]
```

If no file is produced: `ValueError(f"math render failed for {expr!r}: no PNG produced")`.

Add `_png_width(path: Path) -> int` reading the first 24 bytes; require the 8-byte PNG signature and `b"IHDR"` at bytes 12:16, else raise `ValueError(f"invalid PNG: {path}")`; return `int.from_bytes(data[16:20], "big")`.

Rewrite `replace_math` so both branches return
`f"![]({MATH_REF_PREFIX}/{path.name}){{width={round(_png_width(path) * 72 / MATH_DPI, 2)}pt}}"`.

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass (the real-render test runs if `latex`/`dvipng` are installed).

- [ ] **Step 5: Swap the CI package**

In `.github/workflows/pages.yml`, "Install TeX Live": replace `dvisvgm` with `dvipng` in the apt install list; leave the rest of the list unchanged.

- [ ] **Step 6: Verify the EPUB end-to-end locally**

```bash
python3 tools/build_site.py
grep -o '!\[\](build/math/[^)]*){width=[0-9.]*pt}' build/book.md | head -3
grep -c '^\$\$' build/book-raw.md
pandoc build/book.md -o /tmp/opencode/check.epub --toc --split-level=1 \
  --epub-cover-image=Photos/Omslag.jpg -M lang=ru 2>/tmp/opencode/epub.err
unzip -l /tmp/opencode/check.epub | grep media/
unzip -p /tmp/opencode/check.epub EPUB/text/*.xhtml | grep -o '<img src="[^"]*\.png"[^>]*>' | head -2
grep -c 'Could not convert TeX math' /tmp/opencode/epub.err
```

Expected: `build/book.md` references `eq-*.png` with a `{width=...pt}`; `build/book-raw.md` still contains raw `$$` lines; the EPUB lists a `media/*.png`; the XHTML shows the image with `style="width:...in"`; zero "Could not convert TeX math" warnings.

- [ ] **Step 7: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py .github/workflows/pages.yml
git commit -m "Render EPUB formulas as PNG"
```

### Task 2: Push and verify live (requires user confirmation)

**Files:** none.

- [ ] **Step 1: Ask the user for push confirmation and push** (only after approval)

```bash
git push origin master
```

- [ ] **Step 2: Watch the workflow and verify the live EPUB**

```bash
gh run list --workflow pages.yml --limit 1 --json databaseId,status,conclusion
curl -fsSL -o /tmp/opencode/live.epub https://ssppkenny.github.io/internat/internat.epub
unzip -l /tmp/opencode/live.epub | grep media/
unzip -p /tmp/opencode/live.epub EPUB/text/*.xhtml | grep -o '<img src="[^"]*\.png"[^>]*>' | head -2
curl -fsS -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.pdf
```

Expected: run `conclusion: success`; live EPUB contains only PNG media for math (no `eq-*.svg`) and a width style on the image; PDF returns 200.

- [ ] **Step 3: Report**

Tell the user the live EPUB now shows formulas as PNG (their Android reader should display them), with the run link and the PDF status.

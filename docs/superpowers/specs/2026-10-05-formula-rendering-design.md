# Formula Rendering Design

Date: 2026-10-05
Status: Approved (pending written-spec review)

## Problem

The author writes LaTeX math in Manuskript chapters. The PDF renders it (raw
LaTeX goes through `build/book-raw.md` into pdflatex), but the site and the
EPUB show the raw source:

- mdBook has no math support configured, so `$$...$$` appears as literal text
  in the HTML.
- Pandoc (3.7.0.2) cannot convert the current formula: it warns
  `Could not convert TeX math ... rendering as TeX` and emits
  `<span class="math display">$$...$$</span>`. Even when pandoc can convert,
  MathML support in EPUB readers is unreliable.

The user wants: MathJax rendering on the site, and embedded SVG images in the
EPUB (works in any reader, offline, no font dependency).

## Scope

Both display (`$$...$$`) and inline (`$...$`) math, for all formulas now and
in the future. The manuscript sources are never modified: the author keeps
typing LaTeX math in Manuskript.

Exactly one formula exists today:
`internat/outline/0------_1/0------------.md:40`

```
$$ \frac{1}{\sqrt{1}} + \frac{1}{\sqrt{2}} + \dots + \frac{1}{\sqrt{n}} \ge \sqrt{n} $$
```

## Design

### Site (HTML): MathJax

Add `mathjax-support = true` under `[output.html]` in `site/book.toml`.
Verified with the pinned mdBook v0.5.4: the built page includes the MathJax 2
script (config `TeX-AMS-MML_HTMLorMML`), which renders both `$$...$$` and
`$...$` client-side. The site markdown is unchanged. Reading the site already
requires network (GitHub Pages), so the CDN script is acceptable.

### EPUB: pre-rendered SVG images

The converter renders each unique formula to an SVG file and links it as an
image in `build/book.md` (the EPUB source only):

- New module-level function
  `render_math_svg(expr: str, display: bool, out_dir: Path) -> Path` in
  `tools/build_site.py`:
  - Writes `<out_dir>/eq-<sha1>[:12].svg`, where the hash covers `display`
    and the exact expression, so identical formulas share one file.
  - Builds a minimal LaTeX document in a temporary directory:
    `\documentclass[border=1pt]{standalone}` + `\begin{document}` +
    `$\displaystyle <expr>$` (display) or `$<expr>$` (inline) +
    `\end{document}` (expression inserted verbatim; newlines allowed).
  - Runs `latex -interaction=nonstopmode -halt-on-error` then
    `dvisvgm --no-fonts --exact-bbox <file>.dvi -o <out.svg>`.
    `--no-fonts` converts glyphs to paths, so the SVG needs no fonts;
    `--exact-bbox` crops to the formula. Verified locally with dvisvgm
    3.6.1 on the real formula: 122.5 x 22.6 pt SVG, 7 path / 0 text
    elements.
  - On failure (nonzero exit, missing binary) raises `ValueError` with the
    expression and the tail of the tool log, so a bad formula fails the
    build with an actionable message (like a missing photo does).
- New function `replace_math(body: str, math_dir: Path) -> str`:
  - Replaces `$$...$$` (display, single- or multi-line) first, then `$...$`
    inline with the standard TeX whitespace rule: opening `$` not followed
    by whitespace, closing `$` not preceded by whitespace. This keeps
    currency like `$5 и $7` untouched. Inline matches are single-line.
  - Each match becomes `![](build/math/eq-<hash>.svg)` — a path relative to
    the repo root, matching the existing `Photos/...` convention, because
    the CI pandoc command runs from the repo root and pandoc's default
    resource path is the working directory.
- `build(...)`: only the `book_lines` (EPUB) path uses
  `replace_math(body, build_dir / "math")`. The site sources keep raw math
  (MathJax renders it) and `build/book-raw.md` keeps raw math (pdflatex
  renders it). Generated SVGs land in `build/math/` (already gitignored via
  `build/`).

### CI

Add `dvisvgm` to the `Install TeX Live` apt list in
`.github/workflows/pages.yml` (Ubuntu package, DVI-to-SVG, no Ghostscript
needed). `latex` comes from `texlive-latex-base` and `standalone.cls` from
`texlive-latex-extra`, both already installed. The existing pandoc EPUB
command is unchanged.

## Data flow

```
Manuskript chapter ($$...$$ / $...$)
        │
        ▼
tools/build_site.py
  ├─ site/src/...         raw math        → mdBook + MathJax  (HTML)
  ├─ build/book-raw.md    raw math        → pandoc → latex   (PDF)
  └─ build/book.md        ![].svg refs    → pandoc           (EPUB)
        └─ build/math/eq-<hash>.svg       (embedded SVG)
```

## Error handling

- Invalid LaTeX or a missing tool -> `ValueError` -> build exits 1 with the
  expression and log tail.
- A lone/currency `$` (no valid pair) is left as literal text.
- `.svg` is a core EPUB3 media type; pandoc copies local images into the
  EPUB, so every reader gets the picture without network.

## Testing

`tests/test_build_site.py`, on top of the existing 20 tests (all of which
keep passing unchanged; their fixtures contain no `$`):

1. Display math: `$$ x^2 $$` becomes `![](build/math/eq-<hash>.svg)` in
   `book.md`, the SVG file exists, and `book-raw.md` still contains
   `$$ x^2 $$` (renderer stubbed via monkeypatch; no LaTeX needed).
2. Inline math: `Текст $x^2$ ещё` becomes an inline image ref in `book.md`;
   `book-raw.md` unchanged.
3. Currency is not math: `Стоит $5 и $7.` stays verbatim in `book.md`.
4. Render failure: renderer raising `ValueError` propagates out of `build()`.
5. Real rendering (auto-skipped if `latex`/`dvisvgm` are not on PATH):
   renders the real corpus formula and asserts a `<svg` document with a
   non-trivial file size.

## Verification

1. `python3 -m pytest tests/ -v` — 25 expected (20 + 5).
2. Real corpus: converter writes `build/math/eq-*.svg` and a `book.md` image
   ref; `book-raw.md` and `site/src/part1/postuplenie.md` keep `$$...$$`.
3. `mdbook build site`: `postuplenie.html` contains the MathJax script and
   the raw formula (client-side rendering).
4. Local EPUB: pandoc no longer prints `Could not convert TeX math`; the
   EPUB contains an `.svg` entry and an `img` reference for the formula.
5. CI after push (user confirmation required): run green; live
   `postuplenie.html` includes MathJax; live EPUB contains the SVG.

## Risks / decisions

- **Inline SVG baseline**: inline formulas are baseline-aligned images; for
  simple expressions this is acceptable. Only address if a real formula looks
  off.
- **CI dvisvgm version**: flags are stable across dvisvgm 2.x/3.x; the first
  CI run is the verification. If the flag set differs, adjust to the
  equivalent option.
- **Inline false positives**: `$5`-style currency is protected by the
  whitespace rule; no `$` other than the one formula exists in the corpus
  today.
- **No MathML fallback**: deliberate — user requirement.

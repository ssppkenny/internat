# EPUB formulas as PNG instead of SVG

Date: 2026-10-26
Status: draft

## Problem

The EPUB build renders every formula to an SVG file and embeds it. Some e-readers
(confirmed: an Android reader app used by the author) do not support SVG at all —
they display a blank/white rectangle instead of the formula.

An EPUB cannot detect SVG support at runtime: most readers do not run scripts, and
CSS has no feature query for image-format support. A fallback that only fires on
unsupported readers is therefore impossible.

## Decision

Render formulas for the EPUB as **raster PNG** (600 dpi, transparent background).
PNG support is universal across e-readers.

Unchanged:

- Site: MathJax renders `$...$` / `$$...$$` in the browser (no image files).
- PDF: LaTeX typesets formulas natively.
- Only the EPUB source (`build/book.md`) receives image references.

Rejected alternatives:

- Runtime SVG detection / dual SVG+PNG markup — not supported reliably by EPUB readers.
- MathML — not supported by the affected reader either.
- External rendering services — third-party dependency; build must stay offline.

## Implementation

### Renderer

Replace `render_math_svg` with `render_math_png(expr, display, out_dir) -> Path`:

- Filename: `eq-<digest>.png`, same SHA-1 digest of `f"{int(display)}:{expr}"` as today;
  reuse the file if it already exists (per-build cache).
- LaTeX source unchanged: `standalone` class with `border=1pt`; body is
  `$\displaystyle <expr>$` for display and `$<expr>$` for inline.
- Commands, run in a temporary directory:
  1. `latex -interaction=nonstopmode -halt-on-error formula.tex`
  2. `dvipng -T tight -D 600 -bg Transparent -o <absolute out path> formula.dvi`
- Error handling preserved: missing binary → `ValueError("... <tool> not found")`;
  non-zero exit → last five output lines; no output file → `... no PNG produced`.

### Sizing

A PNG at 600 dpi has no meaningful intrinsic CSS size, so every reference carries an
explicit width:

- Read the pixel width from the PNG header (IHDR, big-endian `int` at byte offset 16).
- `width_pt = round(px * 72 / 600, 2)`.
- Emit `![](build/math/eq-<digest>.png){width=<width_pt>pt}` for both display and
  inline formulas. Pandoc converts this to `style="width:<inches>in"` in the EPUB XHTML,
  preserving the formula's physical size.

Inline formulas keep today's baseline behavior (image bottom aligned to the text
baseline); this change does not alter it.

### Workflow

`.github/workflows/pages.yml`: replace the `dvisvgm` apt package with `dvipng` in the
"Install TeX Live" step. `latex` is already provided by `texlive-latex-base`;
`dvipng` is a separate Ubuntu package.

### Tests

Update `tests/test_build_site.py`:

- Stub renderer writes a minimal valid PNG whose IHDR declares a known width
  (e.g. 1206 px); assert the emitted reference is
  `![](build/math/eq-stub.png){width=144.72pt}` (display) and the inline equivalent.
- Currency guard and failure-propagation tests keep working with the renamed renderer.
- Real-render test: skip unless `latex` and `dvipng` are available; assert one `.png`
  is produced, starts with the PNG signature, has non-zero width, and the book uses it.

## Non-goals

- No change to the site (MathJax) or PDF (LaTeX) pipelines.
- No MathML output, no runtime format detection.
- No cleanup of previously generated `.svg` files (build output is gitignored).

## Acceptance criteria

- The converter emits PNG references with explicit widths for display and inline math.
- The EPUB built by pandoc embeds `media/*.png` and references them with a width style.
- Site and PDF builds are unchanged.
- CI installs `dvipng`; the Pages workflow completes successfully.

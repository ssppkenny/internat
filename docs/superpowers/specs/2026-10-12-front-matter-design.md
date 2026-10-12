# Front matter (top-level outline texts) design

Date: 2026-10-12

## Problem

The author added a foreword as the first text in Manuskript. Manuskript stores a top-level text item directly under `internat/outline/` (here: `0------------.md`, title «Предисловие»), outside any part folder. The pipeline ignores such files: `find_parts` only considers directories, `find_chapters` only scans `*.md` inside part directories. The foreword therefore appears nowhere — site, EPUB, and the CI-built PDF all omit it (verified: 0 occurrences in `site/src/SUMMARY.md`, `build/book.md`, `build/book-raw.md`).

## Decision

Treat root-level outline texts as **front matter**: read them, order them by their leading number, and emit them before the first part in every output, going through the same body pipeline as chapters.

### Discovery

- New helper `find_front_texts(outline_dir: Path) -> list[tuple[int, Path]]` next to `find_parts`/`find_chapters`: root-level `*.md` files with a leading integer, sorted like chapters (`(number, name)`).
- Files without a leading integer stay ignored, as today. Multiple front texts are allowed and ordered by number (e.g. a future dedication at position 0 before a foreword at position 1).

### Processing

Identical to chapters: `parse_title`, `strip_front_matter`, empty body → `warning: ... empty chapter body, skipping`, `validate_images`, `convert_verse_emphasis` (raw), `convert_verse_blocks` (site/EPUB), `replace_math` (EPUB), plus `render_image_figures(rewrite_image_refs(...))` for the site. To avoid duplicating this block, extract a helper that returns the three body variants (site, EPUB, raw) for a given chapter path; both loops use it.

### Output placement (always before the first part)

- **Site**: file at `site/src/<slug>.md` (src root), slugs deduplicated among front texts; `SUMMARY.md` gains `- [Предисловие](predislovie.md)` immediately after the `[Интернат](README.md)` line and before the first part heading.
- **EPUB** (`build/book.md`): `# Предисловие` + body — a level-1 entry, so the EPUB navigation lists it before «Часть 1».
- **PDF** (`build/book-raw.md`): `# Предисловие {-}` + raw body. Pandoc renders `{-}` as `\chapter*{Предисловие}` plus `\addcontentsline{toc}{chapter}{Предисловие}` (verified with pandoc 3.7.0.2), i.e. an unnumbered chapter that still appears in the table of contents; part numbering is unchanged.
- The `Wrote N chapters` count includes front texts.

## Architecture

One new discovery helper plus a small shared body-preparation helper in `tools/build_site.py`; the chapter loop is refactored to use the shared helper without behavior change. No workflow, CSS, or test-fixture structure changes. `site/src` root already hosts `README.md`; mdBook accepts root-level chapters in `SUMMARY.md`.

## Error handling

- Empty front text: same warning-and-skip path as empty chapters.
- Missing title: `parse_title` already raises `ValueError` → converter exits 1.
- Image/version errors propagate exactly as for chapters.

## Testing

New tests in `tests/test_build_site.py` (existing `outline` fixture, add a root-level file):

1. `test_front_text_in_summary_before_parts` — `- [Предисловие](predislovie.md)` appears before the `# Часть 1` line in `SUMMARY.md`; the file exists at `src/predislovie.md`.
2. `test_front_text_in_epub_and_pdf_sources` — `build/book.md` contains `# Предисловие` before `# Часть 1`; `build/book-raw.md` contains `# Предисловие {-}`.
3. `test_front_text_image_transforms_applied` — an image ref in the front text becomes `../Photos/...` + `<figure>` on the site and stays `Photos/...` in `book-raw.md`.

Expected suite: 37 + 3 = 40 passed.

## Verification

- Local: `python3 -m pytest tests/ -v` (40); `python3 tools/build_site.py` → 32 chapters; grep «Предисловие» in `SUMMARY.md`, `book.md`, `book-raw.md`; `mdbook build site`; exact CI PDF pipeline → `\chapter*{Предисловие}` in `build/book.tex`, preface in the TOC.
- After the user-approved push: live `/predislovie.html` 200; live EPUB contains «Предисловие»; live PDF TOC lists it and the text follows the TOC; landing page unchanged.

## Risks

- PDF `{-}` behavior relies on pandoc; verified locally on 3.7.0.2, CI runs apt pandoc (3.1.x) — confirm on the first CI run.
- A front-text slug equal to `readme` would collide with the landing page file name; the transliterating slugify makes this practically impossible for Russian titles, and no guard is added (YAGNI).

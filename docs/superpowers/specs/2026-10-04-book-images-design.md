# Book Images Design

**Date:** 2026-10-04
**Status:** Approved (pending written-spec review)
**Related:** `docs/superpowers/specs/2026-10-04-book-site-design.md`

## Goal

Let the author place photos in chapters so they appear in all three outputs: the
mdBook site, the EPUB download, and the regenerated PDF — using a single
markdown convention typed in the Manuskript editor.

## Non-goals

- No automatic attachment of photos to chapters by filename (placement is
  controlled by where the reference is typed).
- No visible caption block under images in the HTML book (alt text only; EPUB
  and PDF render real figure captions via pandoc).
- No per-image sizing controls.
- No changes to chapter content by tooling; the author adds references in
  Manuskript.

## Convention

Photos live in `Photos/` at the repository root and are committed to git
(12 files, ~6.2 MB today). In the Manuskript editor the author types:

```
![Подпись](Photos/имя.jpg)
```

- Path is relative to the repository root. This is what Manuskript writes into
  the chapter `.md`, what the LaTeX export emits as
  `\includegraphics{Photos/имя.jpg}`, and what TeXstudio resolves when
  compiling `book.tex` from the repository root.
- File names: Latin letters, digits, `-`/`_`; no spaces. References are
  case-sensitive (GitHub/Linux).
- The reference position in the chapter controls placement.

## Converter changes (`tools/build_site.py`)

- New module constant `PHOTOS_DIR = REPO_ROOT / "Photos"` and new keyword
  parameter `photos_dir: Path = PHOTOS_DIR` on `build()`.
- Image reference pattern:
  `IMG_RE = re.compile(r"\]\((?:\./)?Photos/([^)\s]+)\)")` — matches
  `](Photos/…)` and `](./Photos/…)`.
- For every chapter body:
  - Each captured `Photos/<rel>` must exist as
    `photos_dir / <rel>`; otherwise raise
    `ValueError(f"{chapter_path}: missing image Photos/<rel>")`.
  - The copy written to `site/src/partN/<slug>.md` rewrites references to
    `](../../Photos/<rel>)` (two levels up from `site/src/partN/`).
  - The copy written to `build/book.md` keeps `Photos/<rel>` unchanged;
    pandoc runs from the repository root and resolves it (verified locally).
- If `photos_dir` exists, copy it wholesale with
  `shutil.copytree(photos_dir, site_src / "Photos")` so mdBook ships the files
  (mdBook copies non-`.md` files from `src/` to the built site).
- If `photos_dir` does not exist and no chapter references an image, the build
  behaves exactly as today (no error).

## Site styling (`site/theme/custom.css`)

Append:

```css
.content main img {
    display: block;
    max-width: 100%;
    height: auto;
    margin: 1em auto;
}
```

## PDF (`fix-manuskript-latex.py`)

Make every included image fit the page while preserving aspect ratio. Insert
after `\usepackage{graphicx}` when present; otherwise insert both lines before
`\begin{document}` (pandoc omits `graphicx` when the book has no images):

```latex
\usepackage{graphicx}
\setkeys{Gin}{width=\linewidth,height=0.8\textheight,keepaspectratio}
```

The author's TeXstudio flow is unchanged; the script is rerun before compiling.

## Repo / CI

- Commit `Photos/` (currently untracked) as a source asset.
- No workflow changes: `python3 tools/build_site.py` copies the photos and the
  existing `pandoc build/book.md …` command already runs from the repository
  root.

## Testing (`tests/test_build_site.py`)

- Existing tests are updated to pass `photos_dir=tmp_path / "Photos"` so they
  do not copy the real 6.2 MB folder.
- New tests:
  1. Referenced photo: site chapter contains `../../Photos/pic.jpg`, the file
     exists at `site/src/Photos/pic.jpg`, and `build/book.md` still contains
     `Photos/pic.jpg`.
  2. `./Photos/` prefix variant is normalized to the same rewritten form.
  3. Missing referenced file raises `ValueError` naming the chapter and the
     missing `Photos/…` path.
  4. No `photos_dir` + no references: build succeeds unchanged.

## Verification

1. `python3 -m pytest tests/test_build_site.py -v` — all tests pass.
2. Real run: `python3 tools/build_site.py` writes `site/src/Photos/` and
   `mdbook build site` outputs `site/book/Photos/`; HTML `img src` resolves.
3. Synthetic EPUB check with a temp markdown referencing `Photos/photo.jpg` and
   the CI pandoc command: EPUB contains media (`EPUB/media/…`).
4. Manual (author): add a reference in Manuskript, regenerate the PDF via the
   existing TeXstudio flow; photo fits the page.

## Success criteria

- Author types `![Подпись](Photos/имя.jpg)` in a chapter and pushes; the photo
  appears at that position on the site and in the EPUB; a typo'd filename
  fails the workflow instead of publishing a broken link.
- Rerunning `fix-manuskript-latex.py` makes photos fit the page in the PDF.

# Frontispiece (Omslag.jpg) Design

**Date:** 2026-10-10
**Status:** Approved

## Goal

Show `Photos/Omslag.jpg` as a frontispiece at the start of the book in all
three targets: the site landing page (`index.html`), the PDF (after the title
page), and the EPUB (as the official cover).

## Decisions (user-approved)

- Landing page: the image is the first element, above the «Интернат» title,
  centered, scaled to the content width, no visible caption, alt text
  «Обложка».
- PDF: a frontispiece on its own page immediately after the generated title
  page and before the table of contents, centered, scaled to text width with
  height capped to the page, no caption.
- EPUB: official cover page via pandoc `--epub-cover-image`; e-reader
  libraries show it as the thumbnail. The text still starts at «Часть 1».
- No converter validation of the frontispiece file. Failure modes are loud
  enough: a missing file shows a broken image on the site and fails CI in the
  pandoc cover step and pdflatex.
- `Photos/Omslag.jpg` (currently untracked, 1024×765, 344 KB) is committed as
  part of this change. Other untracked photos in `Photos/` are left alone.

## Implementation

### tools/build_site.py

- Landing README: prepend `![Обложка](Photos/Omslag.jpg)` as the first line
  (blank line after) before `# Интернат` in the `(site_src / "README.md")`
  text. `Photos/` is already copied into the site sources, so the relative
  reference resolves in the built site. Existing `.content main img` CSS
  already renders it centered at content width.
- PDF source: tracked root file `frontispiece.tex` contains the raw LaTeX
  frontispiece block wrapped in a `\clearpage` pair:

  ```latex
  \clearpage
  \begin{center}
  \includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{Photos/Omslag.jpg}
  \end{center}
  \clearpage
  ```

  The `Build PDF` workflow step passes it to pandoc via
  `--include-before-body=frontispiece.tex`; pandoc emits it between
  `\maketitle` and `\tableofcontents`, and the `\clearpage` pair gives the
  frontispiece its own page: title page p1, frontispiece p2, table of
  contents p3. `tools/build_site.py` no longer seeds the block into
  `build/book-raw.md`. Explicit graphicx options win over the fixer's
  `\setkeys{Gin}` defaults.
- `build/book.md` (EPUB source) is unchanged — the cover comes from pandoc.

### .github/workflows/pages.yml

- Build EPUB command gains one flag:
  `--epub-cover-image=Photos/Omslag.jpg` (path relative to the repo root,
  which is the workflow cwd).
- Build PDF command gains one flag:
  `--include-before-body=frontispiece.tex` (path relative to the repo root,
  which is the workflow cwd).

## Tests

New tests in `tests/test_build_site.py`:

1. The generated landing README starts with the frontispiece line
   `![Обложка](Photos/Omslag.jpg)`.
2. `build/book-raw.md` contains no `\includegraphics` and starts with
   `# Часть 1`; the PDF frontispiece comes from the tracked `frontispiece.tex`.

Existing tests are unaffected (they assert substrings, not the whole file).
Expected suite: 37 passed.

## Verification

1. `python3 -m pytest tests/ -v` → 37 passed.
2. `identify -format '%[orientation]\n' Photos/Omslag.jpg` → `Undefined` or
   `TopLeft`; if it reports a rotation, normalize with
   `magick Photos/Omslag.jpg -auto-orient ...` before committing (same
   treatment as the earlier Bezrukov fix).
3. `python3 tools/build_site.py` and `mdbook build site` (local mdBook
   v0.5.4): `site/book/index.html` contains `src="Photos/Omslag.jpg"` and
   `site/src/README.md` starts with the frontispiece line.
4. EPUB: run the CI pandoc command plus `--epub-cover-image=Photos/Omslag.jpg`
   on `build/book.md`; the zip contains a cover page (cover.xhtml) and the
   cover image, with no pandoc warnings.
5. PDF: run the exact CI sequence on `build/book-raw.md` including
   `--include-before-body=frontispiece.tex`; `pdfimages -list build/book.pdf`
   shows the 1024×765 image on page 2, after the title page and before the
   table of contents.
6. Push (requires explicit user confirmation), then live checks: landing page
   contains the image; live EPUB zip contains the cover; live PDF shows the
   frontispiece on an early page.

## Risks

- `--include-before-body` must land between `\maketitle` and
  `\tableofcontents`; verified with pandoc 3.7. `frontispiece.tex` is tracked,
  so CI checkouts include it.
- Pandoc cover embedding requires the file to be present at the given
  relative path at build time; it is tracked, so CI checkouts include it.

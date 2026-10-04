# Book Version and Auto-Built PDF — Design

## Goal

Show the book version («Версия 0.1») on the PDF title page and the site landing
page, and rebuild the PDF automatically in CI on every push so it always
matches the chapters and contains the photos.

## Problem

- The site's `internat.pdf` is a byte copy of the tracked root `book.pdf`;
  nothing rebuilds it automatically. The current copy was compiled
  2026-10-04 13:18, before the first photos were committed (14:28), so it
  contains zero images (`pdfimages` finds none).
- Verified locally: rebuilding from the current chapters with pandoc (memoir,
  14pt, A4), `fix-manuskript-latex.py`, and pdflatex produces a 53-page PDF
  with all 10 photos, captions («Рис. 2.1: Наш класс», «Рис. 2.2: Татьяна
  Николаевна Трушанина», …), and the poems as real `verse` environments.
  Passing `-V date="Версия X"` renders the version under the author on the
  title page.
- The EPUB already rebuilds in CI from `build/book.md` (poems as blockquotes,
  photos embedded). It stays unchanged; the version is not shown there.

## Decisions (user-approved)

1. Version starts at **0.1**, stored in a new root file `VERSION` containing
   exactly `0.1`. Displayed as «Версия 0.1». Bumping the version = editing that
   one line.
2. The version appears on the **PDF title page** and the **site landing page**
   only (not EPUB).
3. The **PDF is built in CI** on every push from a new raw source. The author's
   local Manuskript/TeXstudio flow remains available for proofreading.

## Implementation

### Converter (`tools/build_site.py`)

- `build(..., version: str | None = None)`. When `version` is None, read
  `REPO_ROOT / "VERSION"` (stripped); raise `ValueError` if the file is
  missing.
- The generated landing page `site/src/README.md` gains a version line between
  the author and the blurb:

  ```markdown
  # Интернат

  **Сергей Михно**

  Версия 0.1

  Воспоминания о годах учёбы в ФМШ №18 при МГУ.

  - [Скачать PDF](internat.pdf)
  - [Скачать EPUB](internat.epub)
  ```

- New output `build/book-raw.md`: the same part/chapter assembly (parts `# `,
  chapters `## `) with chapter bodies untouched — raw `\begin{verse}` blocks
  and `Photos/<rel>` image refs preserved for the LaTeX build.
- `build/book.md` is unchanged (blockquote poems for the EPUB).

### CI (`.github/workflows/pages.yml`)

- Remove the `cp book.pdf site/book/internat.pdf` step.
- Add an `Install TeX Live` step and a `Build PDF` step after
  `Generate site sources`, before the artifact upload:

  ```yaml
  - name: Install TeX Live
    run: |
      sudo apt-get update
      sudo apt-get install -y --no-install-recommends \
        texlive-latex-base texlive-latex-recommended texlive-latex-extra \
        texlive-fonts-recommended texlive-lang-cyrillic lmodern cm-super
  - name: Build PDF
    run: |
      pandoc build/book-raw.md -s -t latex --toc --top-level-division=chapter \
        -V documentclass=memoir -V fontsize=14pt -V papersize=a4 \
        --metadata title="Интернат" --metadata author="Сергей Михно" \
        -V date="Версия $(cat VERSION)" -o build/book.tex
      python3 fix-manuskript-latex.py build/book.tex
      pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
      pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
      cp build/book.pdf site/book/internat.pdf
  ```

### Repo hygiene

- `git rm --cached book.pdf` (the local file stays on disk, untracked).
- Add to `.gitignore`: `/book.pdf`, `/book.tex`, `/book.aux`, `/book.log`,
  `/book.toc`, `/book.txt`, `/book.synctex.gz`.

### Tests (`tests/test_build_site.py`)

- Landing page contains `Версия <version>` (explicit version passed to
  `build()`).
- `VERSION`-file fallback: missing file raises `ValueError`.
- `build/book-raw.md` keeps `\begin{verse}` and `Photos/<rel>` refs while
  `build/book.md` has blockquotes and the site has figures.
- Existing tests updated for the new README line.

## Verification

1. `python3 -m pytest tests/` — all tests pass.
2. Local end-to-end: run the converter, then the exact CI PDF commands;
   `pdfinfo` shows > 41 pages, `pdfimages -list` shows ≥ 10 images, and the
   first page text contains «Версия 0.1».
3. Push (user confirms) → workflow green (first run may need extra TeX
   packages; iterate until it builds).
4. Live: `/` shows «Версия 0.1»; `/internat.pdf` is 200 and freshly built
   (contains images and «Версия 0.1»); `/internat.epub` still 200.

## Out of scope

- Version inside the EPUB, cover images, changes to the Manuskript project,
  changing the author's local TeXstudio flow.

## Risks

- CI pandoc is the distro 3.1.x while local verification uses 3.7.0.2;
  template output may differ slightly — check the first CI PDF.
- The apt TeX package list may need additions; iterate until pdflatex
  succeeds in CI.

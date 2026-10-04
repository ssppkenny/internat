# Book Site for «Интернат» — Design

Date: 2026-10-04
Repo: https://github.com/ssppkenny/internat (branch `master`)
Author contact in book metadata: Сергей Михно, sergey.mikhno@gmail.com

## Context

- The book «Интернат» is a Russian-language memoir.
- Source of truth is the Manuskript project directory `internat/`:
  - `internat/outline/<n>-<Название>/folder.txt` — part metadata, first line `title:          Часть N`
  - `internat/outline/<n>-<Название>/<m>-<Название>.md` — chapters; each begins with a
    plain-text front matter of `key: value` lines (`title`, `ID`, `type`, `compile`,
    `charCount`) followed by a blank line, then the body.
- Content: 5 parts, 24 chapters:
  - Часть 1: Поступление, Зима в Москве, Adidas
  - Часть 2: Учеба, Физкультура, Лыжи, Бег, Фанта, Литература, Стихи, Театр,
    Контролер, Программирование, Споры и конфликты, Чистота и порядок
  - Часть 3: Магнитофон, Музыка, Тото Кутуньо
  - Часть 4: Друг из Краснодара, Шведские студенты, Как сельди в бочке
  - Часть 5: Армия, Шинель, Прописка
- Generated artifacts at repo root: `book.pdf` (tracked in git, fresh), plus untracked
  `book.tex`, `book.txt`, `book.log`, `book.aux`, `book.toc`, `book.synctex.gz`.
- `fix-manuskript-latex.py` post-processes LaTeX exports; unrelated to this project.
- User wants a GitHub Pages book site built from the Manuskript chapters: full book
  readable online plus PDF/EPUB downloads.

## Goal and success criteria

1. Push to `master` (or manual dispatch) builds and deploys the site to
   https://ssppkenny.github.io/internat/ .
2. Sidebar shows the 5 parts and 24 chapters in correct order; chapter text renders
   fully; built-in full-text search works (Cyrillic input included).
3. Landing page shows book title, author, and download links for PDF and EPUB.
4. Future edits to files under `internat/outline/` appear on the site after a push,
   with no manual build steps.
5. Manuskript source files are never modified.

## Non-goals

- No cover image (text-only title page). A cover can be added later.
- No comments, analytics, custom domain, EPUB/print layout customization.
- No PDF regeneration in CI; the tracked `book.pdf` is copied as-is.
- No changes to `book.tex`/`fix-manuskript-latex.py` workflows.

## Architecture

```text
internat/outline/  ──►  tools/build_site.py  ──►  site/src/**  ──►  mdbook build  ──►  site/book/  ──►  Pages
 (source of truth)       (converter)               (generated)       (mdBook)          (HTML + files)
```

### Repository layout (added)

```text
.github/workflows/pages.yml   # build + deploy workflow
tools/build_site.py           # Manuskript -> mdBook converter
site/book.toml                # mdBook config
site/theme/custom.css         # reading typography
site/src/                     # GENERATED, gitignored
.gitignore                    # gains: site/src/, site/book/, build/
```

### Converter `tools/build_site.py`

Pure standard library. Algorithm:

1. Find part directories: direct children of `internat/outline/` whose name starts
   with digits; order by the leading integer.
2. Part title: value of the `title:` line in that directory's `folder.txt`.
3. Chapters: `*.md` files in the part directory, ordered by leading integer in the
   filename. Chapter title: value of the `title:` line in the file's front matter.
4. Body: skip all leading lines matching `^[A-Za-z]+:`; skip the following blank
   line(s); keep the remainder unchanged (markdown as written in Manuskript).
5. Slug: transliterate Cyrillic to ASCII, lowercase, replace non `[a-z0-9]` runs with
   `-`, trim `-`. Deduplicate within a part by appending `-2`, `-3`, ... to collisions.
6. Write `site/src/part<N>/<slug>.md` as `# {chapter title}\n\n{body}\n`.
7. Write `site/src/SUMMARY.md`:

   ```markdown
   # Summary

   [Интернат](README.md)

   # Часть 1

   - [Поступление](part1/postuplenie.md)
   ...
   ```

   Part headings use SUMMARY.md `#` part-title syntax (non-clickable section headers).
8. Write `site/src/README.md` title page:

   ```markdown
   # Интернат

   **Сергей Михно**

   Воспоминания о годах учёбы в ФМШ №18 при МГУ.

   - [Скачать PDF](internat.pdf)
   - [Скачать EPUB](internat.epub)
   ```

9. Write `build/book.md` — all parts/chapters concatenated with `# Часть N` and
   `## Chapter` headings — as input for the EPUB step.
10. Fail with a nonzero exit and a clear message if any part or chapter has no title,
    or if a chapter body is empty.

Output is deterministic; `site/src/` and `build/` are gitignored and regenerated on
every build.

### Site configuration `site/book.toml`

- `title = "Интернат"`, `authors = ["Сергей Михно"]`, `language = "ru"`,
  `src = "src"`, `site-url = "https://ssppkenny.github.io/internat"`.
- `[output.html]`: `additional-css = ["theme/custom.css"]`.
- `site/theme/custom.css`: reading typography only — serif body font stack
  (`Literata`, `PT Serif`, `Georgia`, serif), justified text, comfortable line
  height and content width, styled part headings. mdBook native light/dark themes
  and menu remain.

### CI/CD `.github/workflows/pages.yml`

- Triggers: `push` to `master`, `workflow_dispatch`.
- Permissions: `contents: read`, `pages: write`, `id-token: write`; concurrency
  group `pages` with `cancel-in-progress: false`.
- Build job (ubuntu-latest):
  1. `actions/checkout`
  2. `actions/setup-python` (3.12)
  3. Install pinned mdBook release binary `mdbook-v0.5.4-x86_64-unknown-linux-gnu.tar.gz`
     from the official `rust-lang/mdBook` GitHub release, downloaded with `curl`.
  4. `python3 tools/build_site.py`
  5. `mdbook build site` (output `site/book/`)
  6. `pandoc build/book.md -o site/book/internat.epub --toc --metadata title="Интернат"
     --metadata author="Сергей Михно" --metadata lang=ru` (pandoc is preinstalled on
     ubuntu-latest; `apt-get install -y pandoc` fallback if not).
  7. `cp book.pdf site/book/internat.pdf`
  8. `actions/upload-pages-artifact` on `site/book`
- Deploy job: `actions/deploy-pages`.

### GitHub Pages enablement

Repo Pages settings must use "GitHub Actions" as the source. Done once during
implementation via `gh api` (`POST`/`PUT /repos/ssppkenny/internat/pages` with
`build_type=workflow`). `gh` is authenticated as `ssppkenny` (owner).

## Error handling

- Converter exits nonzero with a descriptive message for missing titles/empty bodies;
  the workflow fails and the previous site stays live.
- Excerpt/link generation is absent, so no risk of broken cross-links beyond the
  two download links, which are produced in step 7 of CI.

## Verification

Local (before pushing):

1. `python3 tools/build_site.py`; inspect `site/src/SUMMARY.md`: 5 part headings,
   24 chapter links in order; `grep -r "charCount" site/src/` returns nothing;
   every generated file starts with its `#` title.
2. Build with a local mdBook binary (downloaded to `/tmp/opencode`):
   `mdbook build site`; confirm `site/book/index.html`, every chapter HTML exists,
   and `site/book/searchindex.js` is non-empty and contains Cyrillic titles.
3. `pandoc build/book.md -o /tmp/opencode/internat.epub --toc` succeeds; EPUB is a
   valid zip.
4. Optionally `mdbook serve site` for visual spot-check.

After push:

5. `gh run watch` until the workflow succeeds.
6. `curl -sI https://ssppkenny.github.io/internat/` returns 200; spot-check one
   chapter URL and `internat.pdf` / `internat.epub` return 200.

## Risks and mitigations

- Cyrillic filenames in `internat/outline/` are unreliable on some tools; converter
  uses numeric filename prefixes only for ordering and takes titles from file
  contents, never from filenames.
- Slug collisions: deduplicated in the converter.
- mdBook binary version drift: pinned release version in the workflow.
- Pages enablement may require repo-admin rights failure: `gh` user is the owner;
  if API rejects, fall back to documented manual Settings → Pages step (printed to
  the user).

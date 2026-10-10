# Frontispiece Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show `Photos/Omslag.jpg` as a frontispiece on the site landing page, as the first page of the PDF, and as the official cover image of the EPUB.

**Architecture:** The converter (`tools/build_site.py`) prepends a Markdown image line to the landing `README.md` and a raw LaTeX `includegraphics` block to `build/book-raw.md`; the CI workflow passes `--epub-cover-image=Photos/Omslag.jpg` to pandoc. The untracked photo is committed with the change. No CSS change is needed (the existing `.content main img` rule already centers images at content width).

**Tech Stack:** Python stdlib converter + pytest; mdBook v0.5.4; pandoc; pdflatex (TinyTeX locally, TeX Live in CI).

## Global Constraints

- Landing frontispiece line is exactly `![Обложка](Photos/Omslag.jpg)` as the FIRST line of `site/src/README.md`, followed by a blank line and then `# Интернат`.
- No caption under the landing image; no new CSS.
- PDF frontispiece is exactly this raw LaTeX block, prepended to `build/book-raw.md` before the first part heading (title page stays first):
  ```
  \begin{center}
  \includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{Photos/Omslag.jpg}
  \end{center}
  ```
- EPUB: add exactly `--epub-cover-image=Photos/Omslag.jpg \` to the CI `Build EPUB` pandoc command; no other workflow change.
- `Photos/Omslag.jpg` (1024x765, orientation Undefined, 344248 B) is ALREADY tracked (author commit `10a59f9`); do not modify or re-add it.
- Never modify `internat/outline/` or any other file under `Photos/`; do not stage the untracked Photos files (`46b8f8f8-...jpeg`, `Sputnik.jpg`, `im-invsample.svg`, `spezial.avif`); the working tree is otherwise clean.
- No converter-time existence validation for the frontispiece; a missing file fails loudly in CI at pandoc/pdflatex.
- Tests run from repo root: `python3 -m pytest tests/ -v`; expected `37 passed` (35 existing + 2 new).
- Short imperative commit messages; push and live verification gated on explicit user confirmation.

---

### Task 1: Frontispiece in converter (landing + PDF) and commit the photo

**Files:**
- Modify: `tools/build_site.py` (README write at lines 296-305; `raw_book_lines` init at line 250)
- Test: `tests/test_build_site.py` (append 2 tests)

**Interfaces:**
- Consumes: existing `build(outline_dir, site_src, build_dir, photos_dir, version=None, last_changed=None)`; `raw_book_lines` accumulates raw markdown written to `build/book-raw.md` (line 307).
- Produces: `site/src/README.md` starting with the frontispiece line; `build/book-raw.md` starting with the raw LaTeX center block. Task 2's EPUB/PDF CI consumes both.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_site.py`:

```python
def test_readme_starts_with_frontispiece(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    readme = (tmp_path / "src" / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("![Обложка](Photos/Omslag.jpg)\n\n# Интернат\n\n")


def test_book_raw_has_frontispiece_before_first_part(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    raw = (tmp_path / "build" / "book-raw.md").read_text(encoding="utf-8")
    assert raw.startswith(
        "\\begin{center}\n"
        "\\includegraphics[width=\\linewidth,height=0.75\\textheight,keepaspectratio]{Photos/Omslag.jpg}\n"
        "\\end{center}\n"
    )
    assert raw.index("\\includegraphics") < raw.index("# Часть 1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_build_site.py::test_readme_starts_with_frontispiece tests/test_build_site.py::test_book_raw_has_frontispiece_before_first_part -v`
Expected: FAIL — both `AssertionError` (README starts with `# Интернат`; raw starts with `# Часть 1`).

- [ ] **Step 3: Implement the converter changes**

In `tools/build_site.py`, replace the `raw_book_lines` initialization (currently line 250):

```python
    raw_book_lines: list[str] = [
        "\\begin{center}\n"
        "\\includegraphics[width=\\linewidth,height=0.75\\textheight,keepaspectratio]{Photos/Omslag.jpg}\n"
        "\\end{center}\n",
    ]
```

In the README write (currently line 296), prepend the image line:

```python
    (site_src / "README.md").write_text(
        "![Обложка](Photos/Omslag.jpg)\n\n"
        "# Интернат\n\n"
        "**Сергей Михно**\n\n"
        f"Версия {version}\n\n"
        f"Обновлено {format_date_ru(last_changed)}\n\n"
        "Воспоминания о годах учёбы в ФМШ №18 при МГУ.\n\n"
        "- [Скачать PDF](internat.pdf)\n"
        "- [Скачать EPUB](internat.epub)\n",
        encoding="utf-8",
    )
```

No other converter change.

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest tests/ -v`
Expected: `37 passed`.

- [ ] **Step 5: Verify against the real repo**

Run: `identify -format '%[orientation]\n' Photos/Omslag.jpg`
Expected: `Undefined` (no EXIF rotation; nothing to normalize).

Run: `python3 tools/build_site.py`
Expected: writes all chapters (`Wrote 26 chapters` at plan time) with no error.

Run: `head -3 site/src/README.md` and `head -3 build/book-raw.md`
Expected: README line 1 `![Обложка](Photos/Omslag.jpg)`; book-raw line 1 `\begin{center}`.

Run: `/tmp/opencode/mdbook-dist/mdbook build site` then `rg -o 'src="Photos/Omslag.jpg"' site/book/index.html`
Expected: mdBook exits 0 and prints one `<img ... src="Photos/Omslag.jpg" ...>` occurrence on the landing page.

- [ ] **Step 6: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py
git commit -m "Add frontispiece to landing and PDF"
```

Verify the commit contains exactly those two paths (`git show --stat HEAD`); the untracked Photos files must remain unstaged.

---

### Task 2: EPUB cover image and local end-to-end verification

**Files:**
- Modify: `.github/workflows/pages.yml` (`Build EPUB` step, lines 51-56)

**Interfaces:**
- Consumes: `Photos/Omslag.jpg` committed in Task 1; `build/book.md`, `build/book-raw.md` from Task 1's converter.
- Produces: CI EPUB built with the official cover; PDF pipeline unchanged.

- [ ] **Step 1: Edit the workflow**

Replace the `Build EPUB` step with:

```yaml
      - name: Build EPUB
        run: |
          pandoc build/book.md -o site/book/internat.epub --toc \
            --epub-cover-image=Photos/Omslag.jpg \
            --metadata title="Интернат" \
            --metadata author="Сергей Михно" \
            --metadata lang=ru
```

No other workflow line changes.

- [ ] **Step 2: Validate YAML and rebuild sources**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml')); print('yaml-ok')"`
Expected: `yaml-ok`.

Run: `python3 tools/build_site.py`
Expected: `Wrote 26 chapters ...` (count at plan time).

- [ ] **Step 3: Verify the EPUB cover locally**

Run:

```bash
pandoc build/book.md -o /tmp/opencode/frontispiece.epub --toc \
  --epub-cover-image=Photos/Omslag.jpg \
  --metadata title="Интернат" \
  --metadata author="Сергей Михно" \
  --metadata lang=ru
unzip -l /tmp/opencode/frontispiece.epub | rg -i 'cover'
```

Expected: listing includes `EPUB/images/cover.jpg` and `EPUB/cover.xhtml` (pandoc also writes a `<meta name="cover">` in `content.opf`). No pandoc warnings.

- [ ] **Step 4: Verify the PDF frontispiece locally with the exact CI commands**

From repo root:

```bash
pandoc build/book-raw.md -s -t latex --toc --top-level-division=chapter \
  -V documentclass=memoir -V fontsize=14pt -V papersize=a4 \
  --metadata title="Интернат" \
  --metadata author="Сергей Михно" \
  -V date="Версия $(cat VERSION)" \
  -o build/book.tex
python3 fix-manuskript-latex.py build/book.tex
pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
pdfimages -list build/book.pdf | head -5
```

Expected: `pdflatex` exits 0 both times; `pdfimages` first listed image is `1024 765` on page 2 (page 1 is the title page); no LaTeX errors.

- [ ] **Step 5: Run the full suite once more**

Run: `python3 -m pytest tests/ -v`
Expected: `37 passed`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "Add frontispiece cover to EPUB"
```

`git show --stat HEAD` must list only `.github/workflows/pages.yml`.

---

### Task 3: Push and live verification (requires user confirmation)

**Files:**
- None (ops only).

**Interfaces:**
- Consumes: commits from Tasks 1-2 pushed to `origin/master`.

- [ ] **Step 1: Ask the user for confirmation to push** (required gate; do not push otherwise).

- [ ] **Step 2: Push and watch**

```bash
git push origin master
gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

Expected: run succeeds (build + deploy).

- [ ] **Step 3: Live checks**

```bash
curl -s "https://ssppkenny.github.io/internat/?cb=$(date +%s)" | grep -o 'src="Photos/Omslag.jpg"' | head -1
curl -sI "https://ssppkenny.github.io/internat/Photos/Omslag.jpg" | head -1
curl -s -o /tmp/opencode/live.epub "https://ssppkenny.github.io/internat/internat.epub" && unzip -l /tmp/opencode/live.epub | grep -i cover
curl -s -o /tmp/opencode/live.pdf "https://ssppkenny.github.io/internat/internat.pdf" && pdfimages -list /tmp/opencode/live.pdf | head -5
```

Expected: landing contains `src="Photos/Omslag.jpg"`; photo URL 200; EPUB lists `cover`; PDF's first image is 1024x765 on page 2; all downloads 200.

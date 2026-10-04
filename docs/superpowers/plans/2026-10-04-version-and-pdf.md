# Version Display and Automatic PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show «Версия 0.1» on the PDF title page and the site landing page, and rebuild the PDF in CI from a raw verse-preserving source so it always contains the photos.

**Architecture:** The converter gains a `version` parameter (read from a root `VERSION` file) and writes a new `build/book-raw.md` with untouched chapter bodies (verse environments and `Photos/` refs intact); `build/book.md` stays blockquote/plain-markdown for the EPUB. The Pages workflow stops copying the tracked `book.pdf` and instead builds `build/book.tex` with pandoc + `fix-manuskript-latex.py` + `pdflatex` twice. `book.pdf` becomes untracked.

**Tech Stack:** Python 3.12 stdlib + pytest; mdBook v0.5.4; pandoc (CI: distro, local: 3.7.0.2 at `~/.local/bin/pandoc`); TeX Live / pdflatex (local TinyTeX, CI apt); GitHub Actions Pages.

**Spec:** `docs/superpowers/specs/2026-10-04-version-and-pdf-design.md`

## Global Constraints

- Version source: `VERSION` at repo root, content exactly `0.1`; displayed as `Версия 0.1` (single space).
- Version appears on the PDF title page (`-V date="Версия $(cat VERSION)"`) and on the site landing page only — NOT in the EPUB.
- PDF is built from `build/book-raw.md` (raw bodies: `\begin{verse}` environments intact, `Photos/<rel>` refs raw); `build/book.md` stays blockquote/plain-markdown for EPUB — no behavior change there.
- Exact CI PDF commands (run from repo root):
  `pandoc build/book-raw.md -s -t latex --toc --top-level-division=chapter -V documentclass=memoir -V fontsize=14pt -V papersize=a4 --metadata title="Интернат" --metadata author="Сергей Михно" -V date="Версия $(cat VERSION)" -o build/book.tex`, then `python3 fix-manuskript-latex.py build/book.tex`, then `pdflatex -interaction=nonstopmode -output-directory=build build/book.tex` twice, then `cp build/book.pdf site/book/internat.pdf`.
- Never modify `internat/outline/` or `Photos/`.
- Converter stays stdlib-only (no new imports).
- Missing `VERSION` file → `ValueError` with `missing version file`, exit 1 via existing `main()` handling.
- `book.pdf` untracked: `git rm --cached book.pdf` plus `.gitignore` entries `/book.pdf`, `/book.tex`, `/book.aux`, `/book.log`, `/book.toc`, `/book.txt`, `/book.synctex.gz`.
- Short imperative commit messages. Pushing to master requires user confirmation at execution time.
- Tests run from repo root: `python3 -m pytest tests/ -v` (18 expected after Task 1).

---

### Task 1: Version and raw PDF source in the converter

**Files:**
- Create: `VERSION`
- Modify: `tools/build_site.py`
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: existing `build(outline_dir, site_src, build_dir, photos_dir)` and helpers from earlier work.
- Produces: `VERSION_FILE` module constant; `read_version() -> str`; `build(..., version: str | None = None)`; new generated file `build/book-raw.md`. Task 2's CI relies on `build/book-raw.md` and `VERSION`.

- [ ] **Step 1: Create `VERSION`**

Write file `VERSION` with content:

```
0.1
```

- [ ] **Step 2: Write the failing tests**

In `tests/test_build_site.py`, add `import tools.build_site as build_site` after `from tools.build_site import build`, include `"Версия 0.1"` in the README test, and append these three tests:

```python
def test_readme_has_version(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    readme = (tmp_path / "src" / "README.md").read_text(encoding="utf-8")
    assert "**Сергей Михно**\n\nВерсия 0.1\n\n" in readme


def test_missing_version_file_fails(
    outline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build_site, "VERSION_FILE", tmp_path / "VERSION")
    with pytest.raises(ValueError, match="missing version file"):
        build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")


def test_book_raw_keeps_verse_and_photo_refs(outline: Path, tmp_path: Path) -> None:
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "pic.jpg").write_bytes(b"img")
    body = (
        "Проза.\n\n"
        "\\begin{verse}\n"
        "Строка.\\\\\n"
        "\\end{verse}\n\n"
        "![Снимок](Photos/pic.jpg)"
    )
    write_chapter(outline / "0-Часть 1" / "0-Поступление.md", "Поступление", body)
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=photos)
    raw = (tmp_path / "build" / "book-raw.md").read_text(encoding="utf-8")
    assert "\\begin{verse}" in raw
    assert "\\end{verse}" in raw
    assert "Строка.\\\\" in raw
    assert "![Снимок](Photos/pic.jpg)" in raw
    assert "<figure>" not in raw
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "\\begin{verse}" not in book
    assert "> Строка." in book
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/ -v`
Expected: FAIL — `test_readme_has_version` (no version line), `test_missing_version_file_fails` (`VERSION_FILE` missing → fixture path is the real repo, read succeeds; then ValueError not raised), `test_book_raw_keeps_verse_and_photo_refs` (no `book-raw.md`).

- [ ] **Step 4: Implement the converter changes**

In `tools/build_site.py`, add the constant after `PHOTOS_DIR = REPO_ROOT / "Photos"`:

```python
VERSION_FILE = REPO_ROOT / "VERSION"
```

Add this function after `slugify`:

```python
def read_version() -> str:
    if not VERSION_FILE.is_file():
        raise ValueError(f"{VERSION_FILE}: missing version file")
    return VERSION_FILE.read_text(encoding="utf-8").strip()
```

Change the `build` signature and add version resolution at the top of the body:

```python
def build(
    outline_dir: Path = OUTLINE_DIR,
    site_src: Path = SITE_SRC,
    build_dir: Path = BUILD_DIR,
    photos_dir: Path = PHOTOS_DIR,
    version: str | None = None,
) -> None:
    if version is None:
        version = read_version()
    if not outline_dir.is_dir():
        raise ValueError(f"{outline_dir}: not a directory")
```

Add a raw output accumulator next to `book_lines`:

```python
    book_lines: list[str] = []
    raw_book_lines: list[str] = []
```

In the part loop, right after `book_lines += [f"# {part_title}", ""]`, add:

```python
        raw_book_lines += [f"# {part_title}", ""]
```

In the chapter loop, capture the raw body before the verse transform. Replace:

```python
            validate_images(body, chapter_path, photos_dir)
            body = convert_verse_blocks(body)
```

with:

```python
            validate_images(body, chapter_path, photos_dir)
            raw_body = body
            body = convert_verse_blocks(body)
```

and after `book_lines += [f"## {chapter_title}", "", body, ""]` add:

```python
            raw_book_lines += [f"## {chapter_title}", "", raw_body, ""]
```

Add the version line to the landing README — replace the `(site_src / "README.md").write_text(...)` call with:

```python
    (site_src / "README.md").write_text(
        "# Интернат\n\n"
        "**Сергей Михно**\n\n"
        f"Версия {version}\n\n"
        "Воспоминания о годах учёбы в ФМШ №18 при МГУ.\n\n"
        "- [Скачать PDF](internat.pdf)\n"
        "- [Скачать EPUB](internat.epub)\n",
        encoding="utf-8",
    )
```

After the `book.md` write, add:

```python
    (build_dir / "book-raw.md").write_text("\n".join(raw_book_lines), encoding="utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/ -v`
Expected: `18 passed`.

- [ ] **Step 6: Verify against the real corpus**

Run: `python3 tools/build_site.py && grep -c 'begin{verse}' build/book-raw.md && grep -c 'begin{verse}' build/book.md; grep 'Версия 0.1' site/src/README.md`
Expected: `Wrote 24 chapters ...`; `11` (raw keeps all verse blocks); `0` or grep exit 1 for `book.md` (no verse left); README line `Версия 0.1`.

- [ ] **Step 7: Commit**

```bash
git add VERSION tools/build_site.py tests/test_build_site.py
git commit -m "Add version and raw PDF source"
```

---

### Task 2: CI PDF build and repo hygiene

**Files:**
- Modify: `.github/workflows/pages.yml`
- Modify: `.gitignore`
- Remove from index: `book.pdf` (file stays on disk)

**Interfaces:**
- Consumes: `build/book-raw.md`, `VERSION`, `fix-manuskript-latex.py` from Task 1.
- Produces: CI-built `site/book/internat.pdf`; `book.pdf` untracked.

- [ ] **Step 1: Update the workflow**

In `.github/workflows/pages.yml`, replace the `Copy PDF` step (currently lines 47-48) with:

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
            --metadata title="Интернат" \
            --metadata author="Сергей Михно" \
            -V date="Версия $(cat VERSION)" \
            -o build/book.tex
          python3 fix-manuskript-latex.py build/book.tex
          pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
          pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
          cp build/book.pdf site/book/internat.pdf
```

Leave the `Build EPUB` and upload steps untouched.

- [ ] **Step 2: Validate the workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml')); print('yaml-ok')"`
Expected: `yaml-ok`.

- [ ] **Step 3: Untrack the PDF and ignore root artifacts**

Append to `.gitignore`:

```
/book.pdf
/book.tex
/book.aux
/book.log
/book.toc
/book.txt
/book.synctex.gz
```

Run: `git rm --cached book.pdf`

- [ ] **Step 4: Verify end-to-end locally with the exact CI commands**

From the repo root (local pandoc 3.7.0.2; commands identical to CI):

```bash
python3 tools/build_site.py
pandoc build/book-raw.md -s -t latex --toc --top-level-division=chapter \
  -V documentclass=memoir -V fontsize=14pt -V papersize=a4 \
  --metadata title="Интернат" --metadata author="Сергей Михно" \
  -V date="Версия $(cat VERSION)" -o build/book.tex
python3 fix-manuskript-latex.py build/book.tex
pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
cp build/book.pdf site/book/internat.pdf
pdfinfo build/book.pdf | grep '^Pages'
pdfimages -list build/book.pdf | wc -l
pdftotext -f 1 -l 1 build/book.pdf - | grep 'Версия 0.1'
```

Expected: `Wrote 24 chapters`; `fixed build/book.tex`; two `pdflatex` exits 0; `Pages:` > 41; image listing line count >= 11 (header + 10 photos); first-page text contains `Версия 0.1`.

- [ ] **Step 5: Confirm tests still pass and hygiene is right**

Run: `python3 -m pytest tests/ -v; git ls-files book.pdf; git check-ignore book.pdf book.tex`
Expected: `18 passed`; no output from `git ls-files book.pdf`; both paths echoed by `git check-ignore`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pages.yml .gitignore
git add -u book.pdf
git commit -m "Build PDF in CI"
```

---

### Task 3: Push and verify live (user confirmation required)

**Files:** none (deployment only)

**Interfaces:**
- Consumes: all commits from Tasks 1-2, pushed to `origin/master`.
- Produces: live site with version + fresh PDF.

- [ ] **Step 1: Final local test run**

Run: `python3 -m pytest tests/ -v`
Expected: `18 passed`.

- [ ] **Step 2: Ask the user to confirm the push** (never push before it)

- [ ] **Step 3: Push**

Run: `git push origin master`

- [ ] **Step 4: Watch the workflow**

Run: `gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status`
Expected: exit 0 (if CI fails on apt packages, iterate the TeX Live list and re-push).

- [ ] **Step 5: Verify live**

```bash
curl -fsS https://ssppkenny.github.io/internat/ | grep -o 'Версия 0.1'
curl -fsS -o /tmp/internat-live.pdf https://ssppkenny.github.io/internat/internat.pdf
pdfinfo /tmp/internat-live.pdf | grep '^Pages'
pdfimages -list /tmp/internat-live.pdf | wc -l
pdftotext -f 1 -l 1 /tmp/internat-live.pdf - | grep 'Версия 0.1'
curl -fsS -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.epub
curl -fsS -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/part2/ucheba.html
```

Expected: `Версия 0.1` on the landing page; live PDF `Pages:` > 41, >= 11 image-listing lines, first page contains `Версия 0.1`; `200` for EPUB and the spot chapter page.

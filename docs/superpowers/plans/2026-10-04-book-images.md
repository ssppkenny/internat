# Book Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chapter photos (`![Подпись](Photos/имя.jpg)`) appear correctly in the mdBook site, the EPUB, and the regenerated PDF.

**Architecture:** The Manuskript chapters stay untouched; `tools/build_site.py` grows a `photos_dir` parameter that validates every `Photos/…` reference, rewrites site copies to `../Photos/…`, keeps `build/book.md` refs as `Photos/…` (pandoc runs from the repo root), and copies `Photos/` into `site/src/`. `fix-manuskript-latex.py` inserts LaTeX image sizing so every included photo fits the page.

**Tech Stack:** Python 3 stdlib + pytest; mdBook v0.5.4 (local binary at `/tmp/opencode/mdbook-dist/mdbook`, CI downloads the same version); pandoc 3.7.0.2 (`~/.local/bin/pandoc`).

**Spec:** `docs/superpowers/specs/2026-10-04-book-images-design.md` (committed `911517c`; path depth corrected in a follow-up commit).

## Global Constraints

- Never modify `internat/outline/` or `Photos/` — author-owned sources. The only existing reference is `internat/outline/1------_2/00------.md:10` (`![Наш класс](Photos/class.jpg)`, chapter «Учеба» → `part2/ucheba.md`).
- Author convention: `![Подпись](Photos/имя.jpg)`, path relative to the repository root, case-sensitive Latin names, no spaces.
- Site chapter copies must reference exactly `../Photos/<rel>` (one level up). Verified against mdBook v0.5.4: chapter HTML keeps that path and `print.html` rewrites it to `Photos/<rel>` from the output root; both resolve.
- `build/book.md` keeps `Photos/<rel>` unchanged; CI command runs from the repo root: `pandoc build/book.md -o site/book/internat.epub --toc --metadata title="Интернат" --metadata author="Сергей Михно" --metadata lang=ru`.
- A referenced file that does not exist must raise `ValueError(f"{chapter_path}: missing image Photos/<rel>")` and fail the build (exit 1 via `main()`).
- `photos_dir` does not exist and no references → build behaves exactly as before (no error).
- `tools/build_site.py` stays stdlib-only. Do not commit generated `site/src/`, `site/book/`, `build/` (already gitignored).
- `Photos/` is already committed (12 files); do not re-add it.
- Commit messages: short imperative, no prefix (repo style).
- Pushing to `master` (Pages deploy) requires explicit user confirmation at execution time.

---

### Task 1: Converter image support

**Files:**
- Modify: `tools/build_site.py`
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: existing `build()`, `strip_front_matter()`, and the `outline`/`tmp_path` test fixture + `write_chapter` helper.
- Produces: `PHOTOS_DIR: Path`, `IMG_RE: re.Pattern[str]`, `validate_images(body: str, chapter_path: Path, photos_dir: Path) -> None`, `rewrite_image_refs(body: str) -> str`, and `build(..., photos_dir: Path = PHOTOS_DIR)`.

- [ ] **Step 1: Update existing tests and add the new image tests**

In `tests/test_build_site.py`, replace all seven occurrences of:

```python
    build(outline, tmp_path / "src", tmp_path / "build")
```

with:

```python
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
```

(The calls are inside `test_summary_parts_and_chapters_in_order`, `test_front_matter_stripped`, `test_duplicate_slugs_deduped`, `test_epub_source_concatenated`, `test_readme_has_download_links`, `test_missing_title_fails`, `test_empty_title_fails`.)

Append to the same file:

```python
def test_photos_rewritten_and_copied(outline: Path, tmp_path: Path) -> None:
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "pic.jpg").write_bytes(b"img")
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "Первый текст.\n\n![Снимок](Photos/pic.jpg)",
    )
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=photos)
    site = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    assert "![Снимок](../Photos/pic.jpg)" in site
    assert (tmp_path / "src" / "Photos" / "pic.jpg").read_bytes() == b"img"
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "![Снимок](Photos/pic.jpg)" in book


def test_dot_slash_image_ref_rewritten(outline: Path, tmp_path: Path) -> None:
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "pic.jpg").write_bytes(b"img")
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "![Снимок](./Photos/pic.jpg)",
    )
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=photos)
    site = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    assert "![Снимок](../Photos/pic.jpg)" in site


def test_missing_photo_fails(outline: Path, tmp_path: Path) -> None:
    write_chapter(
        outline / "0-Часть 1" / "0-Поступление.md",
        "Поступление",
        "![Снимок](Photos/nope.jpg)",
    )
    with pytest.raises(ValueError, match="missing image Photos/nope.jpg"):
        build(
            outline,
            tmp_path / "src",
            tmp_path / "build",
            photos_dir=tmp_path / "Photos",
        )


def test_no_photos_dir_no_refs_builds(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    assert (tmp_path / "src" / "SUMMARY.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_build_site.py -v`
Expected: all tests FAIL with `TypeError: build() got an unexpected keyword argument 'photos_dir'`.

- [ ] **Step 3: Implement image support in `tools/build_site.py`**

Add below `BUILD_DIR` (after line 14):

```python
PHOTOS_DIR = REPO_ROOT / "Photos"
```

Add below the `TRANSLIT` dict (after line 22):

```python
IMG_RE = re.compile(r"\]\((?:\./)?Photos/([^)\s]+)\)")
```

Add after `slugify` (after line 54):

```python
def validate_images(body: str, chapter_path: Path, photos_dir: Path) -> None:
    for match in IMG_RE.finditer(body):
        rel = match.group(1)
        if not (photos_dir / rel).is_file():
            raise ValueError(f"{chapter_path}: missing image Photos/{rel}")


def rewrite_image_refs(body: str) -> str:
    return IMG_RE.sub(r"](../Photos/\1)", body)
```

Change the `build()` signature (lines 75-79) to:

```python
def build(
    outline_dir: Path = OUTLINE_DIR,
    site_src: Path = SITE_SRC,
    build_dir: Path = BUILD_DIR,
    photos_dir: Path = PHOTOS_DIR,
) -> None:
```

After `build_dir.mkdir(parents=True, exist_ok=True)` (line 86) add:

```python
    if photos_dir.is_dir():
        shutil.copytree(photos_dir, site_src / "Photos")
```

After the empty-body check (after line 106) add:

```python
            validate_images(body, chapter_path, photos_dir)
```

Change the site chapter write (lines 116-118) to:

```python
            (site_src / part_slug / f"{candidate}.md").write_text(
                f"# {chapter_title}\n\n{rewrite_image_refs(body)}\n", encoding="utf-8"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_build_site.py -v`
Expected: 11 passed.

- [ ] **Step 5: Verify against the real corpus and mdBook**

Run:

```bash
python3 tools/build_site.py
```

Expected: `Wrote 24 chapters to .../site/src`.

Then run:

```bash
test -f site/src/Photos/class.jpg
rg -n "class.jpg" site/src/part2/ucheba.md
rg -n "class.jpg" build/book.md
PATH="/tmp/opencode/mdbook-dist:$PATH" mdbook build site
test -f site/book/Photos/class.jpg
rg -o 'src="[^"]*class.jpg"' site/book/part2/ucheba.html
```

Expected: both `rg` hits on the site copy show `![Наш класс](../Photos/class.jpg)`; the book.md hit shows `![Наш класс](Photos/class.jpg)`; mdBook exits 0; the HTML hit shows `src="../Photos/class.jpg"`.

- [ ] **Step 6: Verify the EPUB embeds the photo**

Run the exact CI command locally:

```bash
~/.local/bin/pandoc build/book.md -o /tmp/opencode/images-check.epub --toc \
  --metadata title="Интернат" \
  --metadata author="Сергей Михно" \
  --metadata lang=ru
unzip -l /tmp/opencode/images-check.epub | rg class.jpg
```

Expected: an `EPUB/media/...class.jpg` entry.

- [ ] **Step 7: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py
git commit -m "Add image support to site converter"
```

---

### Task 2: Style chapter images on the site

**Files:**
- Modify: `site/theme/custom.css`

**Interfaces:**
- Consumes: nothing from Task 1 (pure CSS).
- Produces: nothing code-level.

- [ ] **Step 1: Append the image rule**

Append to the end of `site/theme/custom.css`:

```css
.content main img {
    display: block;
    max-width: 100%;
    height: auto;
    margin: 1em auto;
}
```

- [ ] **Step 2: Rebuild the site**

Run:

```bash
python3 tools/build_site.py && PATH="/tmp/opencode/mdbook-dist:$PATH" mdbook build site
```

Expected: converter prints `Wrote 24 chapters`, mdBook exits 0.

- [ ] **Step 3: Verify the built CSS contains the rule**

Run:

```bash
rg -n "max-width: 100%" site/book/theme/
```

Expected: one hit in `site/book/theme/custom-<hash>.css`.

- [ ] **Step 4: Commit**

```bash
git add site/theme/custom.css
git commit -m "Style chapter images"
```

---

### Task 3: Fit images to the page in the LaTeX fixer

**Files:**
- Modify: `fix-manuskript-latex.py`
- Test: `tests/test_fix_latex.py` (new)

**Interfaces:**
- Consumes: the existing CLI `python3 fix-manuskript-latex.py [book.tex]` (rewrites in place).
- Produces: `fix()` additionally guarantees `\usepackage{graphicx}` and `\setkeys{Gin}{width=\linewidth,height=0.8\textheight,keepaspectratio}` exist and are idempotent.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fix_latex.py`:

```python
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "fix-manuskript-latex.py"


def run_fix(tex: str, tmp_path: Path) -> str:
    book = tmp_path / "book.tex"
    book.write_text(tex, encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SCRIPT), str(book)],
        check=True,
        capture_output=True,
    )
    return book.read_text(encoding="utf-8")


def test_inserts_graphicx_and_setkeys_when_absent(tmp_path: Path) -> None:
    tex = (
        "\\documentclass{memoir}\n\\usepackage[utf8]{inputenc}\n"
        "\\begin{document}\nhi\n\\end{document}\n"
    )
    fixed = run_fix(tex, tmp_path)
    assert "\\usepackage{graphicx}\n" in fixed
    assert (
        "\\setkeys{Gin}{width=\\linewidth,height=0.8\\textheight,keepaspectratio}"
        in fixed
    )
    assert fixed.index("\\setkeys{Gin}") < fixed.index("\\begin{document}")


def test_setkeys_goes_after_existing_graphicx(tmp_path: Path) -> None:
    tex = (
        "\\documentclass{memoir}\n\\usepackage{graphicx}\n"
        "\\begin{document}\nhi\n\\end{document}\n"
    )
    fixed = run_fix(tex, tmp_path)
    assert fixed.count("\\usepackage{graphicx}") == 1
    assert "\\usepackage{graphicx}\n\\setkeys{Gin}" in fixed


def test_fixer_is_idempotent(tmp_path: Path) -> None:
    tex = "\\documentclass{memoir}\n\\begin{document}\nhi\n\\end{document}\n"
    once = run_fix(tex, tmp_path)
    twice = run_fix(once, tmp_path)
    assert twice.count("\\setkeys{Gin}") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_fix_latex.py -v`
Expected: all three FAIL — `\setkeys{Gin}` is never inserted.

- [ ] **Step 3: Implement the insertion**

In `fix-manuskript-latex.py`, insert immediately before the final `return tex` (line 45):

```python
    gin_keys = (
        r"\setkeys{Gin}{width=\linewidth,height=0.8\textheight,keepaspectratio}"
    )
    if gin_keys not in tex:
        if r"\usepackage{graphicx}" in tex:
            tex = tex.replace(
                r"\usepackage{graphicx}",
                "\\usepackage{graphicx}\n" + gin_keys,
                1,
            )
        else:
            tex = tex.replace(
                r"\begin{document}",
                "\\usepackage{graphicx}\n" + gin_keys + "\n\\begin{document}",
                1,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_fix_latex.py -v`
Expected: 3 passed. Then run the whole suite: `python3 -m pytest -q`
Expected: 14 passed.

- [ ] **Step 5: Check the real `book.tex` (copy, not the original)**

Run:

```bash
cp book.tex /tmp/opencode/book-check.tex
python3 fix-manuskript-latex.py /tmp/opencode/book-check.tex
rg -n "setkeys|begin\{document\}" /tmp/opencode/book-check.tex | head
```

Expected: `\usepackage{graphicx}` and `\setkeys{Gin}...` appear immediately before `\begin{document}` (current `book.tex` has no `graphicx`; if it now does, they appear right after it instead).

- [ ] **Step 6: Commit**

```bash
git add fix-manuskript-latex.py tests/test_fix_latex.py
git commit -m "Fit images to page in LaTeX fixer"
```

---

### Task 4: Push and verify the live site (requires user confirmation)

**Files:**
- No file changes.

**Interfaces:**
- Consumes: commits from Tasks 1-3.
- Produces: live site with photos.

- [ ] **Step 1: Full verification before pushing**

Run:

```bash
python3 -m pytest -q
git status --short
git log --oneline -6
```

Expected: 14 passed; only untracked local artifacts (`book.aux`, `book.log`, `book.synctex.gz`, `book.tex`, `book.toc`, `book.txt`); commits for Tasks 1-3 present.

- [ ] **Step 2: Ask the user for confirmation**

Stop and ask the user to confirm pushing to `master` (this triggers the Pages deploy). Do not push before an explicit yes.

- [ ] **Step 3: Push and watch the workflow**

Run:

```bash
git push origin master
gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

Expected: push succeeds; run completes with success.

- [ ] **Step 4: Verify the live site**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://ssppkenny.github.io/internat/
curl -s https://ssppkenny.github.io/internat/part2/ucheba.html | rg -o 'src="[^"]*class.jpg"'
curl -s -o /dev/null -w "%{http_code}\n" https://ssppkenny.github.io/internat/Photos/class.jpg
curl -s -o /tmp/opencode/live.epub -w "%{http_code}\n" https://ssppkenny.github.io/internat/internat.epub
unzip -l /tmp/opencode/live.epub | rg class.jpg
curl -s -o /dev/null -w "%{http_code}\n" https://ssppkenny.github.io/internat/internat.pdf
```

Expected: `200`; HTML shows `src="../Photos/class.jpg"`; photo URL `200`; EPUB `200` and contains a `class.jpg` media entry; PDF `200`.

- [ ] **Step 5: Report the author follow-up**

Tell the user: in Manuskript add more `![Подпись](Photos/имя.jpg)` references as desired; before compiling the PDF in TeXstudio, run `python3 fix-manuskript-latex.py` on the freshly exported `book.tex` so photos fit the page.

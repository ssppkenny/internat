# Front Matter Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Root-level numbered `*.md` files in `internat/outline/` (e.g. «Предисловие») appear before the first part in the site, EPUB and PDF.

**Architecture:** The converter (`tools/build_site.py`) gains `find_front_texts()` and a shared `prepare_body()` helper; `build()` emits front texts before the parts loop into the site tree, `SUMMARY.md`, `build/book.md` (`#` heading) and `build/book-raw.md` (`# ... {-}` so pandoc makes an unnumbered chapter with a TOC entry).

**Tech Stack:** Python stdlib converter + pytest; mdBook v0.5.4 (`/tmp/opencode/mdbook-dist/mdbook`); pandoc 3.7.0.2 (`~/.local/bin/pandoc`); TinyTeX pdflatex.

## Global Constraints

- Never modify `internat/outline/` or `Photos/`; never stage `internat/settings.txt` (user's uncommitted edit).
- Root-level `*.md` files in `internat/outline/` whose names start with an integer are front texts; ordered by that integer; emitted before the first part everywhere.
- SUMMARY: front entries like `- [Предисловие](predislovie.md)` after the `[Интернат](README.md)` line; site file at the `src/` root.
- `build/book.md` heading: `# Предисловие`; `build/book-raw.md` heading: `# Предисловие {-}`.
- Front texts use the same body pipeline as chapters (images, verse emphasis/blockquote, formulas); an empty body prints `warning: {path}: empty chapter body, skipping` and is skipped.
- Slugs are deduped among front texts (`predislovie.md`, `predislovie-2.md`).
- Converter stays stdlib-only.
- Tests: `python3 -m pytest tests/ -v` from repo root; expected 40 passed (37 existing + 3 new).
- Commit messages short and imperative; push to master requires user confirmation at execution time.

---

### Task 1: Front texts in the converter

**Files:**
- Modify: `tools/build_site.py`
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: existing `find_chapters(part_dir) -> list[tuple[int, Path]]`, `parse_title(path) -> str`, `strip_front_matter(text) -> str`, `slugify(title) -> str`, `validate_images(body, source_path, photos_dir)`, `convert_verse_emphasis(body) -> str`, `convert_verse_blocks(body) -> str`, `replace_math(body, math_dir) -> str`, `render_image_figures(body) -> str`, `rewrite_image_refs(body) -> str`.
- Produces: `find_front_texts(outline_dir: Path) -> list[tuple[int, Path]]` and `prepare_body(body: str, source_path: Path, photos_dir: Path, math_dir: Path) -> tuple[str, str, str]` returning `(site_body, epub_body, raw_body)`. Task 2's CI behavior relies only on the generated files.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_site.py` (the file already imports `pytest`, `Path`, `date`, `build`; the `outline` fixture and `write_chapter` helper exist):

```python
def test_front_text_before_parts(outline: Path, tmp_path: Path) -> None:
    write_chapter(outline / "0-Предисловие.md", "Предисловие", "Вступительное слово.")
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    summary = (tmp_path / "src" / "SUMMARY.md").read_text(encoding="utf-8")
    assert summary.index("[Интернат](README.md)") < summary.index(
        "- [Предисловие](predislovie.md)"
    )
    assert summary.index("- [Предисловие](predislovie.md)") < summary.index("# Часть 1")
    site = (tmp_path / "src" / "predislovie.md").read_text(encoding="utf-8")
    assert site.startswith("# Предисловие\n\n")
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert book.index("# Предисловие") < book.index("# Часть 1")
    raw = (tmp_path / "build" / "book-raw.md").read_text(encoding="utf-8")
    assert raw.startswith("# Предисловие {-}\n")


def test_front_texts_sorted_and_deduped(outline: Path, tmp_path: Path) -> None:
    write_chapter(outline / "1-Предисловие.md", "Предисловие", "Второй текст.")
    write_chapter(outline / "0-Предисловие.md", "Предисловие", "Первый текст.")
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    summary = (tmp_path / "src" / "SUMMARY.md").read_text(encoding="utf-8")
    assert summary.index("- [Предисловие](predislovie.md)") < summary.index(
        "- [Предисловие](predislovie-2.md)"
    )
    first = (tmp_path / "src" / "predislovie.md").read_text(encoding="utf-8")
    second = (tmp_path / "src" / "predislovie-2.md").read_text(encoding="utf-8")
    assert "Первый текст." in first
    assert "Второй текст." in second


def test_empty_front_text_skipped(
    outline: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_chapter(outline / "0-Пусто.md", "Пусто", "")
    write_chapter(outline / "1-Предисловие.md", "Предисловие", "Вступительное слово.")
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    summary = (tmp_path / "src" / "SUMMARY.md").read_text(encoding="utf-8")
    assert "Пусто" not in summary
    assert not (tmp_path / "src" / "pusto.md").exists()
    assert "- [Предисловие](predislovie.md)" in summary
    captured = capsys.readouterr()
    assert "0-Пусто.md: empty chapter body, skipping" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_build_site.py -v`
Expected: 3 failed — `test_front_text_before_parts` and `test_front_texts_sorted_and_deduped` raise `ValueError` from `summary.index(...)` (no front entries), `test_empty_front_text_skipped` fails the `"- [Предисловие](predislovie.md)" in summary` assertion. The other 34 tests in this file still pass.

- [ ] **Step 3: Implement the converter changes**

In `tools/build_site.py`, after `find_chapters` (currently lines 217-223), add:

```python
def find_front_texts(outline_dir: Path) -> list[tuple[int, Path]]:
    return find_chapters(outline_dir)


def prepare_body(
    body: str, source_path: Path, photos_dir: Path, math_dir: Path
) -> tuple[str, str, str]:
    validate_images(body, source_path, photos_dir)
    raw_body = convert_verse_emphasis(body)
    verse_body = convert_verse_blocks(body)
    epub_body = replace_math(verse_body, math_dir)
    site_body = render_image_figures(rewrite_image_refs(verse_body))
    return site_body, epub_body, raw_body
```

In `build()`, after `chapter_count = 0` (currently line 251) and before `parts = find_parts(outline_dir)` (line 253), insert:

```python
    used_front_slugs: set[str] = set()
    for _, front_path in find_front_texts(outline_dir):
        front_title = parse_title(front_path)
        body = strip_front_matter(front_path.read_text(encoding="utf-8"))
        if not body:
            print(f"warning: {front_path}: empty chapter body, skipping")
            continue

        site_body, epub_body, raw_body = prepare_body(
            body, front_path, photos_dir, build_dir / "math"
        )

        slug = slugify(front_title)
        candidate = slug
        suffix = 2
        while candidate in used_front_slugs:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        used_front_slugs.add(candidate)

        (site_src / f"{candidate}.md").write_text(
            f"# {front_title}\n\n{site_body}\n", encoding="utf-8"
        )
        summary_lines.append(f"- [{front_title}]({candidate}.md)")
        book_lines += [f"# {front_title}", "", epub_body, ""]
        raw_book_lines += [f"# {front_title} {{-}}", "", raw_body, ""]
        chapter_count += 1

    if used_front_slugs:
        summary_lines.append("")
```

In the chapter loop, replace the transform block (currently lines 271-274):

```python
            validate_images(body, chapter_path, photos_dir)
            raw_body = convert_verse_emphasis(body)
            body = convert_verse_blocks(body)
            epub_body = replace_math(body, build_dir / "math")
```

with:

```python
            site_body, epub_body, raw_body = prepare_body(
                body, chapter_path, photos_dir, build_dir / "math"
            )
```

and replace the site write (currently lines 284-287):

```python
            (site_src / part_slug / f"{candidate}.md").write_text(
                f"# {chapter_title}\n\n{render_image_figures(rewrite_image_refs(body))}\n",
                encoding="utf-8",
            )
```

with:

```python
            (site_src / part_slug / f"{candidate}.md").write_text(
                f"# {chapter_title}\n\n{site_body}\n",
                encoding="utf-8",
            )
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `python3 -m pytest tests/ -v`
Expected: 40 passed.

- [ ] **Step 5: Verify against the real corpus**

Run from the repo root:

```bash
python3 tools/build_site.py
rg -n 'Предисловие' site/src/SUMMARY.md build/book.md build/book-raw.md
head -1 build/book-raw.md
head -1 site/src/predislovie.md
/tmp/opencode/mdbook-dist/mdbook build site
rg -c 'Предисловие' site/book/predislovie.html
```

Expected: `Wrote 32 chapters to site/src`; SUMMARY contains `- [Предисловие](predislovie.md)` before `# Часть 1`; `build/book.md` has `# Предисловие` before `# Часть 1`; first line of `build/book-raw.md` is `# Предисловие {-}`; first line of `site/src/predislovie.md` is `# Предисловие`; mdBook exits 0; `site/book/predislovie.html` exists with ≥1 `Предисловие` match.

Then verify the PDF path with the exact CI commands:

```bash
pandoc build/book-raw.md -s -t latex --toc --top-level-division=chapter \
  -V documentclass=memoir -V fontsize=14pt -V papersize=a4 \
  --metadata title="Интернат" --metadata author="Сергей Михно" \
  -V date="Версия $(cat VERSION)" \
  --include-in-header=frontispiece.tex \
  -o build/book.tex
python3 fix-manuskript-latex.py build/book.tex
pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
pdflatex -interaction=nonstopmode -output-directory=build build/book.tex
rg -n 'chapter\*\{Предисловие\}' build/book.tex
pdftotext -f 2 -l 4 build/book.pdf - | rg -n 'Предисловие|Часть 1' | head -5
```

Expected: both pdflatex runs exit 0; `build/book.tex` contains `\chapter*{Предисловие}`; the extracted pages show `Предисловие` before the first `Часть 1`.

- [ ] **Step 6: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py
git commit -m "Add front matter support"
```

Verify with `git show --stat HEAD` that exactly these two files are in the commit (`internat/settings.txt` must not appear).

---

### Task 2: Push and live verification (user confirmation required)

**Files:**
- No file changes; deployment only.

**Interfaces:**
- Consumes: commit from Task 1; the Pages workflow (`.github/workflows/pages.yml`) which already runs the converter and builds the site, EPUB and PDF.

- [ ] **Step 1: Final local check**

Run: `python3 -m pytest tests/ -v`
Expected: 40 passed.

- [ ] **Step 2: STOP — ask the user for push confirmation**

Present the change (foreword now first everywhere) and the expected live result; wait for an explicit yes before pushing.

- [ ] **Step 3: Push**

```bash
git push origin master
```

- [ ] **Step 4: Watch the workflow**

```bash
gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

Expected: success.

- [ ] **Step 5: Live checks**

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/predislovie.html
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/part1/postuplenie-v-fmsh.html
curl -s https://ssppkenny.github.io/internat/ | rg -o 'predislovie.html' | head -1
curl -s https://ssppkenny.github.io/internat/predislovie.html | rg -o 'Предисловие' | head -1
curl -s -o /tmp/opencode/live.pdf https://ssppkenny.github.io/internat/internat.pdf
pdftotext -f 2 -l 4 /tmp/opencode/live.pdf - | rg -n 'Предисловие|Часть 1' | head -5
curl -s -o /tmp/opencode/live.epub https://ssppkenny.github.io/internat/internat.epub
unzip -p /tmp/opencode/live.epub EPUB/nav.xhtml | rg -o 'Предисловие' | head -1
```

Expected: landing and `predislovie.html` return 200; the landing sidebar links `predislovie.html`; the page contains `Предисловие`; the PDF text shows `Предисловие` before the first `Часть 1`; the EPUB navigation contains `Предисловие`. Also spot-check one chapter page (e.g. `part1/postuplenie-v-fmsh.html`) returns 200.

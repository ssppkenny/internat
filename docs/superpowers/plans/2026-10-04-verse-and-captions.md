# Verse Blocks and Image Captions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render raw LaTeX `verse` blocks as blockquotes on the site and EPUB, and show image captions on the site.

**Architecture:** The converter (`tools/build_site.py`) gains two transformations applied while writing generated files: `convert_verse_blocks` (both site markdown and `build/book.md`) and `render_image_figures` (site markdown only). Sources in `internat/outline/` and `Photos/` are never modified. A small CSS addition styles captions.

**Tech Stack:** Python stdlib only (`re`, `html`), pytest, mdBook v0.5.4 (local binary `/tmp/opencode/mdbook-dist/mdbook`), pandoc 3.7.0.2 (local `~/.local/bin/pandoc`).

**Spec:** `docs/superpowers/specs/2026-10-04-verse-and-captions-design.md`

## Global Constraints

- Never modify `internat/outline/` or `Photos/`. Affected source chapters: `internat/outline/1------_2/00------.md` (1 verse block), `05-----------.md` (2), `06------.md` (8).
- Verse output form, per line: `> ` + NBSP-preserved indent + text; each leading tab → `&nbsp;&nbsp;&nbsp;&nbsp;`, each leading space → `&nbsp;`; a line ending in two backslashes `\\` is emitted with one backslash `\` (CommonMark hard break); the final line keeps no trailing backslash. No `\begin{verse}`/`\end{verse}` remains.
- Verse transform applies to BOTH the site chapter markdown and `build/book.md`.
- Figure markup (site only), exactly:
  `"<figure>\n" + '<img src="' + src + '" alt="' + alt + '">' + "\n" + "<figcaption>" + alt + "</figcaption>" + "\n" + "</figure>"`
  where `src` is the already-rewritten `../Photos/<rel>` path and `alt` is `html.escape(alt, quote=True)`.
- `build/book.md` keeps plain markdown image refs exactly `![alt](Photos/<rel>)` (pandoc's implicit figure handles EPUB captions).
- Site image refs remain exactly `../Photos/<rel>`.
- CSS appended to `site/theme/custom.css` must be exactly:
  ```css
  .content main figcaption {
      margin-top: 0.5em;
      font-size: 0.9em;
      text-align: center;
      opacity: 0.8;
  }
  ```
- Converter stays stdlib-only; only new import allowed is `html`.
- Commit messages short and imperative. Push to `master` requires user confirmation at execution time.
- CI EPUB command (unchanged, for verification): from repo root,
  `pandoc build/book.md -o site/book/internat.epub --toc --metadata title="Интернат" --metadata author="Сергей Михно" --metadata lang=ru`.
- All 14 existing tests must keep passing (two image tests are updated per this plan).

---

### Task 1: Verse and figure transforms in converter + caption CSS

**Files:**
- Modify: `tools/build_site.py`
- Modify: `tests/test_build_site.py`
- Modify: `site/theme/custom.css`

**Interfaces:**
- Consumes: existing `build(outline_dir, site_src, build_dir, photos_dir)`, `rewrite_image_refs(body)`, `IMG_RE`.
- Produces: `convert_verse_blocks(body: str) -> str`; `render_image_figures(body: str) -> str`; module constants `VERSE_RE`, `STANDALONE_IMAGE_RE`. `build()` applies `convert_verse_blocks` to every chapter body before both writes, and `render_image_figures(rewrite_image_refs(body))` for the site write.

- [ ] **Step 1: Write the failing verse test**

Append to `tests/test_build_site.py`:

```python
def test_verse_block_converted_to_blockquote(outline: Path, tmp_path: Path) -> None:
    body = (
        "Проза.\n\n"
        "\\begin{verse}\n"
        "В порт,\\\\\n"
        "\tгорящий,\\\\\n"
        "\t\tкак расплавленное лето,\\\\\n"
        "разворачивался\\\\\n"
        "Нетте».\n"
        "\\end{verse}"
    )
    write_chapter(outline / "0-Часть 1" / "0-Поступление.md", "Поступление", body)
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    site = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    expected_blockquote = (
        "> В порт,\\\n"
        "> &nbsp;&nbsp;&nbsp;&nbsp;горящий,\\\n"
        "> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;как расплавленное лето,\\\n"
        "> разворачивался\\\n"
        "> Нетте»."
    )
    assert expected_blockquote in site
    assert "\\begin{verse}" not in site
    assert "\\end{verse}" not in site
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert expected_blockquote in book
    assert "\\begin{verse}" not in book
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_build_site.py::test_verse_block_converted_to_blockquote -v`
Expected: FAIL (`\begin{verse}` still present)

- [ ] **Step 3: Implement `convert_verse_blocks` and wire it in**

In `tools/build_site.py`, after the `IMG_RE` line add:

```python
VERSE_RE = re.compile(r"^\\begin\{verse\}\n(.*?)\n\\end\{verse\}$", re.M | re.S)
```

After `rewrite_image_refs` add:

```python
def convert_verse_blocks(body: str) -> str:
    def render(match: re.Match[str]) -> str:
        lines = []
        for line in match.group(1).splitlines():
            if line.endswith("\\\\"):
                line = line[:-2] + "\\"
            indent = re.match(r"[ \t]*", line).group(0)
            spaces = "".join(
                "&nbsp;" * 4 if char == "\t" else "&nbsp;" for char in indent
            )
            lines.append(f"> {spaces}{line[len(indent):]}")
        return "\n".join(lines)

    return VERSE_RE.sub(render, body)
```

In `build()`, after the `validate_images(body, chapter_path, photos_dir)` line, add:

```python
            body = convert_verse_blocks(body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_build_site.py -v`
Expected: 15 passed (14 existing + 1 new)

- [ ] **Step 5: Write the failing figure test**

Append to `tests/test_build_site.py`:

```python
def test_image_rendered_as_figure_on_site(outline: Path, tmp_path: Path) -> None:
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
    assert "<figure>" in site
    assert '<img src="../Photos/pic.jpg" alt="Снимок">' in site
    assert "<figcaption>Снимок</figcaption>" in site
    assert "![" not in site
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "![Снимок](Photos/pic.jpg)" in book
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python3 -m pytest tests/test_build_site.py::test_image_rendered_as_figure_on_site -v`
Expected: FAIL (`<figure>` not present)

- [ ] **Step 7: Implement `render_image_figures` and update the two existing image tests**

In `tools/build_site.py`, add the `html` import next to the other stdlib imports (alphabetical):

```python
import html
import re
import shutil
import sys
```

After the `IMG_RE` line add:

```python
STANDALONE_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\((\.\./Photos/[^)\s]+)\)$", re.M)
```

After `rewrite_image_refs` (and after `convert_verse_blocks`) add:

```python
def render_image_figures(body: str) -> str:
    def render(match: re.Match[str]) -> str:
        alt = html.escape(match.group(1), quote=True)
        return (
            "<figure>\n"
            f'<img src="{match.group(2)}" alt="{alt}">\n'
            f"<figcaption>{alt}</figcaption>\n"
            "</figure>"
        )

    return STANDALONE_IMAGE_RE.sub(render, body)
```

In `build()`, change the site write:

```python
            (site_src / part_slug / f"{candidate}.md").write_text(
                f"# {chapter_title}\n\n{render_image_figures(rewrite_image_refs(body))}\n",
                encoding="utf-8",
            )
```

Update `tests/test_build_site.py::test_photos_rewritten_and_copied` line 102: replace
`assert "![Снимок](../Photos/pic.jpg)" in site` with

```python
    assert '<img src="../Photos/pic.jpg" alt="Снимок">' in site
    assert "<figcaption>Снимок</figcaption>" in site
```

Update `tests/test_build_site.py::test_dot_slash_image_ref_rewritten` line 119: replace
`assert "![Снимок](../Photos/pic.jpg)" in site` with

```python
    assert '<img src="../Photos/pic.jpg" alt="Снимок">' in site
```

- [ ] **Step 8: Run full suite to verify green**

Run: `python3 -m pytest tests/ -v`
Expected: 16 passed

- [ ] **Step 9: Append caption CSS**

Append to `site/theme/custom.css`:

```css

.content main figcaption {
    margin-top: 0.5em;
    font-size: 0.9em;
    text-align: center;
    opacity: 0.8;
}
```

- [ ] **Step 10: Verify against the real corpus and both output tools**

Run from repo root:

```bash
python3 tools/build_site.py
/tmp/opencode/mdbook-dist/mdbook build site
~/.local/bin/pandoc build/book.md -o /tmp/opencode/verse-check.epub --toc --metadata title="Интернат" --metadata author="Сергей Михно" --metadata lang=ru
```

Then verify:

```bash
grep -c 'begin{verse}' site/src/part2/stikhi.md build/book.md       # expect 0 and 0 (grep exits 1; that is fine)
grep -n '> Снова солнце, душная платформа.\\$' site/src/part2/stikhi.md build/book.md   # expect one hit each
grep -c '<blockquote>' site/book/part2/stikhi.html                  # expect >= 8
grep -c 'begin{verse}' site/book/part2/stikhi.html                  # expect 0
grep -n '<figcaption>Наш класс</figcaption>' site/book/part2/ucheba.html   # expect one hit
python3 - <<'EOF'
import zipfile
z = zipfile.ZipFile('/tmp/opencode/verse-check.epub')
text = "\n".join(
    z.read(n).decode('utf-8', 'replace')
    for n in z.namelist() if n.endswith(('.xhtml', '.html'))
)
assert 'Снова солнце, душная платформа' in text, 'poem missing from EPUB'
assert '<figcaption' in text and 'Наш класс' in text, 'caption missing from EPUB'
print('EPUB poem and caption OK')
EOF
```

Expected: all checks pass; EPUB prints `EPUB poem and caption OK`.

- [ ] **Step 11: Commit**

```bash
git add tools/build_site.py tests/test_build_site.py site/theme/custom.css
git commit -m "Render verses and image captions"
```

---

### Task 2: Push and live verification

**Files:** none (ops only).

**Interfaces:**
- Consumes: Task 1 commit on `master`; GitHub Pages workflow `.github/workflows/pages.yml`.
- Produces: deployed site/EPUB with verses and captions.

- [ ] **Step 1: Full local test run**

Run: `python3 -m pytest tests/ -v`
Expected: 16 passed

- [ ] **Step 2: Ask the user for push confirmation**

The controller must ask the user before pushing. Do not push without an explicit yes.

- [ ] **Step 3: Push and watch the workflow**

```bash
git push origin master
gh run watch "$(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

Expected: run completes successfully (build + deploy jobs).

- [ ] **Step 4: Verify live**

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://ssppkenny.github.io/internat/
curl -s https://ssppkenny.github.io/internat/part2/stikhi.html | grep -c '<blockquote>'      # expect >= 8
curl -s https://ssppkenny.github.io/internat/part2/stikhi.html | grep -c 'begin{verse}'      # expect 0
curl -s https://ssppkenny.github.io/internat/part2/ucheba.html | grep -c '<figcaption>Наш класс</figcaption>'  # expect 1
curl -s -o /tmp/opencode/live-verse.epub -w '%{http_code}\n' https://ssppkenny.github.io/internat/internat.epub
python3 - <<'EOF'
import zipfile
z = zipfile.ZipFile('/tmp/opencode/live-verse.epub')
text = "\n".join(
    z.read(n).decode('utf-8', 'replace')
    for n in z.namelist() if n.endswith(('.xhtml', '.html'))
)
assert 'Снова солнце, душная платформа' in text
assert '<figcaption' in text and 'Наш класс' in text
print('Live EPUB poem and caption OK')
EOF
```

Expected: index `200`, blockquote count ≥ 8, zero `begin{verse}`, one `figcaption`, EPUB `200`, `Live EPUB poem and caption OK`.

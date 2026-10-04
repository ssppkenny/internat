# Verse blocks and image captions — design

**Date:** 2026-10-04
**Status:** approved (user chose blockquote rendering)

## Problem

Chapter bodies in `internat/outline/` contain raw LaTeX verse blocks:

```
\begin{verse}
В порт,\\
	горящий,\\
...
\end{verse}
```

The converter (`tools/build_site.py`) copies bodies verbatim, so:

- **Site**: mdBook renders the commands as literal text and collapses the poem into one paragraph.
- **EPUB**: pandoc parses the block as raw LaTeX and drops it entirely — poem text is missing.
- **PDF**: unaffected; Manuskript exports via pandoc to LaTeX, which preserves `verse`.

Image references `![Подпись](Photos/имя.jpg)`:

- **EPUB**: pandoc already produces `<figure><figcaption>Подпись</figcaption></figure>`.
- **Site**: no caption is shown.
- **PDF**: pandoc-generated LaTeX already emits a figure with `\caption` (to be confirmed on the author's next export).

## Fix (converter-only; `internat/outline/` and `Photos/` untouched)

### 1. Verse → blockquote

New function `convert_verse_blocks(body: str) -> str`, applied in `build()` to **both** the site chapter markdown and `build/book.md`.

For each `\begin{verse}` … `\end{verse}` block:

- Emit a Markdown blockquote: one `> ` prefix per poem line.
- Each line's trailing `\\` becomes a single `\` → CommonMark hard line break (`<br>`).
- Leading indentation is preserved as non-breaking spaces: each leading tab → `&nbsp;&nbsp;&nbsp;&nbsp;`, each leading space → `&nbsp;`. This keeps Маяковский's ladder visible.
- No other changes; the block keeps its surrounding blank lines.

Validated: mdBook v0.5.4 and pandoc both render the blockquote with `<br>` and NBSP indentation.

### 2. Site image captions

New function `render_image_figures(body: str) -> str`, applied to the **site chapter markdown only** (after image-path rewriting). A line consisting solely of `![alt](../Photos/<file>)` becomes:

```html
<figure>
<img src="../Photos/<file>" alt="<alt>">
<figcaption><alt></figcaption>
</figure>
```

`alt` is HTML-escaped (`html.escape`). `build/book.md` keeps plain `![alt](Photos/<file>)`, so pandoc's existing figure/caption behavior is unchanged.

### 3. CSS

Append to `site/theme/custom.css`:

```css
.content main figcaption {
  margin-top: 0.5em;
  font-size: 0.9em;
  text-align: center;
  opacity: 0.8;
}
```

Verses use the tools' default blockquote styling; no extra rules.

## Tests (`tests/test_build_site.py`)

- Verse block becomes a blockquote in both site output and `build/book.md`; no `\begin{verse}` remains.
- Tab indentation becomes NBSP runs.
- Site shows `<figure>`/`<figcaption>`; `build/book.md` still has the plain markdown image.
- Existing image tests updated for the figure markup.

## Verification

1. `pytest` all green.
2. Real converter run: `site/src/part2/stikhi.md` has `> Снова солнце…`, no LaTeX commands; `build/book.md` likewise.
3. `mdbook build site`: poem page has `<blockquote>` with `<br>`, no literal `\begin`.
4. pandoc EPUB: poem text present (was missing) and `<figcaption>` present.
5. After user-approved push: live `/part2/stikhi.html` shows the poem; live EPUB contains it.

## Out of scope

- No changes to the PDF path (`fix-manuskript-latex.py`, Manuskript export).
- No changes to `.github/workflows/pages.yml` or any source content.

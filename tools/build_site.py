#!/usr/bin/env python3
"""Convert the Manuskript project in internat/outline/ into an mdBook source tree."""

from __future__ import annotations

import hashlib
import html
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTLINE_DIR = REPO_ROOT / "internat" / "outline"
SITE_SRC = REPO_ROOT / "site" / "src"
BUILD_DIR = REPO_ROOT / "build"
PHOTOS_DIR = REPO_ROOT / "Photos"
VERSION_FILE = REPO_ROOT / "VERSION"

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "№": "",
}

IMG_RE = re.compile(r"\]\((?:\./)?Photos/([^)\s]+)\)")

VERSE_RE = re.compile(r"^\\begin\{verse\}\n(.*?)\n\\end\{verse\}$", re.M | re.S)
STANDALONE_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\((\.\./Photos/[^)\s]+)\)$", re.M)
MATH_REF_PREFIX = "build/math"
DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\$)")


def leading_int(name: str) -> int | None:
    match = re.match(r"^(\d+)", name)
    return int(match.group(1)) if match else None


def parse_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip()
            if not title:
                raise ValueError(f"{path}: no title: line")
            return title
    raise ValueError(f"{path}: no title: line")


def strip_front_matter(text: str) -> str:
    lines = text.splitlines()
    index = 0
    while index < len(lines) and re.match(r"^[A-Za-z]+:", lines[index]):
        index += 1
    if index:
        while index < len(lines) and not lines[index].strip():
            index += 1
    return "\n".join(lines[index:]).strip()


def slugify(title: str) -> str:
    transliterated = "".join(TRANSLIT.get(char, char) for char in title.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    return slug or "chapter"


def read_version() -> str:
    if not VERSION_FILE.is_file():
        raise ValueError(f"{VERSION_FILE}: missing version file")
    return VERSION_FILE.read_text(encoding="utf-8").strip()


MONTHS_RU = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def format_date_ru(d: date) -> str:
    return f"{d.day} {MONTHS_RU[d.month - 1]} {d.year}"


def validate_images(body: str, chapter_path: Path, photos_dir: Path) -> None:
    for match in IMG_RE.finditer(body):
        rel = match.group(1)
        if not (photos_dir / rel).is_file():
            raise ValueError(f"{chapter_path}: missing image Photos/{rel}")


def rewrite_image_refs(body: str) -> str:
    return IMG_RE.sub(r"](../Photos/\1)", body)


def convert_verse_blocks(body: str) -> str:
    def render(match: re.Match[str]) -> str:
        source_lines = match.group(1).splitlines()
        lines = []
        for position, line in enumerate(source_lines):
            if position == len(source_lines) - 1:
                line = line.rstrip("\\")
            elif line.endswith("\\\\"):
                line = line[:-2] + "\\"
            indent = re.match(r"[ \t]*", line).group(0)
            spaces = "".join(
                "&nbsp;" * 4 if char == "\t" else "&nbsp;" for char in indent
            )
            lines.append(f"> {spaces}{line[len(indent):]}")
        return "\n".join(lines)

    return VERSE_RE.sub(render, body)


def convert_verse_emphasis(body: str) -> str:
    def render(match: re.Match[str]) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", match.group(1))
        text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\\emph{\1}", text)
        return f"\\begin{{verse}}\n{text}\n\\end{{verse}}"

    return VERSE_RE.sub(render, body)


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


def render_math_svg(expr: str, display: bool, out_dir: Path) -> Path:
    digest = hashlib.sha1(f"{int(display)}:{expr}".encode("utf-8")).hexdigest()[:12]
    out_path = out_dir / f"eq-{digest}.svg"
    if out_path.is_file():
        return out_path

    body = f"$\\displaystyle {expr}$" if display else f"${expr}$"
    document = (
        "\\documentclass[border=1pt]{standalone}\n"
        "\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "formula.tex").write_text(document, encoding="utf-8")
        commands = [
            ["latex", "-interaction=nonstopmode", "-halt-on-error", "formula.tex"],
            [
                "dvisvgm",
                "--no-fonts",
                "--exact-bbox",
                "formula.dvi",
                "-o",
                str(out_path.resolve()),
            ],
        ]
        for command in commands:
            try:
                result = subprocess.run(
                    command, cwd=tmp_dir, capture_output=True, text=True
                )
            except FileNotFoundError as error:
                raise ValueError(
                    f"math render failed for {expr!r}: {command[0]} not found"
                ) from error
            if result.returncode != 0:
                tail = "\n".join((result.stdout + result.stderr).splitlines()[-5:])
                raise ValueError(f"math render failed for {expr!r}: {tail}")
    if not out_path.is_file():
        raise ValueError(f"math render failed for {expr!r}: no SVG produced")
    return out_path


def replace_math(body: str, math_dir: Path) -> str:
    def render_display(match: re.Match[str]) -> str:
        path = render_math_svg(match.group(1).strip(), True, math_dir)
        return f"![]({MATH_REF_PREFIX}/{path.name})"

    def render_inline(match: re.Match[str]) -> str:
        path = render_math_svg(match.group(1), False, math_dir)
        return f"![]({MATH_REF_PREFIX}/{path.name})"

    body = DISPLAY_MATH_RE.sub(render_display, body)
    return INLINE_MATH_RE.sub(render_inline, body)


def find_parts(outline_dir: Path) -> list[tuple[int, Path]]:
    parts = []
    for child in outline_dir.iterdir():
        number = leading_int(child.name)
        if child.is_dir() and number is not None:
            parts.append((number, child))
    return sorted(parts)


def find_chapters(part_dir: Path) -> list[tuple[int, Path]]:
    chapters = []
    for child in part_dir.glob("*.md"):
        number = leading_int(child.name)
        if number is not None:
            chapters.append((number, child))
    return sorted(chapters)


def build(
    outline_dir: Path = OUTLINE_DIR,
    site_src: Path = SITE_SRC,
    build_dir: Path = BUILD_DIR,
    photos_dir: Path = PHOTOS_DIR,
    version: str | None = None,
    last_changed: date | None = None,
) -> None:
    if version is None:
        version = read_version()
    if last_changed is None:
        last_changed = date.today()
    if not outline_dir.is_dir():
        raise ValueError(f"{outline_dir}: not a directory")

    if site_src.exists():
        shutil.rmtree(site_src)
    site_src.mkdir(parents=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    if photos_dir.is_dir():
        shutil.copytree(photos_dir, site_src / "Photos")

    summary_lines = ["# Summary", "", "[Интернат](README.md)", ""]
    book_lines: list[str] = []
    raw_book_lines: list[str] = [
        "\\begin{center}\n"
        "\\includegraphics[width=\\linewidth,height=0.75\\textheight,keepaspectratio]{Photos/Omslag.jpg}\n"
        "\\end{center}\n",
    ]
    chapter_count = 0

    parts = find_parts(outline_dir)
    for part_index, (_, part_dir) in enumerate(parts, start=1):
        part_title = parse_title(part_dir / "folder.txt")
        part_slug = f"part{part_index}"
        (site_src / part_slug).mkdir(parents=True, exist_ok=True)

        summary_lines += [f"# {part_title}", ""]
        book_lines += [f"# {part_title}", ""]
        raw_book_lines += [f"# {part_title}", ""]

        used_slugs: set[str] = set()
        for _, chapter_path in find_chapters(part_dir):
            chapter_title = parse_title(chapter_path)
            body = strip_front_matter(chapter_path.read_text(encoding="utf-8"))
            if not body:
                print(f"warning: {chapter_path}: empty chapter body, skipping")
                continue

            validate_images(body, chapter_path, photos_dir)
            raw_body = convert_verse_emphasis(body)
            body = convert_verse_blocks(body)
            epub_body = replace_math(body, build_dir / "math")

            slug = slugify(chapter_title)
            candidate = slug
            suffix = 2
            while candidate in used_slugs:
                candidate = f"{slug}-{suffix}"
                suffix += 1
            used_slugs.add(candidate)

            (site_src / part_slug / f"{candidate}.md").write_text(
                f"# {chapter_title}\n\n{render_image_figures(rewrite_image_refs(body))}\n",
                encoding="utf-8",
            )
            summary_lines.append(f"- [{chapter_title}]({part_slug}/{candidate}.md)")
            book_lines += [f"## {chapter_title}", "", epub_body, ""]
            raw_book_lines += [f"## {chapter_title}", "", raw_body, ""]
            chapter_count += 1

        summary_lines.append("")

    (site_src / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
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
    (build_dir / "book.md").write_text("\n".join(book_lines), encoding="utf-8")
    (build_dir / "book-raw.md").write_text("\n".join(raw_book_lines), encoding="utf-8")

    print(f"Wrote {chapter_count} chapters to {site_src}")


def main() -> int:
    try:
        build()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

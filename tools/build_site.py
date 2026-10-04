#!/usr/bin/env python3
"""Convert the Manuskript project in internat/outline/ into an mdBook source tree."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTLINE_DIR = REPO_ROOT / "internat" / "outline"
SITE_SRC = REPO_ROOT / "site" / "src"
BUILD_DIR = REPO_ROOT / "build"

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "№": "",
}


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
) -> None:
    if not outline_dir.is_dir():
        raise ValueError(f"{outline_dir}: not a directory")

    if site_src.exists():
        shutil.rmtree(site_src)
    site_src.mkdir(parents=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = ["# Summary", "", "[Интернат](README.md)", ""]
    book_lines: list[str] = []
    chapter_count = 0

    parts = find_parts(outline_dir)
    for part_index, (_, part_dir) in enumerate(parts, start=1):
        part_title = parse_title(part_dir / "folder.txt")
        part_slug = f"part{part_index}"
        (site_src / part_slug).mkdir(parents=True, exist_ok=True)

        summary_lines += [f"# {part_title}", ""]
        book_lines += [f"# {part_title}", ""]

        used_slugs: set[str] = set()
        for _, chapter_path in find_chapters(part_dir):
            chapter_title = parse_title(chapter_path)
            body = strip_front_matter(chapter_path.read_text(encoding="utf-8"))
            if not body:
                raise ValueError(f"{chapter_path}: empty chapter body")

            slug = slugify(chapter_title)
            candidate = slug
            suffix = 2
            while candidate in used_slugs:
                candidate = f"{slug}-{suffix}"
                suffix += 1
            used_slugs.add(candidate)

            (site_src / part_slug / f"{candidate}.md").write_text(
                f"# {chapter_title}\n\n{body}\n", encoding="utf-8"
            )
            summary_lines.append(f"- [{chapter_title}]({part_slug}/{candidate}.md)")
            book_lines += [f"## {chapter_title}", "", body, ""]
            chapter_count += 1

        summary_lines.append("")

    (site_src / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (site_src / "README.md").write_text(
        "# Интернат\n\n"
        "**Сергей Михно**\n\n"
        "Воспоминания о годах учёбы в ФМШ №18 при МГУ.\n\n"
        "- [Скачать PDF](internat.pdf)\n"
        "- [Скачать EPUB](internat.epub)\n",
        encoding="utf-8",
    )
    (build_dir / "book.md").write_text("\n".join(book_lines), encoding="utf-8")

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

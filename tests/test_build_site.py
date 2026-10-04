from pathlib import Path

import pytest

from tools.build_site import build


def write_part(path: Path, title: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "folder.txt").write_text(
        f"title:          {title}\nID:             1\ntype:           folder\n"
        f"compile:        2\ncharCount:      0\n",
        encoding="utf-8",
    )


def write_chapter(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"title:          {title}\nID:             1\ntype:           md\n"
        f"compile:        2\ncharCount:      {len(body)}\n\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.fixture()
def outline(tmp_path: Path) -> Path:
    root = tmp_path / "outline"
    write_part(root / "0-Часть 1", "Часть 1")
    write_chapter(root / "0-Часть 1" / "0-Поступление.md", "Поступление", "Первый текст.")
    write_chapter(root / "0-Часть 1" / "1-Зима.md", "Зима в Москве", "Второй текст.")
    write_part(root / "1-Часть 2", "Часть 2")
    write_chapter(root / "1-Часть 2" / "0-Учеба.md", "Учеба", "Третий текст.")
    write_chapter(root / "1-Часть 2" / "1-Тест.md", "Тест", "Четвёртый текст.")
    write_chapter(root / "1-Часть 2" / "2-Тест.md", "Тест", "Пятый текст.")
    return root


def test_summary_parts_and_chapters_in_order(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build")
    summary = (tmp_path / "src" / "SUMMARY.md").read_text(encoding="utf-8")
    assert summary.index("# Часть 1") < summary.index("# Часть 2")
    assert "- [Поступление](part1/postuplenie.md)" in summary
    assert "- [Зима в Москве](part1/zima-v-moskve.md)" in summary
    assert "- [Учеба](part2/ucheba.md)" in summary


def test_front_matter_stripped(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build")
    text = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    assert text == "# Поступление\n\nПервый текст.\n"
    assert "charCount" not in text


def test_duplicate_slugs_deduped(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build")
    assert (tmp_path / "src" / "part2" / "test.md").exists()
    assert (tmp_path / "src" / "part2" / "test-2.md").exists()


def test_epub_source_concatenated(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build")
    text = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "# Часть 1" in text
    assert "## Поступление" in text
    assert text.index("## Зима в Москве") < text.index("# Часть 2")


def test_readme_has_download_links(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build")
    readme = (tmp_path / "src" / "README.md").read_text(encoding="utf-8")
    assert "**Сергей Михно**" in readme
    assert "[Скачать PDF](internat.pdf)" in readme
    assert "[Скачать EPUB](internat.epub)" in readme


def test_missing_title_fails(outline: Path, tmp_path: Path) -> None:
    (outline / "0-Часть 1" / "folder.txt").write_text("ID: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no title"):
        build(outline, tmp_path / "src", tmp_path / "build")


def test_empty_title_fails(outline: Path, tmp_path: Path) -> None:
    (outline / "0-Часть 1" / "folder.txt").write_text(
        "title:          \nID:             1\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="no title"):
        build(outline, tmp_path / "src", tmp_path / "build")

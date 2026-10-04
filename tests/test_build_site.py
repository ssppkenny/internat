from pathlib import Path

import pytest

from tools.build_site import build

import tools.build_site as build_site


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
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    summary = (tmp_path / "src" / "SUMMARY.md").read_text(encoding="utf-8")
    assert summary.index("# Часть 1") < summary.index("# Часть 2")
    assert "- [Поступление](part1/postuplenie.md)" in summary
    assert "- [Зима в Москве](part1/zima-v-moskve.md)" in summary
    assert "- [Учеба](part2/ucheba.md)" in summary


def test_front_matter_stripped(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    text = (tmp_path / "src" / "part1" / "postuplenie.md").read_text(encoding="utf-8")
    assert text == "# Поступление\n\nПервый текст.\n"
    assert "charCount" not in text


def test_duplicate_slugs_deduped(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    assert (tmp_path / "src" / "part2" / "test.md").exists()
    assert (tmp_path / "src" / "part2" / "test-2.md").exists()


def test_epub_source_concatenated(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    text = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert "# Часть 1" in text
    assert "## Поступление" in text
    assert text.index("## Зима в Москве") < text.index("# Часть 2")


def test_readme_has_download_links(outline: Path, tmp_path: Path) -> None:
    build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")
    readme = (tmp_path / "src" / "README.md").read_text(encoding="utf-8")
    assert "**Сергей Михно**" in readme
    assert "Версия 0.1" in readme
    assert "[Скачать PDF](internat.pdf)" in readme
    assert "[Скачать EPUB](internat.epub)" in readme


def test_missing_title_fails(outline: Path, tmp_path: Path) -> None:
    (outline / "0-Часть 1" / "folder.txt").write_text("ID: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no title"):
        build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")


def test_empty_title_fails(outline: Path, tmp_path: Path) -> None:
    (outline / "0-Часть 1" / "folder.txt").write_text(
        "title:          \nID:             1\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="no title"):
        build(outline, tmp_path / "src", tmp_path / "build", photos_dir=tmp_path / "Photos")


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
    assert '<img src="../Photos/pic.jpg" alt="Снимок">' in site
    assert "<figcaption>Снимок</figcaption>" in site
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
    assert '<img src="../Photos/pic.jpg" alt="Снимок">' in site


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


def test_verse_block_converted_to_blockquote(outline: Path, tmp_path: Path) -> None:
    body = (
        "Проза.\n\n"
        "\\begin{verse}\n"
        "В порт,\\\\\n"
        "\tгорящий,\\\\\n"
        "\t\tкак расплавленное лето,\\\\\n"
        "разворачивался\\\\\n"
        "Нетте».\\\\\n"
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
    assert expected_blockquote + "\n" in site
    assert "\\begin{verse}" not in site
    assert "\\end{verse}" not in site
    book = (tmp_path / "build" / "book.md").read_text(encoding="utf-8")
    assert expected_blockquote + "\n" in book
    assert "\\begin{verse}" not in book


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

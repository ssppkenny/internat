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


def test_figures_get_here_placement_and_barriers(tmp_path: Path) -> None:
    tex = (
        "\\documentclass{memoir}\n\\usepackage{graphicx}\n"
        "\\begin{document}\n"
        "\\chapter{One}\n"
        "\\section{First}\n"
        "\\begin{figure}\n\\includegraphics{x.jpg}\n\\end{figure}\n"
        "\\section{Second}\nhi\n"
        "\\end{document}\n"
    )
    fixed = run_fix(tex, tmp_path)
    assert "\\usepackage{placeins}\n" in fixed
    assert "\\begin{figure}[htbp]" in fixed
    assert "\\FloatBarrier\n\\chapter{One}" in fixed
    assert "\\FloatBarrier\n\\section{First}" in fixed
    assert "\\FloatBarrier\n\\section{Second}" in fixed


def test_figure_placement_is_idempotent(tmp_path: Path) -> None:
    tex = (
        "\\documentclass{memoir}\n"
        "\\begin{document}\n"
        "\\section{First}\n"
        "\\begin{figure}\n\\includegraphics{x.jpg}\n\\end{figure}\n"
        "\\end{document}\n"
    )
    once = run_fix(tex, tmp_path)
    twice = run_fix(once, tmp_path)
    assert twice == once
    assert twice.count("\\FloatBarrier") == 1
    assert "[htbp][htbp]" not in twice

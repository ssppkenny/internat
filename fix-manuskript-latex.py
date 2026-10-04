#!/usr/bin/env python3
"""Post-process a Manuskript/Pandoc LaTeX export so it compiles with pdflatex."""

import re
import sys
from pathlib import Path


def fix(tex: str) -> str:
    tex = tex.replace(r"\usepackage[T1]{fontenc}", r"\usepackage[T2A]{fontenc}")

    if r"\usepackage[russian]{babel}" not in tex:
        tex = tex.replace(
            r"\usepackage[utf8]{inputenc}",
            "\\usepackage[utf8]{inputenc}\n\\usepackage[russian]{babel}",
            1,
        )

    if r"\renewcommand{\rmdefault}{cmr}" not in tex:
        tex = tex.replace(
            r"\usepackage{lmodern}",
            "\\usepackage{lmodern}\n"
            "\\renewcommand{\\rmdefault}{cmr}\n"
            "\\renewcommand{\\sfdefault}{cmss}\n"
            "\\renewcommand{\\ttdefault}{cmtt}",
            1,
        )

    if "openany" not in tex:
        m = re.search(r"\\documentclass\[([^\]]*)\]\{memoir\}", tex)
        if m:
            tex = tex.replace(
                m.group(0), "\\documentclass[" + m.group(1) + ",openany]{memoir}", 1
            )
        else:
            tex = tex.replace(
                r"\documentclass{memoir}", r"\documentclass[openany]{memoir}", 1
            )

    tex = re.sub(r"\\setstretch\{([^}]*)\}", r"\\linespread{\1}\\selectfont", tex)

    # T2A has no definitions for combining accents; drop them
    tex = re.sub(r"[\u0300-\u036f]", "", tex)

    return tex


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "book.tex")
    path.write_text(fix(path.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"fixed {path}")


if __name__ == "__main__":
    main()

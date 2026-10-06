#!/usr/bin/env python3
"""Print the book version computed from chapter history.

Run from the repo root. Base is the committed VERSION content; each commit
since the one that introduced VERSION adds 0.5 when it adds a chapter file
(internat/outline/*.md), else 0.01 when it only edits/deletes/renames one.
"""
import subprocess
import sys
from decimal import Decimal, InvalidOperation


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def parse_base(text: str) -> int:
    return int(Decimal(text.strip()) * 100)


def commit_increment(added: int, changed: int) -> int:
    if added > 0:
        return 50
    if changed > 0:
        return 1
    return 0


def format_version(hundredths: int) -> str:
    return format(Decimal(hundredths) / 100, "f")


def anchor_commit() -> str:
    output = git("log", "--diff-filter=A", "--format=%H", "--", "VERSION")
    commits = output.split()
    if not commits:
        raise RuntimeError("no commit introduced VERSION")
    return commits[-1]


def compute() -> str:
    hundredths = parse_base(git("show", "HEAD:VERSION"))
    anchor = anchor_commit()
    output = git(
        "log", "--no-merges", "--name-status", "--format=%H", "-z",
        f"{anchor}..HEAD", "--", "internat/outline",
    )
    commits: list[list[tuple[str, str]]] = []
    tokens = output.split("\x00")
    index = 0
    while index < len(tokens):
        token = tokens[index].strip()
        if not token:
            index += 1
            continue
        if len(token) == 40 and all(char in "0123456789abcdef" for char in token):
            commits.append([])
            index += 1
            continue
        paths = 2 if token[0] in "RC" else 1
        commits[-1].append((token, tokens[index + paths]))
        index += paths + 1
    for files in commits:
        added = sum(
            1 for status, path in files
            if status == "A" and path.endswith(".md")
        )
        changed = sum(
            1 for status, path in files
            if status != "A" and path.endswith(".md")
        )
        hundredths += commit_increment(added, changed)
    return format_version(hundredths)


def main() -> int:
    try:
        print(compute())
    except (InvalidOperation, OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

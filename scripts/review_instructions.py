"""Pick the path-scoped review instructions for a pull request's files.

This is the GitLab Duo "custom review instructions" idea for GitHub.
Duo reads ``.gitlab/duo/mr-review-instructions.yaml``. Each entry has
a name, file globs, and instructions that apply when a changed file
matches. Here the same three fields live in
``.agents/review/instructions.toml``::

    [[instructions]]
    name = "Static files"
    file_filters = ["static/**", "!static/vendor/**"]
    instructions = '''
    Keep the CSP: no inline style or script.
    '''

A file matches an entry when at least one plain filter matches it and
no ``!`` filter does. ``REVIEW.md`` stays the main checklist. These
entries only add what matters for one part of the tree.

Glob rules, the same as Duo's and ``.gitignore``-style tools:

- ``*`` matches any characters except ``/``;
- ``?`` matches one character except ``/``;
- ``**/`` matches zero or more whole directories;
- ``**`` at the end matches everything below.

Python 3.12's ``fnmatch`` lets ``*`` cross ``/`` and ``PurePath.match``
does not understand ``**``, so the pattern is turned into a regular
expression here.

    python -m scripts.review_instructions app/api/scores.py README.md
    python -m scripts.review_instructions --file rules.toml \\
        --paths-from files.txt

``--paths-from`` reads one path per line. ``/review-pr`` uses it so a
file name from a pull request never passes through a shell command.
"""

import argparse
import re
import sys
import tomllib

DEFAULT_FILE = ".agents/review/instructions.toml"


def glob_matches(pattern, path):
    """True when ``path`` (with ``/`` separators) matches ``pattern``."""
    return _compile(pattern).fullmatch(path) is not None


def _compile(pattern):
    parts = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts))


def load_instructions(path):
    """The entries in ``path``, checked.

    Raises ``ValueError`` (``tomllib.TOMLDecodeError`` is one) when
    the file is not TOML, an entry misses a field, a filter is not
    text, or two entries share a name.
    """
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    raw = data.get("instructions")
    if not isinstance(raw, list) or not raw:
        raise ValueError("instructions must be a non-empty list of tables")
    entries = []
    names = set()
    for item in raw:
        entry = _checked(item)
        if entry["name"] in names:
            raise ValueError("two entries share a name")
        names.add(entry["name"])
        entries.append(entry)
    return entries


def _checked(item):
    if not isinstance(item, dict):
        raise ValueError("each entry must be a table")
    name = item.get("name")
    filters = item.get("file_filters")
    text = item.get("instructions")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("each entry needs a name")
    if not isinstance(filters, list) or not filters:
        raise ValueError("each entry needs file_filters")
    if not all(isinstance(value, str) and value for value in filters):
        raise ValueError("each file filter must be text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("each entry needs instructions")
    return {"name": name, "file_filters": filters, "instructions": text}


def matching_instructions(entries, paths):
    """``[(entry, [matching paths]), ...]`` in the order of ``entries``."""
    matched = []
    for entry in entries:
        plain = [f for f in entry["file_filters"] if not f.startswith("!")]
        negated = [f[1:] for f in entry["file_filters"] if f.startswith("!")]
        hits = [
            path
            for path in paths
            if any(glob_matches(pattern, path) for pattern in plain)
            and not any(glob_matches(pattern, path) for pattern in negated)
        ]
        if hits:
            matched.append((entry, hits))
    return matched


def render(matched):
    """Markdown for the reviewer: one section per matching entry."""
    if not matched:
        return "No path instructions match these files.\n"
    sections = ["# Path instructions\n"]
    for entry, hits in matched:
        files = ", ".join(f"`{path}`" for path in hits)
        sections.append(
            f"## {entry['name']}\n\nFiles: {files}\n\n"
            f"{entry['instructions'].strip()}\n"
        )
    return "\n".join(sections)


def main(argv=None):
    """Print the instructions for the given paths. Exit 1 on a bad file."""
    parser = argparse.ArgumentParser(
        description="Print the review instructions for changed files."
    )
    parser.add_argument("--file", default=DEFAULT_FILE)
    parser.add_argument(
        "--paths-from",
        help="a file with one changed path per line, such as the output "
        "of `gh pr diff <N> --name-only`",
    )
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    try:
        entries = load_instructions(args.file)
        paths = list(args.paths)
        if args.paths_from:
            # A file name in a PR can contain "$(...)" or ";". Read
            # from a file, it never reaches a shell command line.
            with open(args.paths_from, encoding="utf-8") as handle:
                paths += [line for line in handle.read().splitlines() if line]
    except (OSError, ValueError):
        print(
            "review_instructions: cannot read the rules or the paths",
            file=sys.stderr,
        )
        return 1
    print(render(matching_instructions(entries, paths)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

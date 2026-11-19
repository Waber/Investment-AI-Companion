"""Path-scoped review instructions, the GitLab Duo idea on GitHub.

GitLab Duo reads ``.gitlab/duo/mr-review-instructions.yaml``: each
entry has a name, a list of file globs, and the text to apply when a
changed file matches. This repository keeps the same three fields in
``.agents/review/instructions.toml``. TOML because Python 3.12 reads
it with the standard library (``tomllib``); a YAML parser would be a
new dependency.

The matching is code, not something the reviewer model guesses, so
these tests pin the glob rules.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.review_instructions import (
    DEFAULT_FILE,
    glob_matches,
    load_instructions,
    main,
    matching_instructions,
)

ROOT = Path(__file__).resolve().parent.parent


# --- glob_matches ------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("app/ui/*.py", "app/ui/router.py", True),
        ("app/ui/*.py", "app/ui/templates/x.py", False),
        ("app/**/*.py", "app/scoring.py", True),
        ("app/**/*.py", "app/ui/templates/deep/x.py", True),
        ("**/*.md", "README.md", True),
        ("**/*.md", "docs/reviews/a.md", True),
        ("static/**", "static/vendor/htmx.min.js", True),
        ("fixtures/*.json", "fixtures/demo-v2.json", True),
        ("fixtures/*.json", "fixtures/demo-v2xjson", False),
        ("fixtures/*.json", "fixtures/demo-v2.json.bak", False),
        ("docs?x", "docs/x", False),
        ("tests/test_?.py", "tests/test_a.py", True),
        ("tests/test_?.py", "tests/test_ab.py", False),
        ("alembic/versions/*.py", "alembic/env.py", False),
    ],
    ids=lambda value: str(value),
)
def test_glob_rules(pattern, path, expected):
    assert glob_matches(pattern, path) is expected


# --- matching_instructions ---------------------------------------------


def _entry(name, *filters, text="Check it."):
    return {"name": name, "file_filters": list(filters), "instructions": text}


def test_a_negated_filter_removes_a_file_that_a_positive_one_matched():
    entries = [_entry("Static", "static/**", "!static/vendor/**")]

    matched = matching_instructions(
        entries, ["static/ui.js", "static/vendor/htmx.min.js"]
    )

    assert matched == [(entries[0], ["static/ui.js"])]


def test_an_entry_with_only_negated_filters_matches_nothing():
    entries = [_entry("Odd", "!docs/**")]

    assert matching_instructions(entries, ["app/scoring.py"]) == []


def test_entries_keep_file_order_and_list_each_matching_path():
    ui = _entry("UI", "app/ui/**")
    api = _entry("API", "app/api/**")

    matched = matching_instructions(
        [ui, api], ["app/api/scores.py", "app/ui/router.py", "README.md"]
    )

    assert matched == [
        (ui, ["app/ui/router.py"]),
        (api, ["app/api/scores.py"]),
    ]


# --- load_instructions -------------------------------------------------


def test_a_valid_file_loads(tmp_path):
    path = tmp_path / "instructions.toml"
    path.write_text(
        "[[instructions]]\n"
        'name = "UI"\n'
        'file_filters = ["app/ui/**"]\n'
        'instructions = "Keep the CSP."\n',
        encoding="utf-8",
    )

    assert load_instructions(path) == [
        {
            "name": "UI",
            "file_filters": ["app/ui/**"],
            "instructions": "Keep the CSP.",
        }
    ]


@pytest.mark.parametrize(
    "body",
    [
        "[[instructions]]\nfile_filters = ['a']\ninstructions = 'x'\n",
        "[[instructions]]\nname = 'A'\ninstructions = 'x'\n",
        "[[instructions]]\nname = 'A'\nfile_filters = []\n"
        "instructions = 'x'\n",
        "[[instructions]]\nname = 'A'\nfile_filters = ['a']\n",
        "[[instructions]]\nname = 'A'\nfile_filters = [1]\n"
        "instructions = 'x'\n",
        "[[instructions]]\nname = ' '\nfile_filters = ['a']\n"
        "instructions = 'x'\n",
        (
            "[[instructions]]\nname = 'A'\nfile_filters = ['a']\n"
            "instructions = 'x'\n"
            "[[instructions]]\nname = 'A'\nfile_filters = ['b']\n"
            "instructions = 'y'\n"
        ),
        "instructions = 'not a list'\n",
        "[[instructions]\n",
    ],
    ids=[
        "no-name",
        "no-filters",
        "empty-filters",
        "no-text",
        "filter-not-text",
        "blank-name",
        "duplicate-name",
        "not-a-list",
        "not-toml",
    ],
)
def test_a_broken_file_is_refused(tmp_path, body):
    path = tmp_path / "instructions.toml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError):
        load_instructions(path)


# --- the repository's own file ----------------------------------------


def _tracked_files():
    # Tracked files only. An ignored local file (a demo database, a
    # cache) must not keep a dead filter alive.
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return [path for path in listed.split("\0") if path]


def test_every_repository_filter_still_matches_a_tracked_file():
    # A rename that leaves a glob pointing at nothing would silently
    # switch that part of a rule off. This is the drift check. Each
    # plain filter must match on its own; a "!" filter only removes.
    entries = load_instructions(ROOT / DEFAULT_FILE)
    files = _tracked_files()

    dead = [
        f"{entry['name']}: {pattern}"
        for entry in entries
        for pattern in entry["file_filters"]
        if not pattern.startswith("!")
        and not any(glob_matches(pattern, path) for path in files)
    ]

    assert entries
    assert dead == []


# --- main --------------------------------------------------------------


def test_main_prints_the_matching_instructions(tmp_path, capsys):
    path = tmp_path / "instructions.toml"
    path.write_text(
        "[[instructions]]\n"
        'name = "UI"\n'
        'file_filters = ["app/ui/**"]\n'
        'instructions = "Keep the CSP."\n',
        encoding="utf-8",
    )

    code = main(["--file", str(path), "app/ui/router.py", "README.md"])

    out = capsys.readouterr().out
    assert code == 0
    assert "## UI" in out
    assert "`app/ui/router.py`" in out
    assert "Keep the CSP." in out
    assert "README.md" not in out


def test_main_reads_the_changed_files_from_a_file(tmp_path, capsys):
    # A PR can name a file "a;$(rm -rf x).py". Read from a file, the
    # names never pass through a shell command line.
    rules = tmp_path / "instructions.toml"
    rules.write_text(
        "[[instructions]]\n"
        'name = "UI"\n'
        'file_filters = ["app/ui/**"]\n'
        'instructions = "Keep the CSP."\n',
        encoding="utf-8",
    )
    names = tmp_path / "files.txt"
    names.write_text(
        "app/ui/a;$(rm -rf x).py\n\nREADME.md\n", encoding="utf-8"
    )

    code = main(["--file", str(rules), "--paths-from", str(names)])

    out = capsys.readouterr().out
    assert code == 0
    assert "`app/ui/a;$(rm -rf x).py`" in out
    assert "README.md" not in out


def test_the_matcher_runs_as_a_lone_file_in_isolated_mode(tmp_path):
    # /review-pr copies this script from the base branch and runs it
    # with `python -I`, away from the repository. It must keep to the
    # standard library and must not import application code.
    script = tmp_path / "review_instructions.py"
    script.write_bytes((ROOT / "scripts/review_instructions.py").read_bytes())
    rules = tmp_path / "instructions.toml"
    rules.write_text(
        "[[instructions]]\n"
        'name = "UI"\n'
        'file_filters = ["app/ui/**"]\n'
        'instructions = "Keep the CSP."\n',
        encoding="utf-8",
    )
    names = tmp_path / "files.txt"
    names.write_text("app/ui/router.py\n", encoding="utf-8")

    done = subprocess.run(
        [
            sys.executable,
            "-I",
            str(script),
            "--file",
            str(rules),
            "--paths-from",
            str(names),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert done.returncode == 0, done.stderr
    assert "## UI" in done.stdout


def test_main_says_so_when_nothing_matches(tmp_path, capsys):
    path = tmp_path / "instructions.toml"
    path.write_text(
        "[[instructions]]\n"
        'name = "UI"\n'
        'file_filters = ["app/ui/**"]\n'
        'instructions = "Keep the CSP."\n',
        encoding="utf-8",
    )

    code = main(["--file", str(path), "README.md"])

    assert code == 0
    assert "No path instructions match" in capsys.readouterr().out


def test_main_reports_a_broken_file_without_a_traceback(tmp_path, capsys):
    path = tmp_path / "instructions.toml"
    path.write_text("[[instructions]\n", encoding="utf-8")

    code = main(["--file", str(path), "README.md"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "Traceback" not in captured.err

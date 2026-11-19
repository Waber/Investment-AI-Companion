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


def _repository_files():
    skipped = {".git", ".venv", "__pycache__", ".pytest_cache"}
    return [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and not skipped & set(path.relative_to(ROOT).parts)
    ]


def test_every_repository_entry_still_matches_a_file():
    # A rename that leaves a glob pointing at nothing would silently
    # switch that rule off. This is the drift check.
    entries = load_instructions(ROOT / DEFAULT_FILE)
    files = _repository_files()

    unmatched = [
        entry["name"]
        for entry in entries
        if not matching_instructions([entry], files)
    ]

    assert entries
    assert unmatched == []


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

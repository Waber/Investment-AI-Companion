"""The helper that turns a code-review report into a pending GitHub review.

GitHub accepts an inline review comment only on a line that the pull
request diff shows on the new side. One comment on any other line makes
the whole request fail with 422, so the helper must sort findings into
inline comments and a summary section before anything is sent.

A review created without an ``event`` stays PENDING. Only its author
sees it until they submit it in the GitHub UI. That is the safety
property the tests below pin.
"""

import json

import pytest

from scripts.pending_review import (
    MARKER_PREFIX,
    build_payload,
    commentable_lines,
    main,
)

HEAD = "d041b1c0db5d5c9159765ee93533296af0dbb75f"

DIFF = """\
diff --git a/app/scoring.py b/app/scoring.py
index 1111111..2222222 100644
--- a/app/scoring.py
+++ b/app/scoring.py
@@ -10,3 +10,4 @@ def one():
 context_ten = 1
-removed_eleven = 2
+added_eleven = 2
+added_twelve = 3
 context_thirteen = 4
@@ -40 +41 @@ def two():
-old = 1
+new = 1
\\ No newline at end of file
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,2 @@
+# Title
+Body
diff --git a/docs/gone.md b/docs/gone.md
deleted file mode 100644
index 4444444..0000000
--- a/docs/gone.md
+++ /dev/null
@@ -1,2 +0,0 @@
-# Gone
-Text
"""


def _finding(**overrides):
    finding = {
        "id": "F1",
        "severity": "Important",
        "title": "A retry inserts twice",
        "path": "app/scoring.py",
        "line": 11,
        "body": "The second attempt runs the insert again.",
    }
    finding.update(overrides)
    return finding


def _report(*findings, summary="1 Critical, 0 Important, 0 Minor"):
    return {"summary": summary, "findings": list(findings)}


# --- commentable_lines -------------------------------------------------


def test_added_and_context_lines_are_commentable_on_the_new_side():
    lines = commentable_lines(DIFF)

    assert lines["app/scoring.py"] == {10, 11, 12, 13, 41}


HEADER_LOOKALIKE_DIFF = """\
diff --git a/notes.md b/notes.md
index 1111111..2222222 100644
--- a/notes.md
+++ b/notes.md
@@ -1,2 +1,3 @@
 keep
-last
\\ No newline at end of file
+last
+++ b/evil.md
@@ -10 +11 @@
-x
+y
"""


def test_an_added_line_that_looks_like_a_file_header_stays_content():
    # The added text "++ b/evil.md" is printed as "+++ b/evil.md".
    # The parser knows it is still inside a hunk only if it counts
    # new-side lines exactly: a removed line or the "No newline"
    # marker must not use up the count, or the next line is read
    # as a new file header.
    lines = commentable_lines(HEADER_LOOKALIKE_DIFF)

    assert lines == {"notes.md": {1, 2, 3, 11}}


def test_a_hunk_header_without_a_count_covers_one_line():
    diff = (
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -40 +41 @@\n"
        "-old\n"
        "+new\n"
        "@@ -50 +51 @@\n"
        "-old2\n"
        "+new2\n"
    )

    assert commentable_lines(diff) == {"a.py": {41, 51}}


def test_a_short_hunk_does_not_swallow_the_next_file():
    # The first hunk promises three new lines but has one. A
    # hand-trimmed diff looks like this. "diff --git" still starts
    # the next file, so b.py keeps its lines.
    diff = (
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -1 +1,3 @@\n"
        "+one\n"
        "diff --git a/b.py b/b.py\n"
        "--- a/b.py\n"
        "+++ b/b.py\n"
        "@@ -5 +5 @@\n"
        "-old\n"
        "+new\n"
    )

    lines = commentable_lines(diff)

    assert lines["b.py"] == {5}
    assert lines["a.py"] == {1}


def test_a_new_file_is_commentable_from_line_one():
    assert commentable_lines(DIFF)["docs/new.md"] == {1, 2}


def test_a_deleted_file_has_no_new_side_lines():
    assert "docs/gone.md" not in commentable_lines(DIFF)


def test_an_empty_diff_has_no_commentable_lines():
    assert commentable_lines("") == {}


# --- build_payload -----------------------------------------------------


def test_the_payload_has_no_event_so_the_review_stays_pending():
    payload = build_payload(_report(_finding()), DIFF, HEAD)

    assert "event" not in payload
    assert payload["commit_id"] == HEAD


def test_a_finding_on_a_diff_line_becomes_an_inline_comment():
    payload = build_payload(_report(_finding()), DIFF, HEAD)

    assert payload["comments"] == [
        {
            "path": "app/scoring.py",
            "line": 11,
            "side": "RIGHT",
            "body": (
                "**F1, Important**: A retry inserts twice\n\n"
                "The second attempt runs the insert again."
            ),
        }
    ]


def test_a_finding_outside_the_diff_goes_to_the_summary_not_inline():
    outside = _finding(id="F2", path="app/scoring.py", line=500)

    payload = build_payload(_report(outside), DIFF, HEAD)

    assert payload["comments"] == []
    assert "app/scoring.py:500" in payload["body"]
    assert "A retry inserts twice" in payload["body"]


def test_a_finding_without_a_line_goes_to_the_summary():
    general = _finding(id="F3", path=None, line=None, title="No PR test")

    payload = build_payload(_report(general), DIFF, HEAD)

    assert payload["comments"] == []
    assert "No PR test" in payload["body"]


def test_the_summary_starts_with_the_count_and_ends_with_the_marker():
    payload = build_payload(_report(_finding()), DIFF, HEAD)

    assert payload["body"].startswith("1 Critical, 0 Important, 0 Minor")
    # A literal, not MARKER_PREFIX: /review-pr finds earlier rounds by
    # this exact text, so a changed prefix must fail here.
    assert (
        payload["body"]
        .rstrip()
        .endswith("<!-- code-reviewer head=" + HEAD + " -->")
    )
    assert MARKER_PREFIX == "<!-- code-reviewer head="


def test_an_inline_comment_lists_the_other_locations():
    spread = _finding(other_locations=["app/y.py:12", "app/z.py:40"])

    body = build_payload(_report(spread), DIFF, HEAD)["comments"][0]["body"]

    assert "Also at: `app/y.py:12`, `app/z.py:40`" in body


def test_a_summary_row_keeps_other_locations_and_the_suggestion():
    outside = _finding(
        path="app/limits.py",
        line=7,
        other_locations=["app/y.py:12"],
        suggestion="LIMIT = 50",
    )

    body = build_payload(_report(outside), DIFF, HEAD)["body"]

    assert "Also at: `app/y.py:12`" in body
    # Outside the diff a GitHub suggestion cannot apply, so it is
    # shown as plain code.
    assert "```\n  LIMIT = 50\n  ```" in body
    assert "```suggestion" not in body


def test_the_summary_lists_the_status_of_earlier_findings():
    report = _report(_finding())
    report["previous_findings"] = [
        {"id": "F2 (round 1)", "status": "fixed", "note": "now Decimal"},
        {"id": "F3 (round 1)", "status": "open", "note": ""},
    ]

    body = build_payload(report, DIFF, HEAD)["body"]

    assert "### Earlier findings" in body
    assert "- F2 (round 1): fixed. now Decimal" in body
    assert "- F3 (round 1): open" in body


def test_comments_are_ordered_critical_then_important_then_minor():
    minor = _finding(id="F1", severity="Minor", line=10)
    critical = _finding(id="F2", severity="Critical", line=12)
    important = _finding(id="F3", severity="Important", line=13)

    payload = build_payload(_report(minor, critical, important), DIFF, HEAD)

    assert [comment["line"] for comment in payload["comments"]] == [
        12,
        13,
        10,
    ]


def test_a_pre_existing_finding_is_marked_in_its_label():
    old = _finding(pre_existing=True)

    payload = build_payload(_report(old), DIFF, HEAD)

    assert payload["comments"][0]["body"].startswith(
        "**F1, Important (pre-existing)**: "
    )


def test_the_finding_id_is_shown_inline_and_in_a_summary_row():
    # "F3 (round 1): open" in a later round must point at something
    # Przemek can find on the PR.
    inline = _finding(id="F3")
    outside = _finding(id="F4", path=None, line=None, title="No PR test")

    payload = build_payload(_report(inline, outside), DIFF, HEAD)

    assert payload["comments"][0]["body"].startswith("**F3, Important**: ")
    assert "- **F4, Important**: No PR test" in payload["body"]


def test_a_finding_without_an_id_keeps_the_plain_label():
    unnamed = _finding()
    del unnamed["id"]

    body = build_payload(_report(unnamed), DIFF, HEAD)["comments"][0]["body"]

    assert body.startswith("**Important**: ")


def test_a_two_paragraph_body_stays_inside_its_summary_item():
    # CommonMark ends a list item at a line that starts in column 0.
    # Every line of the body is indented, so "Also at:" still belongs
    # to the item.
    outside = _finding(
        path=None,
        line=None,
        body="First paragraph.\n\nSecond paragraph.",
        other_locations=["app/y.py:12"],
    )

    body = build_payload(_report(outside), DIFF, HEAD)["body"]

    assert (
        "  First paragraph.\n\n  Second paragraph.\n"
        "  Also at: `app/y.py:12`"
    ) in body


def test_a_suggestion_becomes_a_github_suggestion_block():
    fixed = _finding(suggestion="added_eleven = 20")

    payload = build_payload(_report(fixed), DIFF, HEAD)

    assert payload["comments"][0]["body"].endswith(
        "```suggestion\nadded_eleven = 20\n```"
    )


def test_a_suggestion_with_backticks_gets_a_longer_fence():
    fixed = _finding(suggestion='text = "```"')

    body = build_payload(_report(fixed), DIFF, HEAD)["comments"][0]["body"]

    assert body.endswith('````suggestion\ntext = "```"\n````')


def test_an_unknown_severity_is_refused():
    with pytest.raises(ValueError, match="severity"):
        build_payload(_report(_finding(severity="Blocker")), DIFF, HEAD)


@pytest.mark.parametrize(
    "sha",
    ["", "d041b1c", "Z" * 40, HEAD + "0"],
    ids=["empty", "short", "not-hex", "too-long"],
)
def test_a_head_that_is_not_a_full_commit_sha_is_refused(sha):
    with pytest.raises(ValueError, match="commit"):
        build_payload(_report(_finding()), DIFF, sha)


# --- main --------------------------------------------------------------


def test_main_prints_the_payload_as_json(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report(_finding())), encoding="utf-8")
    diff = tmp_path / "pr.diff"
    diff.write_text(DIFF, encoding="utf-8")

    code = main(["--report", str(report), "--diff", str(diff), "--head", HEAD])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["comments"][0]["line"] == 11
    assert "event" not in payload


def test_main_reports_a_bad_report_without_a_traceback(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text("{not json", encoding="utf-8")
    diff = tmp_path / "pr.diff"
    diff.write_text(DIFF, encoding="utf-8")

    code = main(["--report", str(report), "--diff", str(diff), "--head", HEAD])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "report" in captured.err
    assert "Traceback" not in captured.err

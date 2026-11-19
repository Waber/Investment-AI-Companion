"""Turn a code-review report into the JSON for a pending GitHub review.

The ``/review-pr`` skill runs the ``code-reviewer`` agent, which writes
a report as JSON. This module reads that report and the pull request
diff and prints the request body for GitHub's "create a review"
endpoint (``POST /repos/{owner}/{repo}/pulls/{number}/reviews``).
It does not call GitHub. ``gh api --input`` sends what it prints.

Why a pending review: the body has no ``event`` field, so GitHub
creates the review in the PENDING state. Only its author sees it. The
comments are published when the author presses "Submit review" in the
GitHub UI. An agent's review is a draft for Przemek, never his
approval (``REVIEW.md``).

Why the diff is needed: GitHub accepts an inline comment only on a
line that the diff shows on the new side (an added line or a context
line inside a hunk). A single comment on any other line makes the
whole request fail with 422. So a finding on such a line, or a
finding with no line, is listed in the review summary instead.

The report is a JSON object::

    {
      "summary": "1 Critical, 0 Important, 1 Minor\\n\\n...",
      "findings": [
        {"id": "F1", "severity": "Critical", "title": "...",
         "path": "app/x.py", "line": 12, "body": "...",
         "pre_existing": false, "suggestion": "replacement line",
         "other_locations": ["app/y.py:40"]}
      ],
      "previous_findings": [
        {"id": "F2 (round 1)", "status": "fixed", "note": "..."}
      ]
    }

``severity`` is Critical, Important, or Minor (``REVIEW.md``).
``path``, ``line``, ``pre_existing``, ``suggestion``, and
``other_locations`` are optional, and so is ``previous_findings``.
A ``suggestion`` replaces the commented line when Przemek accepts it.
On a finding outside the diff it is shown as plain code instead.
``other_locations`` becomes an "Also at:" line. Earlier findings and
their status (fixed, answered, open) are listed in the summary.

The summary ends with a hidden marker that names the reviewed head
commit. The next round reads it to review only what changed since.

    python -m scripts.pending_review --report report.json \\
        --diff pr.diff --head <40-character head SHA> > payload.json
"""

import argparse
import json
import re
import sys

MARKER_PREFIX = "<!-- code-reviewer head="
SEVERITIES = ("Critical", "Important", "Minor")

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def commentable_lines(diff_text):
    """``{path: {line, ...}}`` for every line GitHub can comment on.

    The numbers are new-side line numbers. A removed line has no new
    line number, so it does not move the counter. A deleted file has
    no new side and is left out.
    """
    lines = {}
    path = None
    new_line = 0
    remaining = 0
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            path = None
            remaining = 0
            continue
        if remaining == 0:
            path, new_line, remaining = _header(raw, path, new_line)
            continue
        if raw.startswith("\\"):
            # "\ No newline at end of file" describes the line above.
            continue
        if raw.startswith("-"):
            continue
        if path is not None:
            lines.setdefault(path, set()).add(new_line)
        new_line += 1
        remaining -= 1
    return lines


def _header(raw, path, new_line):
    """Read a file or hunk header line outside a hunk body.

    Returns the path, the next new-side line number, and how many
    new-side lines the hunk still has.
    """
    if raw.startswith("+++ "):
        # A deleted file is "+++ /dev/null". Its hunks have no new-side
        # lines, so it never gets an entry.
        target = raw[4:].strip().strip('"')
        return target.removeprefix("b/"), 0, 0
    match = _HUNK.match(raw)
    if match is None:
        return path, new_line, 0
    count = 1 if match.group(2) is None else int(match.group(2))
    return path, int(match.group(1)), count


def build_payload(report, diff_text, head_sha):
    """The request body for a PENDING review of ``head_sha``.

    Raises ``ValueError`` for a head that is not a full commit SHA or
    a finding whose severity is not one of ``SEVERITIES``.
    """
    if not isinstance(head_sha, str) or not _SHA.match(head_sha):
        raise ValueError("head must be a full 40-character commit SHA")
    findings = sorted(
        report.get("findings", []),
        key=lambda item: _severity_rank(item.get("severity")),
    )
    allowed = commentable_lines(diff_text)
    comments = []
    elsewhere = []
    for finding in findings:
        path = finding.get("path")
        line = finding.get("line")
        if path in allowed and line in allowed[path]:
            comments.append(
                {
                    "path": path,
                    "line": line,
                    "side": "RIGHT",
                    "body": _comment_body(finding),
                }
            )
        else:
            elsewhere.append(finding)
    body = _summary_body(
        report.get("summary", ""),
        elsewhere,
        report.get("previous_findings", []),
        head_sha,
    )
    return {"commit_id": head_sha, "body": body, "comments": comments}


def _severity_rank(severity):
    if severity not in SEVERITIES:
        raise ValueError("severity must be Critical, Important, or Minor")
    return SEVERITIES.index(severity)


def _label(finding):
    label = finding["severity"]
    if finding.get("pre_existing"):
        label += " (pre-existing)"
    return f"**{label}**: {finding['title']}"


def _fence(text):
    """A code fence longer than any backtick run inside ``text``."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _also_at(finding):
    """``Also at: ...`` for the same bug elsewhere, or an empty string.

    REVIEW.md asks for every location of a class of bug, so the author
    fixes them all in one round. A later round does not repeat it.
    """
    places = finding.get("other_locations") or []
    if not places:
        return ""
    return "Also at: " + ", ".join(f"`{place}`" for place in places)


def _comment_body(finding):
    parts = [_label(finding), finding.get("body", ""), _also_at(finding)]
    suggestion = finding.get("suggestion")
    if suggestion is not None:
        fence = _fence(suggestion)
        parts.append(f"{fence}suggestion\n{suggestion}\n{fence}")
    return "\n\n".join(part for part in parts if part)


def _summary_row(finding):
    where = ""
    if finding.get("path"):
        where = finding["path"]
        if finding.get("line") is not None:
            where += f":{finding['line']}"
        where = f" (`{where}`)"
    rows = [f"- {_label(finding)}{where}"]
    for extra in (finding.get("body"), _also_at(finding)):
        if extra:
            rows.append(f"  {extra}")
    suggestion = finding.get("suggestion")
    if suggestion is not None:
        # Outside the diff GitHub cannot apply a suggestion, so the fix
        # is shown as plain code, indented under its list item.
        fence = _fence(suggestion)
        code = "\n".join(f"  {line}" for line in suggestion.splitlines())
        rows.append(f"  {fence}\n{code}\n  {fence}")
    return rows


def _summary_body(summary, elsewhere, previous, head_sha):
    parts = [summary.strip()]
    if elsewhere:
        rows = [row for finding in elsewhere for row in _summary_row(finding)]
        parts.append(
            "### Findings without an inline comment\n\n"
            "These lines are not part of the diff, or the finding has "
            "no line.\n\n" + "\n".join(rows)
        )
    if previous:
        rows = []
        for item in previous:
            row = f"- {item['id']}: {item['status']}"
            if item.get("note"):
                row += f". {item['note']}"
            rows.append(row)
        parts.append("### Earlier findings\n\n" + "\n".join(rows))
    parts.append(f"{MARKER_PREFIX}{head_sha} -->")
    return "\n\n".join(part for part in parts if part)


def main(argv=None):
    """Print the payload. Exit 1 with one line on stderr on bad input."""
    parser = argparse.ArgumentParser(
        description="Build a pending GitHub review from a review report."
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.report, encoding="utf-8") as handle:
            report = json.load(handle)
        with open(args.diff, encoding="utf-8") as handle:
            diff_text = handle.read()
        payload = build_payload(report, diff_text, args.head)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # json.JSONDecodeError is a ValueError. The message stays
        # fixed so a report never echoes into the terminal by accident.
        print(
            "pending_review: the report, the diff, or the head is not "
            "valid",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

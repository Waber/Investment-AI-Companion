"""The pytest SECRET_KEY placeholder is allowlisted for gitleaks.

``tests/conftest.py`` line 7 sets a fixed key so the suite can start
without a developer environment file. It is not a credential. The
allowlist names that file and that exact string.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "test-secret-key-for-pytest-0123456789"


def test_conftest_placeholder_is_on_line_7_and_allowlisted():
    conftest = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    line_7 = conftest.splitlines()[6]

    config = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")

    assert PLACEHOLDER in line_7
    assert "setdefault" in line_7
    assert PLACEHOLDER in config
    assert "tests/conftest" in config
    assert "useDefault = true" in config

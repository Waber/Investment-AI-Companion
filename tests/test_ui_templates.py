"""Templates stay escaped, catalog-driven, and free of CDN URLs."""

import hashlib
import re
from pathlib import Path

from app.ui.templating import templates

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "app" / "ui" / "templates"
STATIC_DIR = ROOT / "static"
_JINJA = re.compile(r"\{#.*?#\}|\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
_TAG = re.compile(r"<[^>]*>")
_LETTERS = re.compile(r"[^A-Za-z]+")
_CDN = (
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "ajax.googleapis.com",
    "htmx.org",
)


def test_html_templates_autoescape():
    for path in TEMPLATE_DIR.rglob("*.html"):
        name = path.relative_to(TEMPLATE_DIR).as_posix()
        templates.env.get_template(name)
        assert templates.env.autoescape(name) is True


def test_htmx_config_disables_the_indicator_style():
    """The config tag must sit before the script so htmx reads it.

    Without this, htmx injects an inline style. That style is not
    allowed by the page CSP.
    """
    text = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")
    marker = (
        '<meta name="htmx-config" content='
        '\'{"includeIndicatorStyles":false,'
        '"allowEval":false,"allowScriptTags":false}\'>'
    )
    script = '<script src="/static/vendor/htmx-2.0.10.min.js">'
    assert marker in text
    assert text.find(marker) < text.find(script)


def test_templates_have_no_safe_filter_or_hardcoded_text():
    for path in TEMPLATE_DIR.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "|safe" not in text
        assert re.search(r"\|\s+safe\b", text) is None
        assert "javascript:" not in text.casefold()
        leftover = _LETTERS.sub("", _TAG.sub(" ", _JINJA.sub(" ", text)))
        assert leftover == "", f"{path.name}: {leftover}"


def test_local_assets_are_not_a_cdn():
    css = (STATIC_DIR / "ui.css").read_text(encoding="utf-8")
    script = (STATIC_DIR / "vendor" / "htmx-2.0.10.min.js").read_text(
        encoding="utf-8"
    )
    license_text = (STATIC_DIR / "vendor" / "htmx-LICENSE.txt").read_text(
        encoding="utf-8"
    )
    script_path = STATIC_DIR / "vendor" / "htmx-2.0.10.min.js"
    readme = (STATIC_DIR / "vendor" / "README.txt").read_text(encoding="utf-8")
    digest = hashlib.sha256(script_path.read_bytes()).hexdigest()
    assert "htmx" in script
    assert "Zero-Clause BSD" in license_text
    assert "2.0.10" in readme
    assert "0BSD" in readme
    assert f"sha256: {digest}" in readme
    for blob in (css, script):
        lowered = blob.casefold()
        for host in _CDN:
            assert host not in lowered
        assert "url(http" not in lowered
        assert "@import" not in lowered or "http" not in lowered
    assert ":focus-visible" in css
    compact = re.sub(r"\s+", "", css.casefold())
    assert "outline:none" not in compact
    assert "outline:0" not in compact

"""Small HTML helpers for the /ui tests.

The parser is the standard library. ``convert_charrefs`` stays at its
default so a quoted attribute comes back decoded, and the tests can
still look at the raw response when they need to prove escaping.
"""

from html.parser import HTMLParser


class PageParser(HTMLParser):
    """Collect metric cells, anchors, and the website field."""

    def __init__(self):
        super().__init__()
        self.period_type = None
        self.capture_cell = False
        self.cell_field = None
        self.cell_period = None
        self.cell_buf = []
        self.cells = {}
        self.hrefs = []
        self.in_website = False
        self.website_buf = []
        self.website = {"hrefs": [], "rels": [], "text": []}

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "a":
            self.hrefs.append(attr.get("href"))
            if self.in_website:
                self.website["hrefs"].append(attr.get("href"))
                self.website["rels"].append(attr.get("rel"))
        if tag == "table":
            self.period_type = attr.get("data-period-type")
        if tag == "td":
            self.capture_cell = True
            self.cell_field = attr.get("data-field")
            self.cell_period = attr.get("data-period")
            self.cell_buf = []
        if tag == "dd" and attr.get("data-field") == "website":
            self.in_website = True
            self.website_buf = []

    def handle_endtag(self, tag):
        if tag == "td" and self.capture_cell:
            text = "".join(self.cell_buf).strip()
            key = (self.period_type, self.cell_field, self.cell_period)
            self.cells[key] = text
            self.capture_cell = False
        if tag == "dd" and self.in_website:
            self.website["text"].append("".join(self.website_buf).strip())
            self.in_website = False

    def handle_data(self, data):
        if self.capture_cell:
            self.cell_buf.append(data)
        if self.in_website:
            self.website_buf.append(data)


def parse_page(html):
    parser = PageParser()
    parser.feed(html)
    return parser


def plain(text):
    """Turn the Polish thousands separator into a normal space."""
    return text.replace("\u00a0", " ")


class FormParser(HTMLParser):
    """Ids, labels, and inputs for the accessibility checks."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.labels = []
        self.controls = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        element_id = attr.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag == "label" and attr.get("for"):
            self.labels.append(attr["for"])
        if tag in {"input", "textarea", "select"}:
            self.controls.append(attr)


def parse_form(html):
    parser = FormParser()
    parser.feed(html)
    return parser


def assert_labeled(html):
    """Every visible input has a label, and error ids point at real elements.

    A hidden field is not a control the user labels. The language
    switch posts ``next`` that way.
    """
    parsed = parse_form(html)
    visible = [
        control
        for control in parsed.controls
        if control.get("type") != "hidden"
    ]
    assert visible
    for control in visible:
        element_id = control.get("id")
        assert element_id
        assert element_id in parsed.labels
        described = control.get("aria-describedby", "")
        if control.get("aria-invalid") == "true":
            assert described
        for token in described.split():
            assert token in parsed.ids


class FormInParagraph(HTMLParser):
    """Records a <form> that starts while a <p> is still open.

    The HTML parser in a browser closes the <p> at that point. A
    one-button form meant to sit beside the company name (the heart,
    the sticky note) would then drop onto its own line.
    """

    def __init__(self):
        super().__init__()
        self.open_paragraphs = 0
        self.nested = False

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.open_paragraphs += 1
        if tag == "form" and self.open_paragraphs:
            self.nested = True

    def handle_endtag(self, tag):
        if tag == "p" and self.open_paragraphs:
            self.open_paragraphs -= 1


def assert_no_dangerous_href(html):
    """No anchor may use a scheme other than http(s) or a relative path."""
    lowered = html.casefold()
    for scheme in ("javascript:", "data:", "vbscript:"):
        assert f'href="{scheme}' not in lowered
        assert f"href='{scheme}" not in lowered
    parser = parse_page(html)
    for href in parser.hrefs:
        if not href:
            continue
        scheme = href.split(":", 1)[0].casefold() if ":" in href else ""
        assert scheme in {"", "http", "https"}

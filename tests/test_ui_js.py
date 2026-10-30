"""``static/ui.js`` run in node with fake browser objects.

The script has no build step and no npm packages, so node can run it
as it is. The harness below gives it a fake ``document``, a fake
``window.location``, a fake ``FormData``, and fake elements. It fires
the HTMX events the script listens to and prints what the script did
as JSON. No browser starts. The test is skipped when node is not
installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_ui_research import (
    _company,
    _is_create_post,
    _note,
    _panel_actions,
    _thesis,
)

UI_JS = Path(__file__).resolve().parents[1] / "static" / "ui.js"
# The href of the marked link in the harness.
_LINK = "http://127.0.0.1/ui/companies/7/research"
# The page the harness runs on: the company page with the panel open,
# as the language switch returns to it.
_PAGE = "http://127.0.0.1/ui/instruments/7?research=open"

# CommonJS (.cjs), so a package.json above tmp_path cannot turn it into
# an ES module. vm runs ui.js in a fresh context whose only browser
# globals are the fakes, so a call to anything else fails the run.
# URL and URLSearchParams are node's own: the same WHATWG classes that
# browsers have.
_HARNESS = r"""
"use strict";
const fs = require("fs");
const vm = require("vm");

const handlers = {};
const assigned = [];
const location = {
  href: "http://127.0.0.1/ui/instruments/7?research=open",
  assign: (url) => assigned.push(url),
};

function fakeElement(tagName, attributes, extra) {
  const names = new Set(attributes);
  return Object.assign(
    {
      tagName: tagName,
      hasAttribute: (name) => names.has(name),
      removeAttribute: (name) => names.delete(name),
      getAttributeNames: () => [...names].sort(),
    },
    extra
  );
}

// ``fields`` are the [name, value] pairs that FormData reads.
function fakeForm(attributes, method, action, fields) {
  return fakeElement("FORM", attributes, {
    method: method,
    action: action,
    fields: fields,
    submitted: 0,
    submit() {
      this.submitted += 1;
    },
  });
}

// new FormData(form) lists the form's fields as pairs.
class FakeFormData {
  constructor(form) {
    this.fields = form.fields;
  }

  [Symbol.iterator]() {
    return this.fields[Symbol.iterator]();
  }
}

const markedForm = fakeForm(
  ["data-plain-fallback"],
  "post",
  "http://127.0.0.1/ui/watchlist/7",
  [["from", "detail"]]
);
const unmarkedForm = fakeForm(
  [],
  "post",
  "http://127.0.0.1/ui/watchlist/7",
  [["from", "detail"]]
);
// The sticky note. On this page, a GET for the open panel asks for
// this same page plus #research.
const samePageForm = fakeForm(
  ["data-plain-fallback"],
  "get",
  "http://127.0.0.1/ui/instruments/7#research",
  [["research", "open"]]
);
// The same form asking to close the panel: another URL.
const otherPageForm = fakeForm(
  ["data-plain-fallback"],
  "get",
  "http://127.0.0.1/ui/instruments/7#research",
  [["research", "closed"]]
);
const markedLink = fakeElement("A", ["data-plain-fallback", "href"], {
  href: "http://127.0.0.1/ui/companies/7/research",
});
const samePageLink = fakeElement("A", ["data-plain-fallback", "href"], {
  href: "http://127.0.0.1/ui/instruments/7?research=open#research",
});
const unmarkedLink = fakeElement("A", ["href"], {
  href: "http://127.0.0.1/ui/watchlist",
});
// Neither a form nor a link, so the marker alone does nothing.
const markedButton = fakeElement("BUTTON", ["data-plain-fallback"]);

// What one swap left inside its target. "kept" stands for an element
// that hx-preserve carried over from the previous answer.
const inside = [
  fakeElement("TEXTAREA", ["autofocus", "id"], { id: "kept" }),
  fakeElement("DIV", ["autofocus", "id", "tabindex"], { id: "focused" }),
  fakeElement("H2", ["id"], { id: "plain" }),
];
const target = fakeElement("SECTION", ["id"], {
  // Supports one attribute selector such as "[autofocus]".
  querySelectorAll(selector) {
    const match = /^\[([a-z-]+)\]$/.exec(selector);
    if (match === null) {
      throw new Error("unsupported selector: " + selector);
    }
    return inside.filter((element) => element.hasAttribute(match[1]));
  },
});

vm.runInNewContext(
  fs.readFileSync(process.argv[2], "utf8"),
  {
    document: {
      addEventListener(name, handler) {
        (handlers[name] = handlers[name] || []).push(handler);
      },
    },
    window: { location: location },
    FormData: FakeFormData,
    URL: URL,
    URLSearchParams: URLSearchParams,
  },
  { filename: process.argv[2] }
);

function fire(name, event) {
  for (const handler of handlers[name] || []) {
    handler(event);
  }
}

const elements = [
  markedForm,
  samePageForm,
  otherPageForm,
  markedLink,
  samePageLink,
  unmarkedForm,
  unmarkedLink,
  markedButton,
];
for (const name of ["htmx:responseError", "htmx:sendError"]) {
  for (const element of elements) {
    fire(name, { detail: { elt: element } });
  }
  fire(name, {});
}
// A plain POST lands on the page with #research. The page's own
// fragment does not make the sticky note's URL a different page.
location.href = "http://127.0.0.1/ui/instruments/7?research=open#research";
fire("htmx:sendError", { detail: { elt: samePageForm } });
fire("htmx:afterSettle", { target: target, detail: { elt: target } });

console.log(JSON.stringify({
  events: Object.keys(handlers).sort(),
  submitted: {
    marked: markedForm.submitted,
    samePage: samePageForm.submitted,
    otherPage: otherPageForm.submitted,
    unmarked: unmarkedForm.submitted,
  },
  assigned: assigned,
  attributes: Object.fromEntries(
    inside.map((element) => [element.id, element.getAttributeNames()])
  ),
}));
"""


def test_ui_js_repeats_marked_requests(tmp_path):
    """A failed request is repeated without HTMX; settling drops autofocus.

    ``htmx:responseError`` and ``htmx:sendError`` each arrive for
    marked POST and GET forms, marked links, an unmarked form, an
    unmarked link, a marked button, and an event without ``elt``.
    Once per event:

    - the marked POST form is posted again;
    - the GET form that asks for another URL is submitted again;
    - the marked link to another page is followed;
    - the GET form and the link whose URL is this page plus a
      ``#fragment`` load this page without the fragment, because the
      browser would only scroll to it and send no request. The
      page's own fragment does not change that;
    - nothing else happens.

    ``htmx:afterSettle`` then removes ``autofocus`` from every element
    inside the swapped target and leaves other attributes.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    harness = tmp_path / "harness.cjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    completed = subprocess.run(
        [node, str(harness), str(UI_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "events": [
            "htmx:afterSettle",
            "htmx:beforeSwap",
            "htmx:responseError",
            "htmx:sendError",
        ],
        "submitted": {
            "marked": 2,
            "samePage": 0,
            "otherPage": 2,
            "unmarked": 0,
        },
        "assigned": [_PAGE, _LINK, _PAGE, _PAGE, _LINK, _PAGE, _PAGE],
        "attributes": {
            "kept": ["id"],
            "focused": ["id", "tabindex"],
            "plain": ["id"],
        },
    }


# Fires htmx:beforeSwap. The script may only force a swap for a 500
# whose target is the research panel. Other targets and other statuses
# keep the shouldSwap value HTMX already chose.
_SWAP_HARNESS = r"""
"use strict";
const fs = require("fs");
const vm = require("vm");

const handlers = {};
vm.runInNewContext(
  fs.readFileSync(process.argv[2], "utf8"),
  {
    document: {
      addEventListener(name, handler) {
        (handlers[name] = handlers[name] || []).push(handler);
      },
    },
    window: { location: { href: "http://127.0.0.1/ui", assign() {} } },
    FormData: class {},
    URL: URL,
    URLSearchParams: URLSearchParams,
  },
  { filename: process.argv[2] }
);

function fire(event) {
  for (const handler of handlers["htmx:beforeSwap"] || []) {
    handler(event);
  }
}

const cases = [
  { name: "research500", status: 500, id: "research", shouldSwap: false },
  { name: "other500", status: 500, id: "watchlist-table", shouldSwap: false },
  { name: "research404", status: 404, id: "research", shouldSwap: false },
  { name: "research422", status: 422, id: "research", shouldSwap: true },
  { name: "research200", status: 200, id: "research", shouldSwap: true },
  { name: "noId", status: 500, id: "", shouldSwap: false },
];
const results = {};
for (const item of cases) {
  const detail = {
    xhr: { status: item.status },
    target: { id: item.id },
    shouldSwap: item.shouldSwap,
  };
  fire({ detail: detail });
  results[item.name] = detail.shouldSwap;
}
fire({});
console.log(JSON.stringify({
  listened: Object.prototype.hasOwnProperty.call(handlers, "htmx:beforeSwap"),
  results: results,
}));
"""


@pytest.mark.asyncio
async def test_create_forms_do_not_repeat_and_a_research_500_swaps(
    client, tmp_path
):
    """Create posts are not repeated. A 500 swaps into #research only.

    A 500 after the row is stored used to post the add form again,
    because it carried ``data-plain-fallback``. That second post
    stored another note or thesis and threw away the 500 panel.
    Edit and delete stay marked: repeating them does not insert a
    row. ``ui.js`` swaps a 500 into ``#research`` and leaves every
    other 500 unswapped.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}"
    headers = {"hx-request": "true"}
    pages = (
        await client.get(f"{base}/research", headers=headers),
        await client.get(f"{base}/theses/new", headers=headers),
        await client.get(f"{base}/notes/{note_id}/edit", headers=headers),
        await client.get(f"{base}/notes/{note_id}/delete", headers=headers),
        await client.get(f"{base}/theses/{thesis_id}/edit", headers=headers),
        await client.get(f"{base}/theses/{thesis_id}/delete", headers=headers),
    )
    creates, edits, deletes = set(), set(), set()
    for response in pages:
        assert response.status_code == 200
        for tag, attrs in _panel_actions(response.text):
            action = attrs.get("action", attrs.get("href", ""))
            if _is_create_post(tag, attrs):
                assert "data-plain-fallback" not in attrs, action
                creates.add(action)
            else:
                assert "data-plain-fallback" in attrs, action
                if tag == "form" and action.endswith("/edit"):
                    edits.add(action)
                if tag == "form" and action.endswith("/delete"):
                    deletes.add(action)
    assert creates == {f"{base}/notes", f"{base}/theses"}
    assert edits == {
        f"{base}/notes/{note_id}/edit",
        f"{base}/theses/{thesis_id}/edit",
    }
    assert deletes == {
        f"{base}/notes/{note_id}/delete",
        f"{base}/theses/{thesis_id}/delete",
    }

    script = UI_JS.read_text(encoding="utf-8")
    assert 'xhr.status === 500 && target.id === "research"' in script
    assert "detail.shouldSwap = true" in script

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    harness = tmp_path / "swap-harness.cjs"
    harness.write_text(_SWAP_HARNESS, encoding="utf-8")
    completed = subprocess.run(
        [node, str(harness), str(UI_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "listened": True,
        "results": {
            "research500": True,
            "other500": False,
            "research404": False,
            "research422": True,
            "research200": True,
            "noId": False,
        },
    }

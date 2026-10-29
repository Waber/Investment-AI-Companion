"""``static/ui.js`` run in node with fake browser objects.

The script has no build step and no npm packages, so node can run it
as it is. The harness below gives it a fake ``document``, a fake
``window.location``, and fake elements. It fires the HTMX events the
script listens to and prints what the script did as JSON. No browser
starts. The test is skipped when node is not installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI_JS = Path(__file__).resolve().parents[1] / "static" / "ui.js"
# The href of the marked link in the harness.
_LINK = "http://127.0.0.1/ui/companies/7/research"

# CommonJS (.cjs), so a package.json above tmp_path cannot turn it into
# an ES module. vm runs ui.js in a fresh context whose only browser
# globals are the fakes, so a call to anything else fails the run.
_HARNESS = r"""
"use strict";
const fs = require("fs");
const vm = require("vm");

const handlers = {};
const assigned = [];

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

function fakeForm(attributes) {
  return fakeElement("FORM", attributes, {
    submitted: 0,
    submit() {
      this.submitted += 1;
    },
  });
}

const markedForm = fakeForm(["data-plain-fallback"]);
const unmarkedForm = fakeForm([]);
const markedLink = fakeElement("A", ["data-plain-fallback", "href"], {
  href: "http://127.0.0.1/ui/companies/7/research",
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
    window: { location: { assign: (url) => assigned.push(url) } },
  },
  { filename: process.argv[2] }
);

function fire(name, event) {
  for (const handler of handlers[name] || []) {
    handler(event);
  }
}

const elements = [
  markedForm, markedLink, unmarkedForm, unmarkedLink, markedButton,
];
for (const name of ["htmx:responseError", "htmx:sendError"]) {
  for (const element of elements) {
    fire(name, { detail: { elt: element } });
  }
  fire(name, {});
}
fire("htmx:afterSettle", { target: target, detail: { elt: target } });

console.log(JSON.stringify({
  events: Object.keys(handlers).sort(),
  submitted: {
    marked: markedForm.submitted,
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

    ``htmx:responseError`` and ``htmx:sendError`` each arrive for a
    marked form, a marked link, an unmarked form, an unmarked link, a
    marked button, and an event without ``elt``. Only the marked form
    is posted again, and only the marked link is followed, once per
    event. ``htmx:afterSettle`` then removes ``autofocus`` from every
    element inside the swapped target and leaves other attributes.
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
        "events": ["htmx:afterSettle", "htmx:responseError", "htmx:sendError"],
        "submitted": {"marked": 2, "unmarked": 0},
        "assigned": [_LINK, _LINK],
        "attributes": {
            "kept": ["id"],
            "focused": ["id", "tabindex"],
            "plain": ["id"],
        },
    }

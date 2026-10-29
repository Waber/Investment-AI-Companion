// Two helpers for the HTMX requests on /ui pages.
//
// 1. Fallback for HTMX forms and links marked with data-plain-fallback.
//
// Of the 4xx and 5xx answers, HTMX swaps only a 422 (a validation
// error) into the page; the htmx-config meta in base.html sets this.
// Any other failed request (a company deleted in another tab, a
// server error, no network) would leave the click with no visible
// effect. Here the same request is repeated without HTMX, and the
// browser shows what the server answered: a form is posted again, a
// link is followed. form.submit() skips the submit event, so HTMX
// does not catch this second post. Only mark forms whose action is
// safe to repeat.
//
// 2. Stale autofocus.
//
// After a swap HTMX focuses the first [autofocus] element in the new
// content. It does that before htmx:afterSettle, so removing the
// attribute there does not undo the focus. An element that
// hx-preserve keeps is not rendered again: without this cleanup it
// would carry its old autofocus into the next swap and could take the
// focus meant for another element.
(function () {
  function isMarked(element, tagName) {
    return element && element.tagName === tagName && element.hasAttribute("data-plain-fallback");
  }

  function repeatWithoutHtmx(event) {
    var element = event.detail && event.detail.elt;
    if (isMarked(element, "FORM")) {
      element.submit();
    } else if (isMarked(element, "A")) {
      window.location.assign(element.href);
    }
  }

  function clearAutofocus(event) {
    var focused = event.target.querySelectorAll("[autofocus]");
    for (var i = 0; i < focused.length; i++) {
      focused[i].removeAttribute("autofocus");
    }
  }

  document.addEventListener("htmx:responseError", repeatWithoutHtmx);
  document.addEventListener("htmx:sendError", repeatWithoutHtmx);
  document.addEventListener("htmx:afterSettle", clearAutofocus);
})();

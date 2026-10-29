// Two helpers for the HTMX requests on /ui pages.
//
// 1. Fallback for HTMX forms and links marked with data-plain-fallback.
//
// Of the 4xx and 5xx answers, HTMX swaps only a 422 (a validation
// error) into the page; the htmx-config meta in base.html sets this.
// Any other failed request (a company deleted in another tab, a
// server error, no network) would leave the click with no visible
// effect. Here the same request is repeated without HTMX, and the
// browser shows what the server answered: a form is submitted again,
// a link is followed. form.submit() skips the submit event, so HTMX
// does not catch this second request. Only mark forms whose action
// is safe to repeat.
//
// A GET of the page's own URL plus a #fragment sends no request: the
// browser only scrolls to the fragment. The sticky note's form does
// that once the page URL already has ?research=open (after PL/EN, or
// after a plain POST lands there). Such a GET form or link loads the
// URL without its fragment instead. A POST always sends a request.
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

  function withoutFragment(url) {
    var hash = url.indexOf("#");
    return hash === -1 ? url : url.slice(0, hash);
  }

  // True when going to url would only scroll this page (see above).
  function onlyScrolls(url) {
    return url.indexOf("#") !== -1 &&
      withoutFragment(url) === withoutFragment(window.location.href);
  }

  // Where the browser sends a GET form: the action URL with the form
  // data as its query string, which replaces any query in the action.
  function getFormUrl(form) {
    var url = new URL(form.action);
    url.search = new URLSearchParams(new FormData(form)).toString();
    return url.href;
  }

  function repeatWithoutHtmx(event) {
    var element = event.detail && event.detail.elt;
    var url;
    if (isMarked(element, "FORM")) {
      url = element.method === "get" ? getFormUrl(element) : null;
      if (url !== null && onlyScrolls(url)) {
        window.location.assign(withoutFragment(url));
      } else {
        element.submit();
      }
    } else if (isMarked(element, "A")) {
      url = element.href;
      window.location.assign(onlyScrolls(url) ? withoutFragment(url) : url);
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

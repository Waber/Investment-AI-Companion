// Fallback for HTMX forms marked with data-plain-fallback.
//
// HTMX does not swap a 4xx or 5xx answer into the page, so a failed
// request (a company deleted in another tab, a server error, no
// network) would leave the click with no visible effect. Here the
// same form is posted again without HTMX, and the browser shows what
// the server answered. form.submit() skips the submit event, so HTMX
// does not catch this second post. Only mark forms whose action is
// safe to repeat.
(function () {
  function postWithoutHtmx(event) {
    var form = event.detail && event.detail.elt;
    if (form && form.tagName === "FORM" && form.hasAttribute("data-plain-fallback")) {
      form.submit();
    }
  }

  document.addEventListener("htmx:responseError", postWithoutHtmx);
  document.addEventListener("htmx:sendError", postWithoutHtmx);
})();

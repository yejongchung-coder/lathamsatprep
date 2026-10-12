/* ABLE Enrichment lightweight analytics.
   No cookies, no fingerprinting, no personal data.
   Counts pageviews per page so we can report visits and conversion. */
(function () {
  try {
    if (navigator.doNotTrack === "1" || window.doNotTrack === "1") return;
    var payload = JSON.stringify({
      path: location.pathname,
      referrer: document.referrer || ""
    });
    var url = "/api/track";
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
    } else if (window.fetch) {
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true
      });
    }
  } catch (e) {
    /* analytics must never break the page */
  }
})();

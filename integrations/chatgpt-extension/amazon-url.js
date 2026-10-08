/* Resolve Amazon advertising links without fetching arbitrary redirects. */
(() => {
  "use strict";
  const hosts = new Set(["amazon.it", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es"]);
  function resolveAmazonProductURL(value) {
    if (typeof value !== "string" || value.length > 4096 || /[\x00-\x1f\\]/.test(value)) return null;
    let current = value, marketplace;
    for (let depth = 0; depth < 3; depth += 1) {
      try {
        const url = new URL(current), host = url.hostname.replace(/^www\./, "");
        if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443") || !hosts.has(host) || (marketplace && marketplace !== host)) return null;
        marketplace = host;
        if (/\/(?:dp|gp\/product|gp\/aw\/d)\/[A-Z0-9]{10}(?:[/.]|$)/i.test(url.pathname)) return url.href;
        if (url.pathname !== "/sspa/click" && !url.pathname.startsWith("/gp/slredirect/")) return null;
        const targets = url.searchParams.getAll("url");
        if (targets.length !== 1 || !targets[0] || targets[0].length > 4096 || /[\x00-\x1f\\]/.test(targets[0])) return null;
        current = new URL(targets[0], url).href;
      } catch { return null; }
    }
    return null;
  }
  const exported = {resolveAmazonProductURL};
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  globalThis.FactTTLAmazonURL = exported;
})();

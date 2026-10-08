/* Read primary Amazon offer fields in the browser. No account/address data. */
(() => {
  "use strict";
  const hosts = new Set(["amazon.it", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es"]);
  function productIdentity(value) {
    try {
      const url = new URL(value);
      const host = url.hostname.replace(/^www\./, "");
      const asin = url.pathname.match(/\/(?:dp|gp\/product|gp\/aw\/d)\/([A-Z0-9]{10})(?:[/.]|$)/i)?.[1]?.toUpperCase();
      return url.protocol === "https:" && !url.username && !url.password && (!url.port || url.port === "443") && hosts.has(host) && asin ? {host, asin} : null;
    } catch { return null; }
  }
  function money(value) {
    const text = String(value || "").replace(/\s/g, "");
    const currencies = [[/€|EUR/, "EUR"], [/£|GBP/, "GBP"], [/\$|USD/, "USD"]].filter(([pattern]) => pattern.test(text)).map(([, currency]) => currency);
    const currency = currencies.length === 1 ? currencies[0] : null;
    const amounts = text.match(/\d[\d.,]*/g) || [];
    const number = amounts.length === 1 ? amounts[0] : null;
    if (!currency || !number) return null;
    const decimal = /[.,]\d{2}$/.test(number);
    const integer = decimal ? number.slice(0, -3) : number;
    if (!/^\d+$/.test(integer) && !/^\d{1,3}([.,])\d{3}(?:\1\d{3})*$/.test(integer)) return null;
    // Never reinterpret an ambiguous single decimal digit as a tenfold price.
    const normalized = integer.replace(/[.,]/g, "") + (decimal ? "." + number.slice(-2) : "");
    return /^\d{1,7}(?:\.\d{2})?$/.test(normalized) && Number(normalized) > 0 ? {amount: normalized, currency} : null;
  }
  function readProduct(doc, href, now = new Date().toISOString()) {
    const identity = productIdentity(href);
    if (!identity) return {status: "WRONG_PRODUCT"};
    const base = {url: href, asin: identity.asin, observed_at: now, source: "browser_rendered_amazon", scope: "browser_current_offer"};
    const page = (doc.body?.innerText || "").slice(0, 20000);
    if (/enter the characters|inserisci i caratteri|validateCaptcha|robot check/i.test(page) || doc.querySelector('form[action*="validateCaptcha"], form[action*="signin"]')) return {...base, status: "BLOCKED"};
    const pageAsin = doc.querySelector('input#ASIN')?.value?.toUpperCase();
    const title = (doc.querySelector("#productTitle")?.textContent || "").trim().slice(0, 180);
    if (!title || pageAsin !== identity.asin) return {...base, status: "WRONG_PRODUCT"};
    const visible = node => {
      if (!node || node.closest('[hidden], [aria-hidden="true"], .aok-hidden')) return false;
      const view = doc.defaultView;
      for (let parent = node; parent && parent !== doc.body; parent = parent.parentElement) {
        const style = view?.getComputedStyle?.(parent);
        if (style?.display === "none" || style?.visibility === "hidden") return false;
      }
      return true;
    };
    const primary = ["#corePriceDisplay_desktop_feature_div", "#corePrice_desktop", "#apex_desktop", "#corePriceDisplay_mobile_feature_div", "#corePrice_mobile_feature_div", "#buybox"];
    const prices = [];
    const references = [];
    for (const selector of primary) {
      const root = doc.querySelector(selector);
      if (!visible(root)) continue;
      for (const node of root.querySelectorAll(".a-price .a-offscreen")) {
        if (!visible(node)) continue;
        const price = money(node.textContent);
        if (!price) continue;
        if (node.closest(".basisPrice, .apex-basisprice-value")) references.push(price);
        else if (!node.closest(".a-text-price")) prices.push(price);
      }
    }
    const distinct = entries => [...new Map(entries.map(p => [p.amount + p.currency, p])).values()];
    const values = distinct(prices), lists = distinct(references);
    const availability = doc.querySelector("#availability");
    const stockText = visible(availability) ? (availability.textContent || "").trim().slice(0, 300) : "";
    const negative = /non disponibile|attualmente non|esaurit[oa]|currently unavailable|out of stock|nicht verfügbar|derzeit nicht|rupture de stock|indisponible|no disponible|sin stock/i.test(stockText);
    const positive = /disponibil|in stock|auf lager|en stock|en existencia/i.test(stockText);
    const buy = ["#add-to-cart-button", "#buy-now-button", "#add-to-cart-button-ubb"].some(selector => {const n = doc.querySelector(selector); return visible(n) && !n.disabled;});
    const stock = negative ? "unavailable" : positive && buy ? "available" : "unknown";
    return {...base, status: "OBSERVED", title, availability: stock, availability_text: stockText, price: values.length === 1 ? values[0].amount : null, currency: values.length === 1 ? values[0].currency : null, list_price: lists.length === 1 && values.length === 1 && lists[0].currency === values[0].currency ? lists[0].amount : null};
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {productIdentity, money, readProduct};
  if (typeof document === "undefined" || typeof location === "undefined") return;
  const api = typeof browser !== "undefined" ? browser : chrome;
  api.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id === api.runtime.id && message?.type === "READ_PRODUCT_OFFER") respond(readProduct(document, location.href));
    return false;
  });
})();

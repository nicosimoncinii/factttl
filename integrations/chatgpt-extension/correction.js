/* Pure collection of scoped findings; no composer access or chat messages. */
(() => {
  "use strict";
  const safeURL = value => {
    try { const u = new URL(value); return u.protocol === "https:" && !u.username && !u.password && (!u.port || u.port === "443") ? u.href : null; } catch { return null; }
  };
  function collectCorrections(entries, now = Date.now()) {
    const findings = [], seen = new Set();
    for (const entry of entries || []) {
      const searchUI = typeof FactTTLItemUI !== "undefined" && FactTTLItemUI.searchDestination ? FactTTLItemUI : typeof module !== "undefined" && module.exports ? require("./item-ui.js") : null;
      if (safeURL(entry.url) && searchUI?.searchDestination(entry.url)) {
        const key = `${entry.url}:product_selection`;
        if (!seen.has(key)) {seen.add(key); findings.push({url: entry.url, property: "product_selection", original: String(entry.text || "").slice(0, 400), observed: "Link di ricerca: nessun prodotto o prezzo selezionato. La disponibilità del prodotto non è determinata.", scope: "link_structure"});}
        // The URL itself proves this is a search placeholder. Do not depend on
        // a network response, or accept offer/stock claims about a search page.
        continue;
      }
      if (!entry.response?.ok) continue;
      for (const item of entry.response.result?.checks || []) {
        const c = item.result || item, url = safeURL(c.url);
        if (!url || c.outcome !== "CONTRADICTED" || !(Date.parse(c.observed_at) <= now + 5000 && Date.parse(c.observed_at) >= now - 300000)) continue;
        const evidence = c.evidence || [];
        const groundedNews = c.kind === "news" && evidence.some(e => e.provider === "ai_assessed_live_source" && e.assessment === "CONTRADICTED" && (e.citations || []).some(x => x.quote && safeURL(x.source_url || url)));
        const publicProperty = evidence.some(e => e.provider === "live_public_web");
        const typed = c.kind === "product_price" ? /^\d{1,7}(?:[.,]\d{1,2})? (?:EUR|USD|GBP)$/.test(c.observed_value || "") : c.kind === "product_availability" || c.kind === "link_available" ? ["available", "unavailable"].includes(c.observed_value) : c.kind === "product_discount" ? /^(?:true|false|discounted|not_discounted|\d{1,3}(?:[.,]\d{1,2})?%?)$/.test(c.observed_value || "") : false;
        if (!groundedNews && !(publicProperty && typed)) continue;
        const key = `${url}:${c.kind}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const finding = {url, property: c.kind, title: String(evidence.map(e => e.product_title || e.product_name).find(Boolean) || "").slice(0, 180), original: String(c.expected_value || c.claim_text || entry.text || "").slice(0, 400), observed: groundedNews ? "In contrasto con la fonte consultata" : c.observed_value, observed_at: c.observed_at, scope: groundedNews ? "source_relative_assessment" : evidence.some(e => e.scope === "browser_current_offer") ? "browser_current_offer" : "public_source_property"};
        if (groundedNews) finding.evidence = evidence.flatMap(e => e.citations || []).filter(x => safeURL(x.source_url || url)).slice(0, 2).map(x => ({url: safeURL(x.source_url || url), quote: String(x.quote).slice(0, 350)}));
        findings.push(finding);
      }
      const productURL = typeof FactTTLAmazonURL !== "undefined" && FactTTLAmazonURL.resolveAmazonProductURL(entry.url);
      if (productURL) {
        // An estimate is not a false assertion, but a cart still needs updating
        // when the live price changes its budget. Keep that distinction visible.
        const estimateText = String(entry.text || "");
        const estimates = [...estimateText.matchAll(/(?<![\d.,])(\d{1,6}(?:[.,]\d{1,2})?)\s*(?:€|EUR\b)(?!\d|[.,]\d)/g)].filter(match => !/(?:^|\s)\d+\s+$/.test(estimateText.slice(0, match.index)));
        const price = (entry.response.result?.checks || []).map(c => c.result || c).find(c => safeURL(c.url) === safeURL(entry.url) && c.kind === "product_price" && c.outcome === "SUPPORTED" && !c.expected_value && /^\d+(?:[.,]\d{1,2})? EUR$/.test(c.observed_value || "") && Date.parse(c.observed_at) <= now + 5000 && Date.parse(c.observed_at) >= now - 300000 && (c.evidence || []).some(e => e.provider === "live_public_web"));
        if (price && estimates.length === 1 && /indicativ|orientativ|previsto|estimated|estimate|circa|about|[~≈]/i.test(entry.text || "") && Number(estimates[0][1].replace(",", ".")) !== Number(price.observed_value.split(" ")[0].replace(",", "."))) {
          const key = `${entry.url}:product_estimate_update`;
          if (!seen.has(key)) {seen.add(key); findings.push({url: entry.url, property: "product_estimate_update", original: `${estimates[0][1]} EUR (stima)`, observed: price.observed_value, observed_at: price.observed_at, scope: "estimate_update_not_false_claim"});}
        }
        const missing = (entry.response.result?.checks || []).map(c => c.result || c).filter(c => safeURL(c.url) === safeURL(entry.url) && Date.parse(c.observed_at) <= now + 5000 && Date.parse(c.observed_at) >= now - 300000 && ["product_price", "product_availability"].includes(c.kind) && c.outcome !== "SUPPORTED" && c.outcome !== "CONTRADICTED");
        const key = `${entry.url}:product_evidence_missing`;
        if (missing.length && !seen.has(key)) {seen.add(key); findings.push({url: entry.url, property: "product_evidence_missing", original: String(entry.text || "").slice(0, 400), observed: `Prove mancanti per ${missing.map(c => c.kind === "product_price" ? "prezzo" : "disponibilità del prodotto").join(" e ")}. Non è una prova che il prodotto sia esaurito o che il dato sia falso.`, scope: "verification_incomplete"});}
      }
    }
    return findings.slice(0, 10);
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {collectCorrections};
})();

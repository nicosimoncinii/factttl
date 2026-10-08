const assert = require("node:assert/strict");
const {test} = require("node:test");
const {summarize, sameURL} = require("../integrations/chatgpt-extension/item-ui.js");

test("a supported link alone gets an accessibility result, never a fact-green badge", () => {
  const summary = summarize({
    status: "SUPPORTED",
    checks: [{result: {
      url: "https://shop.example/item",
      kind: "link_available",
      outcome: "SUPPORTED",
    }}],
  }, "https://shop.example/item");

  assert.equal(summary.status, "ACCESSIBLE");
  assert.equal(summary.label, "Link accessibile");
});

test("a news link remains unverified even when the source page is accessible", () => {
  const summary = summarize({
    status: "SUPPORTED",
    checks: [
      {result: {url: "https://news.example/story", kind: "link_available", outcome: "SUPPORTED"}},
      {result: {url: "https://news.example/story", kind: "news", outcome: "SUPPORTED", published_at: "2026-10-06T12:00:00Z"}},
    ],
  }, "https://news.example/story");

  assert.notEqual(summary.status, "SUPPORTED");
  assert.equal(summary.label, "Notizia non verificata");
});

test("a news assessment with a citation anchored to its fetched source can say consistent", () => {
  const sourceUrl = "https://news.example/story";
  const summary = summarize({
    status: "SUPPORTED",
    checks: [{result: {
      url: sourceUrl,
      kind: "news",
      outcome: "SUPPORTED",
      evidence: [{
        provider: "ai_assessed_live_source",
        scope: "current_source_consistency",
        assessment: "SUPPORTED",
        citations: [{source_id: "source-1", quote: "The cited passage from the live source is long enough."}],
      }],
    }}],
  }, sourceUrl);

  assert.equal(summary.status, "SUPPORTED");
  assert.equal(summary.label, "Coerente con la fonte");
});

test("an AI news assessment without source citations stays unverified", () => {
  const sourceUrl = "https://news.example/story";
  const summary = summarize({
    status: "SUPPORTED",
    checks: [{result: {
      url: sourceUrl,
      kind: "news",
      outcome: "SUPPORTED",
      evidence: [{
        provider: "ai_assessed_live_source",
        scope: "current_source_consistency",
        assessment: "SUPPORTED",
        citations: [],
      }],
    }}],
  }, sourceUrl);

  assert.notEqual(summary.status, "SUPPORTED");
  assert.equal(summary.label, "Notizia non verificata");
});

test("a prior correction blocks a green news badge until the caller reviews it", () => {
  const sourceUrl = "https://news.example/story";
  const summary = summarize({
    status: "SUPPORTED",
    prior_corrections: [{url: sourceUrl, claim_text: "A prior disputed assertion."}],
    checks: [{result: {
      url: sourceUrl,
      kind: "news",
      outcome: "SUPPORTED",
      evidence: [{
        provider: "ai_assessed_live_source",
        scope: "current_source_consistency",
        assessment: "SUPPORTED",
        citations: [{source_id: "source-1", quote: "The cited passage from the live source is long enough."}],
      }],
    }}],
  }, sourceUrl);

  assert.notEqual(summary.status, "SUPPORTED");
});

test("URL-specific evidence keeps products on distinct source paths separate", () => {
  const firstProduct = "https://shop.example/dp/AAAA111111";
  const secondProduct = "https://shop.example/dp/BBBB222222";
  const result = {
    status: "PARTIAL",
    checks: [
      {result: {url: firstProduct, kind: "product_price", outcome: "CONTRADICTED", expected_value: "9 EUR", observed_value: "12 EUR"}},
      {result: {url: secondProduct, kind: "product_price", outcome: "SUPPORTED", expected_value: "18 EUR", observed_value: "18 EUR"}},
    ],
  };

  assert.equal(sameURL(firstProduct, secondProduct), false);
  assert.equal(summarize(result, firstProduct).status, "CONTRADICTED");
  assert.equal(summarize(result, secondProduct).status, "SUPPORTED");
});

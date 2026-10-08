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

test("Amazon search link clearly reports that no specific offer has been selected", () => {
  const url = "https://www.amazon.it/s?k=esp32";
  const summary = summarize({checks: [{result: {url, kind: "link_available", outcome: "SUPPORTED"}}]}, url);
  assert.equal(summary.status, "SEARCH");
  assert.equal(summary.label, "Ricerca Amazon: nessuna offerta scelta");
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

test("a supported news excerpt remains amber and exposes its limited scope", () => {
  for (const fields of [{scope: "excerpt_consistency"}, {scope: "current_source_consistency", source_analysis_truncated: true}]) {
    const summary = summarize({checks: [{result: {
      url: "https://news.example/story", kind: "news", outcome: "SUPPORTED",
      evidence: [{provider: "ai_assessed_live_source", assessment: "SUPPORTED", citations: [{quote: "Quoted live source evidence."}], ...fields}],
    }}]});
    assert.equal(summary.status, "PARTIAL");
    assert.equal(summary.label, "Coerente con estratto");
  }
});

test("a contradiction inferred from a news excerpt names the limited scope", () => {
  const summary = summarize({checks: [{result: {
    url: "https://news.example/story", kind: "news", outcome: "CONTRADICTED",
    evidence: [{provider: "ai_assessed_live_source", scope: "excerpt_consistency", assessment: "CONTRADICTED", citations: [{quote: "Quoted live source evidence."}]}],
  }}]});
  assert.equal(summary.status, "CONTRADICTED");
  assert.equal(summary.label, "In contrasto con estratto");
});

test("conflicting provided sources never produce a decisive news badge", () => {
  const summary = summarize({checks: [{result: {
    url: "https://news.example/story", kind: "news", outcome: "INCONCLUSIVE",
    evidence: [
      {provider: "ai_assessed_live_source", scope: "current_source_consistency", assessment: "SUPPORTED", citations: [{quote: "A supported quotation from one source."}]},
      {provider: "provided_source_comparison", conflicting_sources: true, source_count: 2, independence_established: false},
    ],
  }}]});
  assert.equal(summary.status, "INCONCLUSIVE");
  assert.equal(summary.label, "Fonti in contrasto");
});

test("unlinked group can use one quoted source without verifying unread members", () => {
  const first = "https://news.example/known", second = "https://other.example/unread";
  const evidence = [
    {provider: "ai_assessed_live_source", scope: "current_source_consistency", assessment: "SUPPORTED", source_analysis_truncated: true, citations: [{quote: "A validated source quotation supporting the claim.", source_url: first}]},
    {provider: "provided_source_comparison", assessment: "SUPPORTED", assessment_basis_urls: [first], inconclusive_source_count: 1, omitted_source_count: 0},
  ];
  const result = {checks: [
    {result: {url: first, kind: "news", outcome: "SUPPORTED", evidence}},
    {result: {url: second, kind: "news", outcome: "INCONCLUSIVE", evidence}},
  ]};
  assert.equal(summarize(result).label, "Coerente con estratto");
  assert.equal(summarize(result).status, "PARTIAL");
  assert.equal(summarize(result, second).status, "INCONCLUSIVE");
  assert.equal(summarize(result, second).label, "Notizia non verificata");
  assert.equal(summarize({checks: [result.checks[1]]}).status, "INCONCLUSIVE");
});

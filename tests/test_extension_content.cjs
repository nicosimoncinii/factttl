const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const {chatKey, destinationKey, itemTargets, normalizeChecks, serializeMessage, sourceFor, publicFactCandidate} = require("../integrations/chatgpt-extension/content.js");
const manifest = require("../integrations/chatgpt-extension/manifest.json");

function text(value) {
  return {nodeType: 3, textContent: value};
}

function element(tagName, children = [], attrs = {}) {
  const node = {
    nodeType: 1,
    tagName: tagName.toUpperCase(),
    childNodes: children,
    textContent: children.map(child => child.textContent || "").join(""),
    getAttribute(name) { return attrs[name] ?? null; },
    matches(selector) {
      if (selector === '[hidden], [aria-hidden="true"], script, style') {
        return Boolean(attrs.hidden) || attrs["aria-hidden"] === "true" ||
          ["SCRIPT", "STYLE"].includes(this.tagName);
      }
      if (selector === "[hidden]") return Boolean(attrs.hidden);
      if (selector === '[aria-hidden="true"]') return attrs["aria-hidden"] === "true";
      return ["script", "style"].includes(selector) && this.tagName.toLowerCase() === selector;
    },
    closest(selector) { return selector === ".factttl-ui" && attrs.factttlUi ? this : null; },
  };
  for (const child of children) child.parentElement = node;
  return node;
}

test("chatKey accepts conversation routes for ChatGPT, Claude, and Gemini", () => {
  assert.equal(chatKey("/c/abc-123"), "chatgpt:abc-123");
  assert.equal(chatKey("/"), null);
  assert.equal(chatKey("/g/gpt-id"), null);
  assert.equal(chatKey("/chat/uuid-1", "claude.ai"), "claude:uuid-1");
  assert.equal(chatKey("/new", "claude.ai"), null);
  assert.equal(chatKey("/app/xyz", "gemini.google.com"), "gemini:xyz");
  assert.equal(chatKey("/u/0/app/xyz", "gemini.google.com"), "gemini:xyz");
});

test("extension key matches the origin configured by the local bridge", () => {
  const digest = crypto.createHash("sha256").update(Buffer.from(manifest.key, "base64")).digest();
  const extensionId = [...digest.subarray(0, 16)]
    .map(byte => byte.toString(16).padStart(2, "0"))
    .join("")
    .replace(/[0-9a-f]/g, digit => String.fromCharCode(97 + Number.parseInt(digit, 16)));
  const bridge = fs.readFileSync(path.join(__dirname, "../src/factttl/browser_bridge.py"), "utf8");
  assert.ok(bridge.includes(`chrome-extension://${extensionId}`));
});

test("repeated citations within one assertion block create a single primary target", () => {
  const makeAnchor = href => ({
    href,
    tagName: "A",
    closest: () => null,
  });
  const anchors = [
    makeAnchor("https://shop.example/item#details"),
    makeAnchor("https://shop.example/item#reviews"),
    makeAnchor("https://shop.example/other-item"),
  ];
  const citationParagraph = {
    tagName: "P",
    textContent: "Source citation repeated in a long paragraph to exercise the fallback target behavior.",
    closest: () => null,
    contains: node => node === anchors[1],
    querySelector: () => null,
  };
  const root = {
    querySelectorAll(selector) {
      if (selector === "a[href]") return anchors;
      if (selector === "p, li") return [citationParagraph];
      return [];
    },
  };

  assert.equal(destinationKey(anchors[0].href), destinationKey(anchors[1].href));
  assert.deepEqual(itemTargets(root), [anchors[0], anchors[2]]);
});

test("different paragraphs keep separate assertions for the same source", () => {
  const paragraphs = [
    {tagName: "P", textContent: "Il prodotto costa attualmente 10 EUR e questa è la prima affermazione."},
    {tagName: "P", textContent: "Il prodotto costa attualmente 20 EUR e questa è una seconda affermazione."},
  ];
  const anchors = paragraphs.map(paragraph => ({
    href: "https://shop.example/item", tagName: "A", parentElement: paragraph,
    closest: selector => selector === "p, tr" ? paragraph : null,
  }));
  paragraphs.forEach((paragraph, index) => {
    paragraph.closest = () => null;
    paragraph.contains = node => node === anchors[index];
    paragraph.querySelector = () => null;
  });
  const root = {querySelectorAll: selector => selector === "a[href]" ? anchors : paragraphs};
  assert.deepEqual(itemTargets(root), anchors);
});

test("product list item citations share scope across nested paragraphs", () => {
  const item = {tagName: "LI", textContent: "Prodotto con descrizione e fonti ripetute per il controllo della disponibilità.", closest: () => null, querySelector: () => ({tagName: "P"})};
  const anchors = ["https://www.amazon.it/dp/B0ABC12345", "https://amazon.it/gp/product/B0ABC12345?ref_=citation"].map(href => ({
    href, tagName: "A", closest: selector => selector === "li" ? item : null,
  }));
  item.contains = node => anchors.includes(node);
  const root = {querySelectorAll: selector => selector === "a[href]" ? anchors : [item]};
  assert.deepEqual(itemTargets(root), [anchors[0]]);
});

test("Amazon product URL variants deduplicate by marketplace and ASIN", () => {
  const first = destinationKey("https://www.amazon.com/dp/B0ABC12345?tag=one#reviews");
  const tracked = destinationKey("https://amazon.com/gp/product/b0abc12345?tag=one&ref_=abc");
  const otherProduct = destinationKey("https://www.amazon.com/gp/aw/d/B0XYZ98765?tag=one");
  const otherMarketplace = destinationKey("https://www.amazon.co.uk/dp/B0ABC12345?tag=one");

  assert.equal(first, "https://amazon.com/asin/B0ABC12345");
  assert.equal(tracked, first);
  assert.notEqual(otherProduct, first);
  assert.notEqual(otherMarketplace, first);
  assert.notEqual(destinationKey("https://amazon.com/dp/B0ABC12345?psc=1"), first);
  assert.notEqual(destinationKey("https://amazon.com/dp/B0ABC12345?seller=A"), destinationKey("https://amazon.com/dp/B0ABC12345?seller=B"));
});

test("same ASIN with different sellers retains separate offer buttons in one block", () => {
  const item = {tagName: "LI", textContent: "Due venditori propongono lo stesso prodotto: ogni offerta va controllata separatamente.", closest: () => null, querySelector: () => null};
  const anchors = ["https://amazon.it/dp/B0ABC12345?seller=A", "https://amazon.it/gp/product/B0ABC12345?seller=B"].map(href => ({
    href, tagName: "A", closest: selector => selector === "li" ? item : null,
  }));
  item.contains = node => anchors.includes(node);
  const root = {querySelectorAll: selector => selector === "a[href]" ? anchors : [item]};
  assert.deepEqual(itemTargets(root), anchors);
});

test("normalizeChecks exposes nested price evidence to cards and correction drafts", () => {
  const source = {
    result: {
      url: "https://shop.example/product",
      kind: "product_price",
      outcome: "CONTRADICTED",
      expected_value: "9.99 EUR",
      observed_value: "10.99 EUR",
      rationale: "La pagina riporta il prezzo corrente di 10.99 EUR.",
    },
    flags: {usable_as_current_fact: false},
    assertion_scope: "product_price",
    claim_id: "claim-123",
  };
  const [normalized] = normalizeChecks([source]);

  assert.equal(normalized, source.result);
  assert.equal(normalized.outcome, "CONTRADICTED");
  assert.equal(normalized.expected_value, "9.99 EUR");
  assert.equal(normalized.observed_value, "10.99 EUR");
  assert.equal(normalized.url, "https://shop.example/product");
  assert.equal(normalized.rationale, "La pagina riporta il prezzo corrente di 10.99 EUR.");
});

test("serializeMessage keeps text and its HTTPS source URL together", () => {
  const root = element("article", [
    element("p", [text("The current version is "), element("a", [text("5.0")], {href: "https://example.org/release"}), text(".")]),
    element("div", [element("a", [text("unsafe")], {href: "javascript:alert(1)"})]),
  ]);

  assert.deepEqual(serializeMessage(root), {
    text: "The current version is [5.0](https://example.org/release).\n\nunsafe",
    links: ["https://example.org/release"],
  });
});

test("serializeMessage omits hidden content, scripts, and extension UI", () => {
  const root = element("div", [
    element("p", [text("Visible claim")]),
    element("p", [text("hidden claim")], {hidden: true}),
    element("script", [text("injected code")]),
    element("div", [text("badge")], {factttlUi: true}),
  ]);

  assert.equal(serializeMessage(root).text, "Visible claim");
});

test("serializeMessage strips credentials and excludes non-HTTPS source links", () => {
  const root = element("p", [
    element("a", [text("private")], {href: "https://user:secret@example.org/page"}),
    text(" "),
    element("a", [text("plain http")], {href: "http://example.org/page"}),
  ]);

  const serialized = serializeMessage(root);
  assert.equal(serialized.links.length, 0);
  assert.equal(serialized.text, "private plain http");
  assert.doesNotMatch(serialized.text, /secret|https?:\/\//);
});

test("table offer serializes name price and link together despite paragraph-wrapped cells", () => {
  const href = "https://www.amazon.it/dp/B0DKF9NCN1";
  const anchor = element("a", [text("Acquista"), element("svg", [text("ICON NOISE")])], {href});
  const linkParagraph = element("p", [anchor]);
  const row = element("tr", [element("td", [element("p", [text("ESP32 DevKit")])]), element("td", [element("p", [text("9,99 EUR")])]), element("td", [linkParagraph])]);
  anchor.closest = selector => selector === "tr" ? row : selector === "p, tr" ? linkParagraph : null;
  assert.equal(sourceFor(anchor), row);
  const payload = serializeMessage(row);
  assert.equal(payload.text, `ESP32 DevKit 9,99 EUR [Acquista](${href})`);
  assert.equal(payload.text.includes("\n"), false);
  assert.deepEqual(payload.links, [href]);
});

test("advice disclaimers and opinions do not receive generic unknown badges", () => {
  for (const value of ["Se vuoi spendere meno, controlla il prezzo prima di acquistare il carrello.", "Ti consiglio un alimentatore adatto al progetto e qualche cavo jumper.", "Secondo me questo kit è il migliore per cominciare con Arduino.", "Prezzi indicativi: la disponibilità può cambiare in qualsiasi momento."]) assert.equal(publicFactCandidate(value), false);
  assert.equal(publicFactCandidate("NASA ha annunciato il lancio della nuova missione Artemis."), true);
  assert.equal(publicFactCandidate("In Toscana il nuovo decreto rende obbligatorio questo requisito."), true);
});

test("mixed product references preserve host shortcuts locally without fetching them through the public bridge", () => {
  const shortcut = "https://chatgpt.com/?hints=search&q=Syma+S107G";
  const merchant = "https://www.amazon.it/dp/B012345678";
  const row = element("p", [text("Syma S107G 41,99 EUR "), element("a", [text("Apri prodotto")], {href: shortcut}), text(" "), element("a", [text("Amazon")], {href: merchant})]);
  assert.deepEqual(serializeMessage(row).links, [shortcut, merchant]);
  const publicPayload = serializeMessage(row, {includeHostSearch: false});
  assert.deepEqual(publicPayload.links, [merchant]);
  assert.doesNotMatch(publicPayload.text, /https:\/\/chatgpt\.com/);
  assert.match(publicPayload.text, /Syma S107G 41,99 EUR Apri prodotto/);
});

test("production scanner settles host product-search shortcuts locally without a bridge request or composer action", () => {
  const vm = require("node:vm");
  const source = fs.readFileSync(require.resolve("../integrations/chatgpt-extension/content.js"), "utf8");
  const fn = source.slice(source.indexOf("  function scan()"), source.indexOf("  async function pump()"));
  const target = {tagName: "A", href: "https://chatgpt.com/?hints=search&q=Syma+S107G", isConnected: true};
  const payload = {text: "Syma S107G 41,99 EUR", links: [target.href]};
  const state = {lastText: JSON.stringify(payload), signature: "", changedAt: Date.now() - 2000, pending: false, finishedAt: 0, box: {remove() {}}};
  const results = [];
  const context = vm.createContext({enabled: true, currentChat: "chatgpt:a", epoch: 1, states: new Map([[target, state]]), queue: [],
    Date, JSON, Set, Map, MESSAGE_SELECTOR: "assistant", document: {querySelectorAll: () => [{}]}, itemTargets: () => [target], sourceFor: () => target,
    serializeMessage: () => payload, hostSearchURL: require("../integrations/chatgpt-extension/content.js").hostSearchURL,
    isStreaming: () => false, showResult: (_state, result) => results.push(result), pump: () => {}});
  vm.runInContext(fn + "\nscan();", context);
  assert.equal(context.queue.length, 0);
  assert.equal(results.length, 1);
  assert.equal(results[0].result.reference.product_selected, false);
  assert.equal(results[0].result.reference.basis, "url_structure");
  assert.equal(state.signature, JSON.stringify(payload));
  assert.ok(state.finishedAt > 0);
});

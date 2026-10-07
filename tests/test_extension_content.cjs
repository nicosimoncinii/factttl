const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const {chatKey, destinationKey, itemTargets, normalizeChecks, serializeMessage} = require("../integrations/chatgpt-extension/content.js");
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

test("repeated citations to one destination create a single primary target", () => {
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

test("Amazon product URL variants deduplicate by marketplace and ASIN", () => {
  const first = destinationKey("https://www.amazon.com/dp/B0ABC12345?tag=one#reviews");
  const tracked = destinationKey("https://amazon.com/gp/product/b0abc12345?psc=1&ref_=abc");
  const otherProduct = destinationKey("https://www.amazon.com/gp/aw/d/B0XYZ98765?tag=one");
  const otherMarketplace = destinationKey("https://www.amazon.co.uk/dp/B0ABC12345?tag=one");

  assert.equal(first, "https://amazon.com/asin/B0ABC12345");
  assert.equal(tracked, first);
  assert.notEqual(otherProduct, first);
  assert.notEqual(otherMarketplace, first);
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

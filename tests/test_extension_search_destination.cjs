"use strict";
const assert = require("node:assert/strict");
const {test} = require("node:test");
const {readFileSync} = require("node:fs");
const {webcrypto} = require("node:crypto");
const vm = require("node:vm");
const content = require("../integrations/chatgpt-extension/content.js");
const {summarize, searchDestination} = require("../integrations/chatgpt-extension/item-ui.js");
global.FactTTLItemUI = {summarize, searchDestination};
const {collectCorrections, correctionPrompt} = require("../integrations/chatgpt-extension/correction.js");

const search = "https://chatgpt.com/?hints=search&q=efaso+Pale+del+rotore+gialle+per+elicottero+S107G";

function text(value) {return {nodeType: 3, textContent: value};}
function element(tag, children = [], attrs = {}) {
  const node = {nodeType: 1, tagName: tag.toUpperCase(), childNodes: children,
    textContent: children.map(child => child.textContent || "").join(""),
    href: attrs.href,
    getAttribute: name => attrs[name] ?? null,
    matches: () => false,
    closest(selector) {
      if (selector === ".factttl-ui") return null;
      const tags = selector.split(",").map(value => value.trim().toUpperCase());
      for (let parent = this; parent; parent = parent.parentElement) if (tags.includes(parent.tagName)) return parent;
      return null;
    },
    contains(child) {return this === child || this.childNodes.some(node => node === child || node.contains?.(child));},
    querySelectorAll(selector) {
      const found = [], selectors = selector.split(",").map(value => value.trim().toUpperCase());
      for (const child of this.childNodes) {
        if (selectors.some(value => value === child.tagName || value === "A[HREF]" && child.tagName === "A" && child.href)) found.push(child);
        if (child.querySelectorAll) found.push(...child.querySelectorAll(selector));
      }
      return found;
    },
    querySelector(selector) {return this.querySelectorAll(selector)[0] || null;},
  };
  children.forEach(child => {child.parentElement = node;});
  return node;
}

test("helicopter product-search href stays attached to the product and claimed price", () => {
  const anchor = element("a", [text("Apri il prodotto"), element("svg", [text("decorative icon")])], {href: search});
  const row = element("tr", [element("td", [element("p", [text("efaso Pale del rotore S107G")])]), element("td", [element("p", [text("5,00 €")])]), element("td", [element("p", [anchor])])]);
  const root = element("table", [row]);
  assert.equal(content.sourceFor(anchor), row);
  const payload = content.serializeMessage(row);
  assert.deepEqual(payload.links, [search]);
  assert.match(payload.text, /efaso Pale del rotore S107G 5,00 €/);
  assert.ok(payload.text.includes(`[Apri il prodotto](${search})`));
  assert.doesNotMatch(payload.text, /decorative icon/);
  assert.deepEqual(content.itemTargets(root), [anchor]);
});

test("ordinary host chat navigation remains excluded from verification", () => {
  const anchors = ["https://chatgpt.com/c/private-conversation", "https://chatgpt.com/?q=hello", "https://claude.ai/chat/private-conversation"].map(href => element("a", [text("Open chat")], {href}));
  const root = element("article", anchors.map(anchor => element("p", [anchor])));
  assert.deepEqual(content.itemTargets(root), []);
  assert.deepEqual(content.serializeMessage(root).links, []);
});

test("generated illustration and favicon URLs are omitted as product evidence", () => {
  const assetURLs = ["https://images.openai.com/static-rsc-4/example?purpose=inline", "https://www.google.com/s2/favicons?domain=https%3A%2F%2Fwww.trovaprezzi.it&sz=32"];
  const image = element("a", [text("Alasum S107G parts - Walmart.com")], {href: assetURLs[0]});
  const favicon = element("a", [text("Trovaprezzi")], {href: assetURLs[1]});
  const product = element("a", [text("Apri il prodotto")], {href: search});
  const root = element("article", [element("p", [image]), element("p", [product]), element("p", [favicon])]);
  for (const url of assetURLs) assert.equal(content.referenceAssetURL(url), true);
  assert.equal(content.referenceAssetURL("https://www.trovaprezzi.it/elicotteri/s107g"), false);
  assert.deepEqual(content.itemTargets(root), [product]);
  assert.deepEqual(content.serializeMessage(root).links, [search]);
});

test("host search classifier validates destination instead of trusting search-looking text", () => {
  assert.equal(content.hostSearchURL(search), true);
  assert.equal(content.hostSearchURL("https://chatgpt.com/?hints=search&q=" + encodeURIComponent("S107G motore 3,7 V")), true);
  for (const url of [
    "http://chatgpt.com/?hints=search&q=S107G",
    "https://chatgpt.com:8443/?hints=search&q=S107G",
    "https://user:secret@chatgpt.com/?hints=search&q=S107G",
    "https://chatgpt.com.evil.example/?hints=search&q=S107G",
    "https://chatgpt.com/c/private-chat?hints=search&q=S107G",
    "https://chatgpt.com/?hints=search&q=",
    "https://chatgpt.com/?hints=search&q=%20%20",
    "https://chatgpt.com/?hints=not-search&q=S107G",
  ]) assert.equal(content.hostSearchURL(url), false, url);
});

test("host product search and Amazon search are selection links, never stock evidence", () => {
  assert.equal(searchDestination(search), "host");
  assert.equal(searchDestination("https://www.amazon.it/s?k=S107G"), "amazon");
  assert.equal(searchDestination("https://www.amazon.it/dp/B0DKF9NCN1"), null);
  assert.equal(searchDestination("https://images.openai.com/static-rsc-4/example?purpose=inline"), null);
  for (const result of [{}, {status: "ERROR"}, {checks: [{result: {url: search, kind: "link_available", outcome: "SUPPORTED"}}]}]) {
    const summary = summarize(result, search);
    assert.equal(summary.status, "SEARCH");
    assert.match(summary.label, /Ricerca ChatGPT/);
    assert.doesNotMatch(summary.label, /non disponibile|Link accessibile/i);
  }
});

test("missing service connection still allows local correction of fake product destinations", () => {
  const original = "efaso Pale del rotore S107G · Prezzo verificato 5,00 € · Apri il prodotto";
  const findings = collectCorrections([{url: search, text: original, response: {ok: false, error: "Connection refused"}}]);
  assert.equal(findings.length, 1);
  assert.equal(findings[0].property, "product_selection");
  assert.equal(findings[0].url, search);
  assert.equal(findings[0].scope, "link_structure");
  assert.match(findings[0].original, /Prezzo verificato 5,00/);
  assert.doesNotMatch(findings[0].observed, /esaurito|non disponibile/i);
  const prompt = correctionPrompt(findings);
  assert.match(prompt, /link diretti/i);
  assert.match(prompt, /budget, componenti, paese e negozio/);
  assert.match(prompt, /Non inventare/);
  assert.ok(prompt.includes(search));
});

test("offline search finding reaches automatic follow-up rather than stopping at a badge", async () => {
  class Node {
    constructor() {this.children = []; this.listeners = {}; this.dataset = {}; this.isConnected = true;}
    append(...nodes) {this.children.push(...nodes);}
    replaceChildren(...nodes) {this.children = nodes;}
    setAttribute() {}
    addEventListener(type, fn) {this.listeners[type] = fn;}
    remove() {this.isConnected = false;}
  }
  const root = new Node(), control = new Node(), calls = [], prompts = [];
  root.dataset.factttlCorrectionIdentity = "helicopter-answer";
  const state = {enabled: true, chatId: "chatgpt:helicopter-test", autoCorrection: true};
  const sandbox = vm.createContext({
    document: {hidden: false, createElement: () => new Node()},
    FactTTLItemUI: {summarize, searchDestination}, crypto: webcrypto, TextEncoder, Uint8Array, URL, Date,
  });
  vm.runInContext(readFileSync(require.resolve("../integrations/chatgpt-extension/correction.js"), "utf8"), sandbox);
  const correction = sandbox.FactTTLCorrection.install({
    getState: () => state, control, isStreaming: () => false,
    memory: {isEnabled: () => true, clearCorrectionDraft() {}, hasDraft: () => false,
      sendCorrection: async (prompt, guard) => {assert.equal(guard(), true); prompts.push(prompt); return {ok: true};}},
    send: async message => {
      calls.push(message);
      if (message.type === "GET_MEMORY_CONTEXT") return {ok: false, error: "Connection refused"};
      if (message.type === "RESERVE_CORRECTION") return {ok: true, reserved: true, reservation: "owned-local-reservation"};
      throw new Error(`Unexpected call ${message.type}`);
    },
  });
  const args = {root, identity: "helicopter-answer", settled: true,
    entries: [{url: search, text: "Prezzo verificato 5,00 €", response: {ok: false, error: "Connection refused"}}]};
  await correction.update(args);
  await correction.update(args);
  assert.equal(prompts.length, 1);
  assert.match(prompts[0], /link diretti/i);
  assert.ok(prompts[0].includes(search));
  assert.deepEqual(calls.map(call => call.type), ["GET_MEMORY_CONTEXT", "RESERVE_CORRECTION"]);
});

test("unproven stock cannot become a saved or automatically corrected unavailable offer", () => {
  const url = "https://www.amazon.it/dp/B0DKF9NCN1";
  const result = {checks: [{result: {url, kind: "product_availability", outcome: "INCONCLUSIVE", expected_value: "false", observed_value: null}}]};
  assert.notEqual(summarize(result, url).status, "CONTRADICTED");
  assert.doesNotMatch(summarize(result, url).label, /Prodotto non disponibile/);
  assert.deepEqual(collectCorrections([{url, text: "Scheda ricevente Non disponibile", response: {ok: true, result}}]), []);
});

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.listeners = {};
    this.parentElement = null;
    this._text = "";
  }

  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(""); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.children.push(node);
    }
  }
  after(node) {
    if (this.parentElement) {
      const siblings = this.parentElement.children;
      const index = siblings.indexOf(this);
      node.parentElement = this.parentElement;
      siblings.splice(index + 1, 0, node);
    }
  }
  remove() {
    if (!this.parentElement) return;
    const siblings = this.parentElement.children;
    const index = siblings.indexOf(this);
    if (index >= 0) siblings.splice(index, 1);
    this.parentElement = null;
  }
  close() { this.closed = true; }
  showModal() { this.open = true; }
  focus() { this.focused = true; }
}

function loadItemUI() {
  const document = {
    body: new FakeElement("body"),
    createElement: tag => new FakeElement(tag),
  };
  const context = vm.createContext({document, module: {exports: {}}, URL, Date});
  const source = fs.readFileSync(path.join(__dirname, "../integrations/chatgpt-extension/item-ui.js"), "utf8");
  vm.runInContext(source, context);
  return {api: context.FactTTLItemUI, document};
}

function textIn(element) { return element.textContent; }

test("external discovery details disclose Bing queries and exclude snippets as proof", () => {
  const {api, document} = loadItemUI();
  const paragraph = new FakeElement("p"); paragraph.textContent = "Una notizia da controllare";
  document.body.append(paragraph);
  const state = api.create(paragraph, () => {});
  api.update(state, {ok: true, result: {
    discovery: {enabled: true, provider: "bing_rss", queries_sent: 1},
    checks: [{result: {kind: "news", url: "https://news.example/story", outcome: "INCONCLUSIVE", evidence: [{provider: "public_source_discovery", status: "FOUND", fetched_source_count: 2, independence_established: false}]}}],
  }});
  state.badge.listeners.click();
  const rendered = textIn(document.body.children.at(-1));
  assert.match(rendered, /Ricerca esterna Bing: inviate 1 query/);
  assert.match(rendered, /riassunti non sono prove/);
  assert.match(rendered, /Lette 2 fonti/);
  assert.match(rendered, /indipendenza non è stata accertata/);
  assert.equal(state.badge.dataset.status, "INCONCLUSIVE");
});

test("product sheet uses source identity and separates observed and asserted prices", () => {
  const {api, document} = loadItemUI();
  const anchor = new FakeElement("a"); anchor.href = "https://shop.example/product"; anchor.textContent = "Apri su Amazon";
  document.body.append(anchor);
  const state = api.create(anchor, () => {});
  api.update(state, {ok: true, result: {discovery: {enabled: true, queries_sent: 0}, checks: [
    {result: {url: anchor.href, kind: "product_price", outcome: "CONTRADICTED", expected_value: "9 EUR", observed_value: "12 EUR", evidence: [{product_title: "ESP32 DevKit C"}]}},
    {result: {url: anchor.href, kind: "product_availability", outcome: "SUPPORTED", expected_value: "true", observed_value: "available"}},
    {result: {url: anchor.href, kind: "link_available", outcome: "SUPPORTED"}},
    {result: {url: anchor.href, kind: "product_discount", outcome: "INCONCLUSIVE", expected_value: "true"}},
  ]}});
  state.badge.listeners.click();
  const rendered = textIn(document.body.children.at(-1));
  assert.match(rendered, /ESP32 DevKit C/);
  assert.match(rendered, /Prezzo letto: 12,00\s*€/);
  assert.match(rendered, /Nella risposta: 9,00\s*€/);
  assert.match(rendered, /Disponibile sulla pagina pubblica/);
  assert.doesNotMatch(rendered, /Apertura del link/);
  assert.doesNotMatch(rendered, /Ricerca esterna Bing|Nella risposta: true/);
  assert.match(rendered, /Nella risposta: In sconto/);
  assert.equal(state.badge.textContent, "! Prezzo diverso");
});

test("failed connection offers recovery without claiming link accessibility", () => {
  const {api, document} = loadItemUI();
  const paragraph = new FakeElement("p"); paragraph.textContent = "Messaggio da verificare"; document.body.append(paragraph);
  const state = api.create(paragraph, () => {});
  api.update(state, {ok: false, error: "UNAUTHORIZED"}); state.badge.listeners.click();
  const rendered = textIn(document.body.children.at(-1));
  assert.match(rendered, /Importa nuovamente il file di configurazione/);
  assert.doesNotMatch(rendered, /Link accessibile|La pagina si apre/);
});

test("an unlinked paragraph can display evidence from discovered publisher URLs", () => {
  const {api, document} = loadItemUI();
  const paragraph = new FakeElement("p"); paragraph.textContent = "La notizia annuncia un evento pubblico da verificare.";
  document.body.append(paragraph);
  const state = api.create(paragraph, () => {});
  api.update(state, {ok: true, result: {checks: [{result: {
    url: "https://publisher.example/discovered", kind: "news", outcome: "SUPPORTED",
    claim_text: paragraph.textContent,
    evidence: [{provider: "ai_assessed_live_source", scope: "current_source_consistency", assessment: "SUPPORTED", citations: [{quote: "Una citazione presente nella fonte scoperta."}]}],
  }}]}});
  assert.equal(state.url, null);
  assert.equal(state.badge.dataset.status, "SUPPORTED");
  state.badge.listeners.click();
  const rendered = textIn(document.body.children.at(-1));
  assert.match(rendered, /Coerente con la fonte/);
  assert.match(rendered, /Una citazione presente nella fonte scoperta/);
});

test("long evidence has a concise preview and an accessible complete disclosure", () => {
  const {api, document} = loadItemUI();
  const paragraph = new FakeElement("p"); paragraph.textContent = "Notizia da confrontare";
  document.body.append(paragraph);
  const state = api.create(paragraph, () => {});
  const quote = "Prova completa della fonte. ".repeat(30);
  api.update(state, {ok: true, result: {checks: [{result: {
    url: "https://news.example/story", kind: "news", outcome: "INCONCLUSIVE",
    evidence: [{source_excerpt: quote}, {provider: "ai_assessed_live_source", configured: true, citations: [{quote}]}],
    rationale: "Motivazione dettagliata. ".repeat(30),
  }}]}});
  state.badge.listeners.click();
  const dialog = document.body.children.at(-1);
  function descendants(node) { return node.children.flatMap(child => [child, ...descendants(child)]); }
  const all = descendants(dialog);
  const disclosures = all.filter(node => node.tagName === "DETAILS" && node.className === "factttl-full-evidence");
  assert.equal(disclosures.length, 2);
  assert.ok(disclosures.every(node => node.children[0].tagName === "SUMMARY" && node.children[0].textContent === "Leggi prove complete"));
  const visibleQuotes = all.filter(node => node.tagName === "BLOCKQUOTE" && node.parentElement.tagName !== "DETAILS");
  assert.equal(visibleQuotes.length, 1); // Do not repeat source excerpts when quoted evidence is present.
  assert.ok(visibleQuotes[0].textContent.length <= 351);
  assert.equal(disclosures[0].children[1].textContent, quote);
});

test("editing a reused link clears old evidence and updates its destination", () => {
  const {api, document} = loadItemUI();
  const anchor = new FakeElement("a");
  anchor.href = "https://shop.example/old";
  anchor.textContent = "Vecchio prodotto";
  document.body.append(anchor);
  const state = api.create(anchor, () => {});
  api.update(state, {ok: true, result: {checks: [{result: {
    url: anchor.href, kind: "product_price", outcome: "SUPPORTED", observed_value: "10 EUR",
  }}]}});
  state.badge.listeners.click();
  const previousDialog = document.body.children.at(-1);
  anchor.href = "https://shop.example/new";
  anchor.textContent = "Nuovo prodotto";
  api.invalidate(state, anchor);
  assert.equal(state.result, undefined);
  assert.equal(state.url, anchor.href);
  assert.equal(state.title, "Nuovo prodotto");
  assert.equal(state.badge.dataset.status, "PENDING");
  assert.equal(previousDialog.parentElement, null);
  state.badge.listeners.click();
  const rendered = textIn(document.body.children.at(-1));
  assert.match(rendered, /Nuovo prodotto/);
  assert.doesNotMatch(rendered, /Dati confermati|10 EUR/);
});

test("opening an updated badge reads the same state object and current evidence", () => {
  const {api, document} = loadItemUI();
  const paragraph = new FakeElement("p");
  paragraph.textContent = "Prezzo 9,99 EUR";
  document.body.append(paragraph);
  const anchor = new FakeElement("a");
  anchor.href = "https://shop.example/item";
  anchor.textContent = "prodotto";
  document.body.append(anchor);
  let retried = false;
  const state = api.create(anchor, () => { retried = true; });
  const result = {
    status: "CONTRADICTED",
    preferences: {country: "IT", language: "it"},
    checks: [{
      result: {
        url: anchor.href,
        kind: "product_price",
        outcome: "CONTRADICTED",
        expected_value: "9.99 EUR",
        observed_value: "10.99 EUR",
        rationale: "Prezzo letto sulla pagina pubblica.",
      },
      regional_context: {
        country: "IT",
        language: "it",
        marketplace_country: "US",
        warning: "La fonte è negli Stati Uniti; il prezzo per l'Italia non è confermato.",
        limitation: "La preferenza paese non dimostra la destinazione di consegna.",
      },
    }],
  };

  api.update(state, {ok: true, result});
  state.badge.listeners.click();
  const dialog = document.body.children.at(-1);
  const rendered = textIn(dialog);
  assert.equal(state.badge.dataset.status, "CONTRADICTED");
  assert.match(rendered, /Prezzo letto: 10,99\s*€/);
  assert.match(rendered, /Nella risposta: 9,99\s*€/);
  assert.match(rendered, /Paese scelto: Italia/);
  assert.match(rendered, /marketplace della fonte è diverso/);
  assert.equal(retried, false);

  const content = fs.readFileSync(path.join(__dirname, "../integrations/chatgpt-extension/content.js"), "utf8");
  assert.match(content, /state\s*=\s*Object\.assign\(resultUI\(node\),/);
  assert.doesNotMatch(content, /state\s*=\s*\{\.\.\.resultUI\(node\)/);
});

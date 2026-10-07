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
  assert.match(rendered, /Prezzo letto: 10\.99 EUR/);
  assert.match(rendered, /Nella risposta era indicato 9\.99 EUR/);
  assert.match(rendered, /Paese scelto: Italia/);
  assert.match(rendered, /marketplace della fonte è diverso/);
  assert.equal(retried, false);

  const content = fs.readFileSync(path.join(__dirname, "../integrations/chatgpt-extension/content.js"), "utf8");
  assert.match(content, /state\s*=\s*Object\.assign\(resultUI\(node\),/);
  assert.doesNotMatch(content, /state\s*=\s*\{\.\.\.resultUI\(node\)/);
});

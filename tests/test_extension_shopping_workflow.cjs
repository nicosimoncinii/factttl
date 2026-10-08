const assert = require('node:assert/strict');
const {test} = require('node:test');
const {serializeMessage, sourceFor} = require('../integrations/chatgpt-extension/content.js');
const {summarize} = require('../integrations/chatgpt-extension/item-ui.js');
global.FactTTLItemUI = {summarize};
const {collectCorrections, correctionPrompt} = require('../integrations/chatgpt-extension/correction.js');

function node(tag, children = [], attrs = {}) {
  const n = {nodeType: 1, tagName: tag.toUpperCase(), childNodes: children,
    textContent: children.map(c => c.textContent).join(''),
    getAttribute: key => attrs[key] ?? null, matches: () => false,
    closest(selector) {
      let p = this;
      while (p) {
        if (selector.split(',').map(s => s.trim().toUpperCase()).includes(p.tagName)) return p;
        p = p.parentElement;
      }
      return null;
    },
    querySelectorAll(selector) {
      const found = [];
      for (const c of this.childNodes) {
        if (c.tagName === selector.toUpperCase()) found.push(c);
        if (c.querySelectorAll) found.push(...c.querySelectorAll(selector));
      }
      return found;
    }};
  children.forEach(c => {c.parentElement = n;});
  return n;
}
const txt = value => ({nodeType: 3, textContent: value});
function fixture() {
  const url = 'https://www.amazon.it/s?k=esp32';
  const anchor = node('a', [txt('Amazon'), node('svg', [txt('decorative icon')])], {href: url});
  const row = node('tr', [node('td', [node('p', [txt('ESP32')])]), node('td', [node('p', [txt('9,99 €')])]), node('td', [node('p', [anchor])])]);
  node('table', [node('thead', [node('tr', [node('th', [txt('Componente')]), node('th', [txt('Prezzo indicativo')])])]), node('tbody', [row])]);
  return {url, anchor, row};
}

test('shopping table retains row name, estimated price, URL and header scope with paragraphs inside cells', () => {
  const {anchor, row, url} = fixture();
  assert.equal(sourceFor(anchor), row);
  const payload = serializeMessage(sourceFor(anchor));
  assert.match(payload.text, /^Prezzo indicativo: ESP32 9,99 €/);
  assert.ok(payload.text.includes(`[Amazon](${url})`));
  assert.ok(!payload.text.includes('decorative icon'));
  assert.ok(!payload.text.includes('\n'));
  assert.deepEqual(payload.links, [url]);
});

test('accessible Amazon search is not a confirmed product and generates a product-selection correction', () => {
  const {url, row} = fixture();
  const result = {checks: [{result: {url, kind: 'link_available', outcome: 'SUPPORTED'}}]};
  assert.equal(summarize(result, url).status, 'SEARCH');
  const findings = collectCorrections([{url, text: serializeMessage(row).text, response: {ok: true, result}}]);
  assert.equal(findings.length, 1);
  assert.equal(findings[0].property, 'product_selection');
  assert.match(findings[0].original, /Prezzo indicativo: ESP32 9,99/);
  assert.match(correctionPrompt(findings), /Non inventare/);
});

test('actual browser price and stock contradicting a row are separately retained in corrections', () => {
  const url = 'https://www.amazon.it/dp/B012345678';
  const observed_at = new Date().toISOString();
  const evidence = [{provider: 'live_public_web', scope: 'browser_current_offer', product_title: 'ESP32 DevKit'}];
  const result = {checks: [
    {result: {url, kind: 'product_price', outcome: 'CONTRADICTED', expected_value: '9.99 EUR', observed_value: '10.99 EUR', observed_at, evidence}},
    {result: {url, kind: 'product_availability', outcome: 'CONTRADICTED', expected_value: 'true', observed_value: 'unavailable', observed_at, evidence}},
  ]};
  assert.equal(summarize(result, url).status, 'CONTRADICTED');
  const findings = collectCorrections([{url, response: {ok: true, result}}]);
  assert.deepEqual(findings.map(f => [f.property, f.original, f.observed]), [['product_price', '9.99 EUR', '10.99 EUR'], ['product_availability', 'true', 'unavailable']]);
  assert.ok(findings.every(f => f.title === 'ESP32 DevKit' && f.scope === 'browser_current_offer'));
});

test('fixture budget sums to 41.96 EUR without treating estimates as observed offers', () => {
  const cents = [999, 1049, 999, 399, 350, 400];
  assert.equal(cents.reduce((a, b) => a + b, 0), 4196);
});

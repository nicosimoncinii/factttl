const {test} = require("node:test");
const assert = require("node:assert/strict");
const {money, productIdentity, readProduct} = require("../integrations/chatgpt-extension/merchant.js");

test("offer money preserves currency and decimal separators", () => {
  assert.deepEqual(money("10,99 €"), {amount: "10.99", currency: "EUR"});
  assert.deepEqual(money("$1,299.99"), {amount: "1299.99", currency: "USD"});
  assert.deepEqual(money("1.299,99 EUR"), {amount: "1299.99", currency: "EUR"});
  assert.deepEqual(money("£10.99"), {amount: "10.99", currency: "GBP"});
  for (const value of ["12.3 EUR", "1,234.567 EUR", "EUR 10.99 / EUR 2.00", "$10.99 EUR", "0 EUR", "10.99", "free"]) assert.equal(money(value), null);
});

test("product identity rejects credential URLs, foreign hosts and mismatched ASIN paths", () => {
  assert.deepEqual(productIdentity("https://www.amazon.it/dp/B0DKF9NCN1?tag=tracking"), {host: "amazon.it", asin: "B0DKF9NCN1"});
  assert.deepEqual(productIdentity("https://amazon.it/gp/aw/d/b0dkf9ncn1"), {host: "amazon.it", asin: "B0DKF9NCN1"});
  for (const url of ["http://amazon.it/dp/B0DKF9NCN1", "https://amazon.it.evil.example/dp/B0DKF9NCN1", "https://user:password@amazon.it/dp/B0DKF9NCN1", "https://amazon.it:444/dp/B0DKF9NCN1"]) assert.equal(productIdentity(url), null);
});

function fixture({price = "10,99 €", asin = "B0DKF9NCN1", hidden = false, stock = "Disponibilità immediata", buy = true, captcha = false} = {}) {
  const body = {innerText: captcha ? "Inserisci i caratteri" : "ESP32 Disponibilità immediata"};
  const element = (textContent, overrides = {}) => ({textContent, parentElement: body, closest: () => null, ...overrides});
  const offer = element(price, {closest: selector => hidden && selector.includes("hidden") ? {} : null});
  const root = element("", {querySelectorAll: () => [offer]});
  const nodes = {"input#ASIN": {value: asin}, "#productTitle": element("ESP32 DevKit"), "#corePriceDisplay_desktop_feature_div": root, "#availability": element(stock), "#add-to-cart-button": buy ? element("Compra", {disabled: false}) : null};
  return {body, defaultView: {getComputedStyle: () => ({display: "block", visibility: "visible"})}, querySelector: selector => nodes[selector] || null};
}

test("primary browser offer returns exact current 10.99 EUR and stock", () => {
  const result = readProduct(fixture(), "https://www.amazon.it/dp/B0DKF9NCN1");
  assert.equal(result.price, "10.99"); assert.equal(result.currency, "EUR");
  assert.equal(result.availability, "available"); assert.equal(result.title, "ESP32 DevKit");
});

test("hidden offer, wrong product, challenge and absent buy button never confirm stock blindly", () => {
  assert.equal(readProduct(fixture({hidden: true}), "https://amazon.it/dp/B0DKF9NCN1").price, null);
  assert.equal(readProduct(fixture({asin: "B0XXXXXXXX"}), "https://amazon.it/dp/B0DKF9NCN1").status, "WRONG_PRODUCT");
  assert.equal(readProduct(fixture({captcha: true}), "https://amazon.it/dp/B0DKF9NCN1").status, "BLOCKED");
  assert.equal(readProduct(fixture({buy: false}), "https://amazon.it/dp/B0DKF9NCN1").availability, "unknown");
  assert.equal(readProduct(fixture({stock: "Attualmente non disponibile"}), "https://amazon.it/dp/B0DKF9NCN1").availability, "unavailable");
});

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");

class Element {
  constructor() { this.dataset = {}; this.listeners = {}; this.textContent = ""; this.value = ""; this.hidden = false; this.button = {disabled: false}; }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  querySelector() { return this.button; }
  setAttribute(name, value) { this[name] = value; }
  click() {}
}

function load({engine = {configured: false, ready: false}, handler, extension = true, locale = "it-IT"} = {}) {
  const elements = new Map();
  const messages = [];
  const timers = [];
  const document = {
    documentElement: {}, title: "",
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new Element());
      return elements.get(id);
    },
    querySelectorAll() { return []; },
  };
  document.getElementById("country").options = ["IT", "US", "GB", "DE", "FR", "ES"].map(value => ({value}));
  const runtime = {
    getURL: () => "moz-extension://11111111-1111-4111-8111-111111111111/",
    async sendMessage(message) {
      messages.push(message);
      if (handler) return handler(message);
      if (message.type === "GET_PREFERENCES") return {ok: true, preferences: {country: "IT", language: "it"}};
      if (message.type === "GET_HEALTH") return {ok: true, status: {status: "ready", service: "FactTTL", news_engine: engine}};
      return {ok: true};
    },
  };
  const context = vm.createContext({document, navigator: {language: locale, clipboard: {async writeText() {}}},
    ...(extension ? {browser: {runtime}} : {}), Intl, Promise, JSON,
    setTimeout(callback) { const timer = {callback, canceled: false}; timers.push(timer); return timer; },
    clearTimeout(timer) { if (timer) timer.canceled = true; },
  });
  const source = fs.readFileSync(path.join(__dirname, "../integrations/chatgpt-extension/options.js"), "utf8");
  vm.runInContext(source, context);
  return {context, elements, messages, timers};
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test("configured model alone never displays a ready-green status", async () => {
  const fixture = load({engine: {configured: true, model: "qwen3:4b"}});
  await settle();
  assert.equal(fixture.elements.get("news-engine-state").dataset.state, "configured");
  assert.match(fixture.elements.get("news-engine-label").textContent, /disponibilità da verificare/);
});

test("unavailable model stays amber while the bridge is connected", async () => {
  const fixture = load({engine: {configured: true, ready: false, model: "qwen3:4b"}});
  await settle();
  assert.equal(fixture.elements.get("connection-state").dataset.state, "connected");
  assert.equal(fixture.elements.get("news-engine-state").dataset.state, "unavailable");
  assert.match(fixture.elements.get("news-engine-label").textContent, /non ancora disponibile/);
});

test("available model is labeled availability rather than verified inference", async () => {
  const fixture = load({engine: {configured: true, ready: true, model: "qwen3:4b"}});
  await settle();
  assert.equal(fixture.elements.get("news-engine-state").dataset.state, "ready");
  assert.equal(fixture.elements.get("news-engine-label").textContent, "Modello locale disponibile");
  assert.match(fixture.elements.get("news-engine-description").textContent, /non certifica/);
});

test("configured false never becomes ready even with malformed ready true", async () => {
  const fixture = load({engine: {configured: false, ready: true}});
  await settle();
  assert.equal(fixture.elements.get("news-engine-state").dataset.state, "missing");
});

test("page opened outside the extension gives an instruction instead of crashing", async () => {
  const fixture = load({extension: false});
  await settle();
  assert.match(fixture.elements.get("status").textContent, /pulsante FactTTL/);
  assert.equal(fixture.elements.get("import-config").disabled, true);
  assert.equal(fixture.elements.get("connection-state").dataset.state, "unconfigured");
});

test("a hung extension message leaves the checking state after the bounded timeout", async () => {
  const fixture = load({handler: () => new Promise(() => {})});
  assert.equal(fixture.elements.get("country").value, "IT");
  for (const timer of fixture.timers) if (!timer.canceled) timer.callback();
  await settle();
  assert.equal(fixture.elements.get("connection-state").dataset.state, "offline");
});

test("invalid browser locale falls back without breaking the settings page", async () => {
  const fixture = load({locale: "not@locale"});
  await settle();
  assert.equal(fixture.elements.get("country").value, "IT");
  assert.equal(fixture.elements.get("language").value, "it");
});

test("invalid config and other-extension config cannot persist a token", async () => {
  const fixture = load();
  await settle();
  const file = data => ({size: 100, async text() { return JSON.stringify(data); }});
  const importConfig = vm.runInContext("importConfiguration", fixture.context);
  await assert.rejects(importConfig(file({base_url: "https://remote.example", token: "a".repeat(40)})), /INVALID_CONFIGURATION/);
  await assert.rejects(importConfig(file({base_url: "http://127.0.0.1:8765", allowed_origin: "moz-extension://other", token: "a".repeat(40)})), /ORIGIN_MISMATCH/);
  assert.equal(fixture.messages.some(message => message.type === "SET_TOKEN"), false);
});

test("imported token remains in privileged extension messaging and is cleared from the input", async () => {
  const fixture = load();
  await settle();
  const token = "a".repeat(40);
  fixture.elements.get("token").value = token;
  await fixture.elements.get("configuration").listeners.submit({preventDefault() {}});
  assert.equal(fixture.elements.get("token").value, "");
  assert.ok(fixture.messages.some(message => message.type === "SET_TOKEN" && message.payload.token === token));
  assert.equal(fixture.elements.get("status").textContent.includes(token), false);
});

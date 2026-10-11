"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {webcrypto} = require("node:crypto");

// Run the real badge and content modules beside an instrumented host editor.
// Old persisted automatic-correction settings must never reactivate injection.
function harness({host = "chatgpt.com", draft = "La mia domanda originale"} = {}) {
  let now = Date.now();
  const intervals = [], scheduled = [], runtimeListeners = [], globalListeners = [], calls = [];
  const editorActivity = {read: 0, write: 0, click: 0, focus: 0, event: 0};
  class Node {
    constructor(tag = "DIV", text = "") {this.nodeType = 1; this.tagName = tag; this.childNodes = []; this.dataset = {}; this.listeners = {}; this.isConnected = true; this.textContent = text;}
    append(...nodes) {for (const node of nodes) {this.childNodes.push(node); node.parentElement = this;}}
    after(node) {this.parentElement?.append(node);}
    setAttribute(name, value) {this[name] = value;}
    getAttribute(name) {return this[name] || null;}
    addEventListener(type, handler) {this.listeners[type] = handler;}
    matches() {return false;}
    contains(other) {return this === other || this.childNodes.some(child => child === other || child.contains?.(other));}
    closest(selector) {
      for (let node = this; node; node = node.parentElement) {
        if (selector === ".factttl-ui" && node.className?.split(" ").includes("factttl-ui")) return node;
        if (selector.split(",").some(tag => tag.trim().toUpperCase() === node.tagName)) return node;
      }
      return null;
    }
    querySelectorAll(selector) {
      const found = [];
      for (const child of this.childNodes) {
        if (selector === "a[href]" && child.tagName === "A" && child.href || selector === "p, li" && ["P", "LI"].includes(child.tagName)) found.push(child);
        if (child.querySelectorAll) found.push(...child.querySelectorAll(selector));
      }
      return found;
    }
    querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
    remove() {this.isConnected = false;}
  }
  const body = new Node("BODY"), root = new Node("ARTICLE"), row = new Node("P");
  const anchor = new Node("A", "ESP32"), label = {nodeType: 3, textContent: "ESP32 9,99 €"};
  anchor.href = "https://www.amazon.it/dp/B0DKF9NCN1"; anchor.append(label); row.append(anchor); root.append(row); body.append(root);
  const editor = new Node("TEXTAREA");
  Object.defineProperty(editor, "value", {get() {editorActivity.read += 1; return draft;}, set() {editorActivity.write += 1;}});
  editor.focus = () => {editorActivity.focus += 1;}; editor.click = () => {editorActivity.click += 1;}; editor.dispatchEvent = () => {editorActivity.event += 1;};
  editor.addEventListener = () => {editorActivity.event += 1;}; body.append(editor);
  const nativeSend = new Node("BUTTON"); nativeSend.click = () => {editorActivity.click += 1;}; body.append(nativeSend);
  const document = {
    body, hidden: false,
    createElement: tag => new Node(tag.toUpperCase()),
    querySelector(selector) {
      if (/composer|prompt-textarea|contenteditable|textarea|send-button/i.test(selector)) {editorActivity.read += 1; return /send-button/i.test(selector) ? nativeSend : editor;}
      if (selector === "#factttl-controller") return body.childNodes.find(node => node.id === "factttl-controller") || null;
      return null;
    },
    querySelectorAll(selector) {
      if (selector.includes("assistant-message")) return [root];
      if (selector === ".factttl-result") return body.querySelectorAll(selector);
      if (/user-message|data-message-author-role="user"|textarea|contenteditable/i.test(selector)) {editorActivity.read += 1; return [editor];}
      return [];
    },
    addEventListener() {editorActivity.event += 1;},
    execCommand() {editorActivity.write += 1;},
  };
  const kind = host.includes("claude") ? "claude" : host.includes("gemini") ? "gemini" : "chatgpt";
  const path = kind === "claude" ? "/chat/test" : kind === "gemini" ? "/app/test" : "/c/test";
  const runtime = {
    onMessage: {addListener: fn => runtimeListeners.push(fn)},
    async sendMessage(message) {
      calls.push(message);
      if (message.type === "GET_CHAT_STATE") return {ok: true, enabled: true, autoCorrection: true, memoryEnabled: true};
      if (message.type === "VERIFY_MESSAGE") return {ok: true, result: {checks: [{result: {url: anchor.href, kind: "product_availability", outcome: "CONTRADICTED", expected_value: "true", observed_value: "unavailable", observed_at: new Date(now).toISOString(), evidence: [{provider: "live_public_web"}]}}]}};
      return {ok: true};
    },
  };
  const sandbox = vm.createContext({document, browser: {runtime}, location: {pathname: path, hostname: host, origin: `https://${host}`}, crypto: webcrypto, URL, URLSearchParams, Intl,
    Date: class extends Date {static now() {return now;}},
    MutationObserver: class {constructor(callback) {this.callback = callback;} observe() {}},
    addEventListener: (type, callback) => globalListeners.push({type, callback}),
    setInterval: fn => intervals.push(fn), setTimeout: fn => {scheduled.push(fn); return fn;}, clearTimeout() {},
    FactTTLMemory: {install() {throw new Error("Retired memory injector was installed");}},
    FactTTLCorrection: {install() {throw new Error("Retired correction injector was installed");}},
  });
  for (const filename of ["amazon-url.js", "item-ui.js", "content.js"]) vm.runInContext(fs.readFileSync(require.resolve(`../integrations/chatgpt-extension/${filename}`), "utf8"), sandbox);
  return {editorActivity, calls, body, root, editor, nativeSend, runtimeListeners, globalListeners,
    async tick() {now += 2000; for (const fn of intervals) fn(); await new Promise(resolve => setImmediate(resolve));},
    async settle() {await new Promise(resolve => setImmediate(resolve));},
  };
}

for (const host of ["chatgpt.com", "claude.ai", "gemini.google.com"]) test(`${host}: stale auto/memory flags never write, click, inspect or intercept the composer`, async () => {
  const h = harness({host}); await h.settle(); await h.tick(); await h.tick();
  for (const listener of h.runtimeListeners) listener({type: "CORRECTION_MODE_CHANGED", chatId: `${host.startsWith("claude") ? "claude" : host.startsWith("gemini") ? "gemini" : "chatgpt"}:test`, enabled: true});
  await h.tick();
  assert.deepEqual(h.editorActivity, {read: 0, write: 0, click: 0, focus: 0, event: 0});
  assert.ok(h.calls.some(message => message.type === "VERIFY_MESSAGE"));
  assert.ok(h.calls.every(message => ["GET_CHAT_STATE", "VERIFY_MESSAGE"].includes(message.type)));
  assert.deepEqual(h.globalListeners.map(value => value.type), ["popstate"]);
  const control = h.body.childNodes.find(node => node.id === "factttl-controller");
  assert.equal(control.childNodes.length, 2);
  const badges = h.root.querySelectorAll("button");
  assert.equal(control.childNodes.some(node => /Memoria|Correzione/.test(node.textContent)), false);
  assert.equal(h.calls.some(message => /MEMORY|CORRECTION/.test(message.type)), false);
});

test("an empty composer also remains empty after contradicted assistant results", async () => {
  const h = harness({draft: ""}); await h.settle(); await h.tick(); await h.tick();
  assert.deepEqual(h.editorActivity, {read: 0, write: 0, click: 0, focus: 0, event: 0});
});

test("host user send events retain their ordinary behavior", async () => {
  const h = harness(); await h.settle();
  // All listeners installed by the real content script are confined to its
  // own controller/badges or navigation. No listener can cancel host send.
  assert.equal(h.editor.listeners.keydown, undefined);
  assert.equal(h.editor.listeners.submit, undefined);
  assert.equal(h.nativeSend.listeners.click, undefined);
  assert.equal(h.globalListeners.some(({type}) => ["click", "keydown", "submit", "input"].includes(type)), false);
});

test("badge actions contain evidence/source/recheck only, never prompt copying", () => {
  const source = fs.readFileSync(require.resolve("../integrations/chatgpt-extension/item-ui.js"), "utf8");
  assert.doesNotMatch(source, /clipboard\.writeText|Copia la correzione|incolla nella chat|chiede alla chat/);
});

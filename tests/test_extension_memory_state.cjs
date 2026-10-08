"use strict";
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function harness({enabled = true, deferred = false, ignoreHost = false} = {}) {
  const documentListeners = new Map(), calls = [], hostClicks = [], timers = [];
  const state = {enabled, chatId: "chat-a"};
  class Node {
    constructor(tag = "SPAN") {this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.children = []; this.attributes = {}; this.textContent = "";}
    setAttribute(key, value) {this.attributes[key] = value;}
    append(...nodes) {this.children.push(...nodes);}
    addEventListener(type, callback) {this.listeners.set(type, callback);}
    getClientRects() {return [{}];}
    closest(selector) {return selector === "button" && this.tagName === "BUTTON" ? this : null;}
    contains(other) {return other === this;}
    focus() {}
    dispatchEvent() {}
    emit(type) {this.listeners.get(type)?.({target: this, isTrusted: true});}
  }
  class TextArea extends Node {
    constructor() {super("TEXTAREA"); this._value = "Vorrei un ESP32 https://www.amazon.it/dp/B0DKF9NCN1";}
    get value() {return this._value;}
    set value(value) {this._value = value;}
  }
  const editor = new TextArea(), button = new Node("BUTTON"), control = new Node("DIV");
  const document = {
    createElement: tag => new Node(tag.toUpperCase()),
    querySelectorAll: selector => selector.includes("prompt-textarea") ? [editor] : [button],
    addEventListener: (type, callback) => documentListeners.set(type, callback),
  };
  function event(type, options = {}) {
    const value = {type, target: type === "click" ? button : editor, isTrusted: true,
      key: "Enter", defaultPrevented: false, stopped: false, ...options,
      preventDefault() {this.defaultPrevented = true;},
      stopImmediatePropagation() {this.stopped = true;}};
    documentListeners.get(type)?.(value);
    return value;
  }
  button.click = () => {
    event("click", {isTrusted: false});
    hostClicks.push(editor.value);
    if (!ignoreHost) editor.value = "";
  };
  const findings = {findings: [{url: "https://www.amazon.it/dp/B0DKF9NCN1",
    property: "product_price", outcome: "CONTRADICTED", expected_value: "1 EUR",
    observed_value: "10.99 EUR", observed_value_usable_as_current_fact: true,
    do_not_reuse_prior_assertion: true, observed_at: new Date(Date.now() - 1000).toISOString(),
    expires_at: new Date(Date.now() + 60000).toISOString(), source_scope: "browser_current_offer"}]};
  let resolveContext;
  const pending = new Promise(resolve => {resolveContext = resolve;});
  const sandbox = vm.createContext({document, URL, HTMLTextAreaElement: TextArea,
    InputEvent: class {constructor(type, options) {Object.assign(this, {type}, options);}},
    setTimeout: callback => {timers.push(callback); return timers.length;},
  });
  vm.runInContext(readFileSync(path.join(__dirname, "../integrations/chatgpt-extension/memory.js"), "utf8"), sandbox);
  const installed = sandbox.FactTTLMemory.install({getState: () => state,
    control, send: message => {calls.push(message); return deferred ? pending : Promise.resolve({ok: true, context: findings});}});
  return {state, editor, button, control, calls, hostClicks, event, installed,
    resolve: () => resolveContext({ok: true, context: findings}),
    marker: "[FactTTL — verifiche precedenti]"};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test("installation alone never queries memory or sends a message", async () => {
  const h = harness(); await flush();
  assert.equal(h.calls.length, 0); assert.equal(h.hostClicks.length, 0);
  h.event("click", {isTrusted: false}); await flush();
  assert.equal(h.calls.length, 0); assert.equal(h.hostClicks.length, 0);
});

for (const action of ["click", "keydown"]) {
  test(`trusted ${action} attaches relevant data before resuming host send`, async () => {
    const h = harness(), original = h.editor.value;
    const event = h.event(action); await flush();
    assert.equal(event.defaultPrevented, true);
    assert.equal(h.calls.length, 1);
    assert.equal(h.calls[0].type, "GET_MEMORY_CONTEXT");
    assert.equal(h.calls[0].payload.query, original);
    assert.equal(h.calls[0].payload.chatId, "chat-a");
    assert.equal(h.calls[0].payload.urls[0], "https://www.amazon.it/dp/B0DKF9NCN1");
    assert.equal(h.hostClicks.length, 1);
    assert.ok(h.hostClicks[0].startsWith(original));
    assert.ok(h.hostClicks[0].includes(h.marker));
    assert.ok(h.hostClicks[0].includes("10.99 EUR"));
  });
}

test("disabled verification and disabled memory make no context request", async () => {
  const h = harness({enabled: false});
  assert.equal(h.event("click").defaultPrevented, false); await flush();
  assert.equal(h.calls.length, 0); assert.equal(h.hostClicks.length, 0);
  h.state.enabled = true; h.installed.refresh(); h.control.children[0].emit("click");
  assert.equal(h.event("keydown").defaultPrevented, false); await flush();
  assert.equal(h.calls.length, 0); assert.equal(h.hostClicks.length, 0);
});

test("a host-ignored send leaves a removable owned block in the draft", async () => {
  const h = harness({ignoreHost: true}), original = h.editor.value;
  h.event("click"); await flush();
  assert.ok(h.editor.value.includes(h.marker));
  h.editor.value += "\nAggiunta personale";
  h.control.children[0].emit("click");
  assert.equal(h.editor.value, original + "\nAggiunta personale");
  assert.equal(h.hostClicks.length, 1);
});

for (const change of ["route", "draft", "disconnected"]) {
  test(`pending context cannot send after ${change} changes`, async () => {
    const h = harness({deferred: true}); h.event("click");
    assert.equal(h.calls.length, 1); assert.equal(h.hostClicks.length, 0);
    if (change === "route") h.state.chatId = "chat-b";
    if (change === "draft") h.editor.value = "Nuova bozza";
    if (change === "disconnected") h.editor.isConnected = false;
    h.resolve(); await flush();
    assert.equal(h.hostClicks.length, 0);
    assert.equal(h.editor.value.includes(h.marker), false);
  });
}

test("Shift Enter, composing input and duplicate busy send do not create extra requests", async () => {
  const h = harness({deferred: true});
  h.event("keydown", {shiftKey: true}); h.event("keydown", {isComposing: true});
  assert.equal(h.calls.length, 0);
  h.event("keydown"); h.event("click");
  assert.equal(h.calls.length, 1); h.resolve(); await flush();
  assert.equal(h.hostClicks.length, 1);
});

test("modified owned block prevents sending when memory is switched off", async () => {
  const h = harness({ignoreHost: true}); h.event("click"); await flush();
  h.editor.value = h.editor.value.replace("10.99 EUR", "modified");
  h.control.children[0].emit("click");
  assert.ok(h.editor.value.includes(h.marker));
  const event = h.event("click");
  assert.equal(event.defaultPrevented, true);
  assert.equal(h.hostClicks.length, 1);
});

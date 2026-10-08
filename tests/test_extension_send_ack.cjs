"use strict";
const assert = require("node:assert/strict");
const {test} = require("node:test");
const {readFileSync} = require("node:fs");
const vm = require("node:vm");

const correction = "[FactTTL — correzione automatica]\nPassaggio: 1/2.\nPrezzo contestato: 1 EUR → 10.99 EUR.";

function harness({buttonDelay = 0, accepted = false, clearOnly = false, acknowledgeDelay = 0, streaming = false, provider = "chatgpt", priorCorrection = false, emitGeneration = false, acceptedText = null} = {}) {
  let elapsed = 0, sequence = 0;
  const timers = [], calls = [], clicks = [], listeners = new Map();
  const state = {enabled: true, chatId: "chatgpt:send-ack"};
  class Clock extends Date {static now() {return 1750000000000 + elapsed;}}
  class Node {
    constructor(tag = "SPAN") {this.tagName = tag; this.isConnected = true; this.children = []; this.listeners = new Map(); this.attributes = {}; this.textContent = ""; this.innerText = "";}
    append(...children) {this.children.push(...children);}
    setAttribute(name, value) {this.attributes[name] = value;}
    getAttribute(name) {return this.attributes[name] ?? null;}
    addEventListener(type, listener) {this.listeners.set(type, listener);}
    getClientRects() {return [{}];}
    closest(selector) {return selector === "button" && this.tagName === "BUTTON" ? this : null;}
    contains(node) {return this === node;}
    focus() {}
    dispatchEvent() {}
  }
  class TextArea extends Node {
    constructor() {super("TEXTAREA"); this._value = "";}
    get value() {return this._value;}
    set value(value) {this._value = value;}
  }
  const editor = new TextArea(), button = new Node("BUTTON"), control = new Node("DIV");
  button.disabled = false;
  const previousUser = new Node("DIV"); previousUser.textContent = previousUser.innerText = priorCorrection ? correction : "Fammi un carrello di componenti Amazon Italia entro 50 euro";
  let users = [previousUser], generating = streaming;
  const queue = (callback, duration = 0) => {const id = ++sequence; timers.push({id, at: elapsed + duration, callback}); return id;};
  button.click = () => {
    clicks.push(editor.value);
    if (clearOnly) editor.value = "";
    if (accepted) queue(() => {
      const sent = new Node("DIV"); sent.textContent = sent.innerText = acceptedText ?? clicks.at(-1);
      users = [...users, sent]; editor.value = ""; generating = emitGeneration;
    }, acknowledgeDelay);
  };
  const document = {
    hidden: false,
    createElement: tag => new Node(tag.toUpperCase()),
    addEventListener: (type, callback) => listeners.set(type, callback),
    querySelectorAll(selector) {
      if (selector.includes("prompt-textarea") || selector.includes("contenteditable") || selector.includes("textarea[placeholder]")) return [editor];
      const userSelector = {chatgpt: 'data-message-author-role="user"', claude: ".font-user-message", gemini: "user-query"}[provider];
      if (selector.includes(userSelector)) return users;
      if (selector.includes("stop-button") || selector.includes("Stop generating") || selector.includes("data-is-streaming")) {
        if (!generating) return [];
        const stop = new Node("BUTTON"); stop.setAttribute("data-testid", "stop-button"); return [stop];
      }
      if (selector.includes("send-button") || selector.includes("Send message") || selector.includes("Send prompt") || selector.includes('type="submit"')) return elapsed >= buttonDelay ? [button] : [];
      return [];
    },
    querySelector(selector) {return this.querySelectorAll(selector)[0] || null;},
  };
  const sandbox = vm.createContext({document, URL, Date: Clock, HTMLTextAreaElement: TextArea,
    InputEvent: class {constructor(type, options) {Object.assign(this, {type}, options);}},
    setTimeout: queue, clearTimeout: id => {const timer = timers.find(timer => timer.id === id); if (timer) timer.canceled = true;},
  });
  vm.runInContext(readFileSync(require.resolve("../integrations/chatgpt-extension/memory.js"), "utf8"), sandbox);
  const installed = sandbox.FactTTLMemory.install({getState: () => state, control, send: async message => {calls.push(message); return {ok: false};}});
  async function finish(promise, beforeTimer = () => {}) {
    let settled = false, value, failure;
    promise.then(result => {settled = true; value = result;}, error => {settled = true; failure = error;});
    for (let turn = 0; turn < 1000 && !settled; turn += 1) {
      await new Promise(resolve => setImmediate(resolve));
      if (settled) break;
      timers.sort((a, b) => a.at - b.at || a.id - b.id);
      const timer = timers.shift();
      if (!timer) throw new Error("Adapter stalled without an acknowledgment timer");
      elapsed = timer.at; beforeTimer(elapsed);
      if (!timer.canceled) timer.callback();
    }
    assert.equal(settled, true, "Adapter must finish within a bounded acknowledgment window");
    if (failure) throw failure;
    return value;
  }
  return {installed, state, editor, button, users: () => users, clicks, calls, finish, elapsed: () => elapsed};
}

test("clicking an ignored host button does not report automatic correction as sent", async () => {
  const h = harness();
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, false);
  assert.ok(h.clicks.length <= 1, "No repeated clicks while awaiting host acknowledgment");
  assert.equal(h.users().length, 1);
});

test("a send button that mounts after 120 ms is awaited and sends the correction once", async () => {
  const h = harness({buttonDelay: 600, accepted: true});
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, true);
  assert.equal(h.clicks.length, 1);
  assert.equal(h.users().length, 2);
  assert.equal(h.editor.value, "");
});

test("delayed host acceptance waits for a visible submitted correction", async () => {
  const h = harness({accepted: true, acknowledgeDelay: 700});
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, true);
  assert.ok(h.elapsed() >= 700);
  assert.equal(h.users().at(-1).textContent, correction);
  assert.equal(h.clicks.length, 1);
});

test("the submitted correction changing the latest user does not invalidate its own acknowledgment", async () => {
  const h = harness({accepted: true, acknowledgeDelay: 300});
  // Production's current-answer guard rejects a newer user message. After a
  // click, that newer message can be this very correction and must be checked
  // as acknowledgment before treating it as unrelated navigation or editing.
  const result = await h.finish(h.installed.sendCorrection(correction, () => h.users().length === 1));
  assert.equal(result.ok, true);
  assert.equal(h.users().at(-1).textContent, correction);
  assert.equal(h.clicks.length, 1);
});

for (const provider of ["claude", "gemini"]) test(`${provider} acceptance is observable through that host's user-message nodes`, async () => {
  const h = harness({provider, accepted: true, acknowledgeDelay: 300});
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, true);
  assert.equal(h.users().at(-1).textContent, correction);
  assert.equal(h.clicks.length, 1);
});

test("a matching correction already present in history is not acknowledgment of a new send", async () => {
  const h = harness({priorCorrection: true});
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, false);
  assert.equal(h.users().length, 1);
});

test("a different user message starting generation cannot acknowledge the ignored correction", async () => {
  const h = harness({accepted: true, acknowledgeDelay: 300, emitGeneration: true, acceptedText: "Una nuova domanda personale"});
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, false);
  assert.equal(h.users().at(-1).textContent, "Una nuova domanda personale");
  assert.equal(h.clicks.length, 1);
});

test("clearing a composer without a submitted message or new generation is not acknowledgment", async () => {
  const h = harness({clearOnly: true});
  const result = await h.finish(h.installed.sendCorrection(correction));
  assert.equal(result.ok, false);
  assert.equal(h.users().length, 1);
});

test("a user draft changed while waiting for the button is preserved", async () => {
  const h = harness({buttonDelay: 600, accepted: true});
  const result = await h.finish(h.installed.sendCorrection(correction), elapsed => {if (elapsed >= 300) h.editor.value = "La mia nuova bozza";});
  assert.equal(result.ok, false);
  assert.equal(h.editor.value, "La mia nuova bozza");
  assert.equal(h.clicks.length, 0);
});

"use strict";

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const {createHash} = require("node:crypto");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const manifest = JSON.parse(readFileSync(path.join(__dirname, "manifest.json"), "utf8"));
const ID = "nfnnmjcbjidblifbdfkhbdiidgcjbiem";
const TOKEN = "test-only-token-not-a-real-secret-123456";
const chat = {id: ID, url: "https://chatgpt.com/c/chat-123", frameId: 0, tab: {id: 1}};
const options = {id: ID, url: `chrome-extension://${ID}/options.html`};
const payload = {id: "message-123", chatId: "chat-123", text: "Example assertion", links: ["https://merchant.example/product"]};

function harness(fetcher, settings = {}) {
  const storage = {...(settings.storage || {})};
  const requests = [];
  const broadcasts = [];
  let handler;
  let access;
  const runtimeId = settings.firefox ? "factttl-local@factttl.dev" : ID;
  const origin = settings.firefox ? "moz-extension://11111111-2222-4333-8444-555555555555" : `chrome-extension://${ID}`;
  const chatSender = {...chat, id: runtimeId};
  const optionsSender = {id: runtimeId, url: origin + "/options.html"};
  const jobs = new Map();
  if (!fetcher) fetcher = async (url, init) => {
    if (url.endsWith("/health")) return new Response(JSON.stringify({status: "ready"}));
    if (url.endsWith("/jobs")) {
      const id = JSON.parse(init.body).id;
      const jobId = "j".repeat(23) + (jobs.size + 1);
      jobs.set(jobId, id);
      return new Response(JSON.stringify({id, job_id: jobId, status: "PENDING"}), {status: 202});
    }
    const jobId = url.split("/")[4];
    return new Response(JSON.stringify({id: jobs.get(jobId), status: url.endsWith("/cancel") ? "CANCELED" : "SUPPORTED"}));
  };
  const chrome = {
    runtime: {
      id: runtimeId,
      getURL: suffix => `${origin}/${suffix}`,
      openOptionsPage: async () => {},
      onMessage: {addListener: fn => { handler = fn; }},
    },
    action: {onClicked: {addListener: () => {}}},
    tabs: {
      ...(settings.merchant ? {create: async value => {broadcasts.push({created: value}); return {id: 99};}, remove: async id => broadcasts.push({removed: id})} : {}),
      sendMessage: async (tabId, message) => message.type === "READ_PRODUCT_OFFER" && settings.merchant ? settings.merchant : broadcasts.push({tabId, message}),
    },
    storage: {local: {
      setAccessLevel: async value => { access = settings.firefox ? value : value.accessLevel; },
      get: async key => ({[key]: storage[key]}),
      set: async value => Object.assign(storage, value),
      remove: async key => { delete storage[key]; },
    }},
  };
  if (settings.noAccessLevel) delete chrome.storage.local.setAccessLevel;
  const context = vm.createContext({
    chrome,
    ...(settings.firefox ? {browser: chrome} : {}),
    ...(settings.indexedDB ? {indexedDB: settings.indexedDB} : {}),
    ...(settings.locale ? {navigator: {language: settings.locale}} : {}),
    URL, URLSearchParams, AbortController, DOMException, clearTimeout, TextDecoder, Uint8Array,
    setTimeout: (fn, delay) => setTimeout(fn, delay < 5000 ? Math.min(delay, 5) : delay),
    fetch: async (url, init) => { requests.push({url, init}); return fetcher(url, init); },
  });
  vm.runInContext(readFileSync(path.join(__dirname, "background.js"), "utf8"), context);
  return {
    storage, requests, broadcasts, chatSender, optionsSender, origin,
    access: () => access,
    send: (message, sender = chatSender) => new Promise(resolve => handler(message, sender, resolve)),
  };
}

async function ready(h) {
  await h.send({type: "SET_TOKEN", payload: {token: TOKEN}}, h.optionsSender);
  await h.send({type: "SET_CHAT_STATE", payload: {chatId: payload.chatId, enabled: true}});
}

test("browser offer is read in an inactive owned tab and accompanies only the requested product", async () => {
  const offer = {url: "https://www.amazon.it/dp/B0DKF9NCN1", asin: "B0DKF9NCN1", status: "OBSERVED", source: "browser_rendered_amazon", scope: "browser_current_offer", observed_at: new Date().toISOString(), title: "ESP32", availability: "available", price: "10.99", currency: "EUR", list_price: null};
  const h = harness(null, {merchant: offer}); await ready(h);
  const result = await h.send({type: "VERIFY_MESSAGE", payload: {...payload, links: [offer.url]}});
  assert.equal(result.ok, true);
  const request = h.requests.find(value => value.url.endsWith("/jobs"));
  assert.equal(JSON.parse(request.init.body).browser_observations[0].price, "10.99");
  assert.equal(h.broadcasts.find(value => value.created).created.active, false);
  assert.equal(h.broadcasts.find(value => value.removed).removed, 99);
});

test("memory context requires an enabled trusted chat and stays on the authenticated loopback bridge", async () => {
  const h = harness(async () => new Response(JSON.stringify({findings: []}))); await ready(h);
  const result = await h.send({type: "GET_MEMORY_CONTEXT", payload: {chatId: payload.chatId, query: "ESP32 prezzo"}});
  assert.equal(result.ok, true);
  const request = h.requests[0]; assert.equal(request.url, "http://127.0.0.1:8765/context");
  assert.equal(JSON.parse(request.init.body).query, "ESP32 prezzo");
  assert.equal(request.init.headers.Authorization, `Bearer ${TOKEN}`);
  await h.send({type: "SET_CHAT_STATE", payload: {chatId: payload.chatId, enabled: false}});
  const blocked = await h.send({type: "GET_MEMORY_CONTEXT", payload: {chatId: payload.chatId, query: "ESP32"}});
  assert.equal(blocked.ok, false); assert.equal(h.requests.length, 1);
});

test("manifest has a stable extension origin and minimal access", () => {
  const hex = createHash("sha256").update(Buffer.from(manifest.key, "base64")).digest("hex").slice(0, 32);
  assert.equal([...hex].map(c => String.fromCharCode(97 + parseInt(c, 16))).join(""), ID);
  assert.deepEqual(manifest.permissions, ["storage"]);
  assert.equal(manifest.host_permissions[0], "http://127.0.0.1:8765/*");
  assert.equal(manifest.host_permissions.length, 13);
  for (const value of manifest.host_permissions.slice(1)) assert.match(value, /^https:\/\/(?:www\.)?amazon\.(?:it|com|co\.uk|de|fr|es)\/\*$/);
  assert.equal(manifest.content_scripts[1].js[0], "merchant.js");
  assert.deepEqual(manifest.content_scripts[0].matches, [
    "https://chatgpt.com/*",
    "https://chat.openai.com/*",
    "https://claude.ai/*",
    "https://www.claude.ai/*",
    "https://gemini.google.com/*",
  ]);
});

function fakePrivateDatabase() {
  const secrets = new Map();
  return {
    open() {
      const openRequest = {};
      queueMicrotask(() => {
        openRequest.result = {
          createObjectStore() {},
          close() {},
          transaction() {
            const transaction = {};
            transaction.objectStore = () => ({
              get(key) {
                const request = {result: secrets.get(key)};
                queueMicrotask(() => transaction.oncomplete());
                return request;
              },
              put(value, key) {
                secrets.set(key, value);
                const request = {};
                queueMicrotask(() => transaction.oncomplete());
                return request;
              },
            });
            return transaction;
          },
        };
        openRequest.onupgradeneeded();
        openRequest.onsuccess();
      });
      return openRequest;
    },
  };
}

test("Firefox uses promise namespace, string access level, and exact moz-extension origin", async () => {
  const h = harness(undefined, {firefox: true});
  await ready(h);
  const result = await h.send({type: "VERIFY_MESSAGE", payload});
  assert.equal(result.ok, true);
  assert.equal(h.access(), "TRUSTED_CONTEXTS");
  assert.equal(h.requests[0].init.headers["X-FactTTL-Origin"], h.origin);
  assert.equal(manifest.browser_specific_settings.gecko.id, "factttl-local@factttl.dev");
  assert.deepEqual(manifest.background.scripts, ["background.js"]);
});

test("Firefox without access-level API persists token privately across background restarts", async () => {
  const indexedDB = fakePrivateDatabase();
  const settings = {firefox: true, noAccessLevel: true, indexedDB};
  const first = harness(undefined, settings);
  await ready(first);
  assert.equal(first.storage.bridgeToken, undefined);
  assert.equal((await first.send({type: "GET_HEALTH"}, first.optionsSender)).ok, true);
  const resumed = harness(undefined, settings);
  assert.equal((await resumed.send({type: "GET_HEALTH"}, resumed.optionsSender)).ok, true);
  assert.equal(resumed.storage.bridgeToken, undefined);
  assert.equal(resumed.requests[0].init.headers.Authorization, "Bearer " + TOKEN);
});

test("storage is private, chats start disabled, and disabled chats never fetch", async () => {
  const h = harness();
  await h.send({type: "SET_TOKEN", payload: {token: TOKEN}}, options);
  const state = await h.send({type: "GET_CHAT_STATE", payload: {chatId: payload.chatId}});
  assert.equal(h.access(), "TRUSTED_CONTEXTS");
  assert.equal(state.enabled, false);
  assert.equal((await h.send({type: "VERIFY_MESSAGE", payload})).error, "DISABLED");
  assert.equal((await h.send({type: "GET_HEALTH", payload: {chatId: payload.chatId}})).error, "DISABLED");
  assert.equal(h.requests.length, 0);
});

test("only options may set token and responses do not expose it", async () => {
  const h = harness();
  assert.equal((await h.send({type: "SET_TOKEN", payload: {token: TOKEN}})).error, "FORBIDDEN");
  const result = await h.send({type: "SET_TOKEN", payload: {token: TOKEN}}, options);
  assert.equal(result.ok, true);
  assert.equal(JSON.stringify(result).includes(TOKEN), false);
  assert.equal(h.storage.bridgeToken, TOKEN);
});

test("enabled request uses fixed bridge, bearer and exact extension origin", async () => {
  const h = harness();
  await ready(h);
  const result = await h.send({type: "VERIFY_MESSAGE", payload});
  assert.equal(result.ok, true);
  assert.equal(result.id, payload.id);
  assert.equal(result.chatId, payload.chatId);
  const request = h.requests[0];
  assert.equal(request.url, "http://127.0.0.1:8765/jobs");
  assert.equal(request.init.headers.Authorization, "Bearer " + TOKEN);
  assert.equal(request.init.headers["X-FactTTL-Origin"], `chrome-extension://${ID}`);
  assert.equal(request.init.credentials, "omit");
  assert.equal(request.init.redirect, "error");
  assert.equal(JSON.parse(request.init.body).chatId, payload.chatId);
  assert.equal(JSON.stringify(result).includes(TOKEN), false);
});

test("health can be explicitly tested in options without an enabled chat", async () => {
  const h = harness();
  await h.send({type: "SET_TOKEN", payload: {token: TOKEN}}, options);
  assert.equal((await h.send({type: "GET_HEALTH"}, options)).ok, true);
  assert.equal(h.requests[0].url, "http://127.0.0.1:8765/health");
});

test("foreign pages and iframes cannot use background transport", async () => {
  const h = harness();
  await ready(h);
  for (const sender of [
    {...chat, url: "https://evil.example"}, {...chat, id: "other-extension"}, {...chat, frameId: 2},
  ]) {
    assert.equal((await h.send({type: "VERIFY_MESSAGE", payload}, sender)).error, "FORBIDDEN");
  }
  assert.equal(h.requests.length, 0);
});

test("ChatGPT, Claude, and Gemini conversation pages can use background transport", async () => {
  const h = harness();
  await ready(h);
  for (const url of [
    "https://chatgpt.com/c/chat-123",
    "https://claude.ai/chat/uuid-1",
    "https://gemini.google.com/app/xyz",
  ]) {
    const result = await h.send({type: "GET_CHAT_STATE", payload: {chatId: payload.chatId}}, {...chat, url});
    assert.equal(result.ok, true);
  }
});

test("oversized text, too many links and unsafe links never fetch", async () => {
  const h = harness();
  await ready(h);
  for (const invalid of [
    {...payload, text: "x".repeat(20001)},
    {...payload, links: Array(21).fill("https://example.com")},
    {...payload, links: ["http://example.com"]},
    {...payload, links: ["https://user:password@example.com"]},
    {...payload, links: ["https://example.com:9000/"]},
  ]) assert.equal((await h.send({type: "VERIFY_MESSAGE", payload: invalid})).error, "INVALID_PAYLOAD");
  assert.equal(h.requests.length, 0);
});

test("disabling chat aborts verification and does not return a verdict", async () => {
  let started;
  const begin = new Promise(resolve => { started = resolve; });
  const h = harness(async (url, init) => {
    if (url.endsWith("/jobs")) return new Response(JSON.stringify({id: payload.id, job_id: "j".repeat(24), status: "PENDING"}), {status: 202});
    if (url.endsWith("/cancel")) return new Response(JSON.stringify({id: payload.id, status: "CANCELED"}));
    return new Promise((resolve, reject) => {
      started();
      init.signal.addEventListener("abort", () => reject(new DOMException("Stopped", "AbortError")));
    });
  });
  await ready(h);
  const pending = h.send({type: "VERIFY_MESSAGE", payload});
  await begin;
  await h.send({type: "SET_CHAT_STATE", payload: {chatId: payload.chatId, enabled: false}});
  const result = await pending;
  assert.equal(result.ok, false);
  assert.equal(result.error, "CANCELLED");
  assert.equal(result.result, undefined);
  assert.equal(h.requests.at(-1).url.endsWith("/cancel"), true);
});

test("CANCEL_CHAT aborts only requests from the sender tab", async () => {
  let count = 0;
  let started;
  const begin = new Promise(resolve => { started = resolve; });
  const polls = [];
  const h = harness(async (url, init) => {
    if (url.endsWith("/jobs")) {
      const id = JSON.parse(init.body).id;
      return new Response(JSON.stringify({id, job_id: id === payload.id ? "j".repeat(24) : "k".repeat(24), status: "PENDING"}), {status: 202});
    }
    if (url.endsWith("/cancel")) return new Response(JSON.stringify({status: "CANCELED"}));
    return new Promise((resolve, reject) => {
      polls.push(init);
      count += 1;
      if (count === 2) started();
      init.signal.addEventListener("abort", () => reject(new DOMException("Stopped", "AbortError")));
    });
  });
  await ready(h);
  const first = h.send({type: "VERIFY_MESSAGE", payload});
  const otherSender = {...chat, tab: {id: 2}};
  const second = h.send({type: "VERIFY_MESSAGE", payload: {...payload, id: "message-other"}}, otherSender);
  await begin;
  await h.send({type: "CANCEL_CHAT", payload: {chatId: payload.chatId}});
  assert.equal((await first).error, "CANCELLED");
  assert.equal(polls[1].signal.aborted, false);
  await h.send({type: "CANCEL_CHAT", payload: {chatId: payload.chatId}}, otherSender);
  assert.equal((await second).error, "CANCELLED");
});

test("toggle updates other registered tabs without exposing token", async () => {
  const h = harness();
  await ready(h);
  await h.send({type: "GET_CHAT_STATE", payload: {chatId: payload.chatId}}, {...chat, tab: {id: 2}});
  await h.send({type: "SET_CHAT_STATE", payload: {chatId: payload.chatId, enabled: false}});
  assert.equal(h.broadcasts[0].tabId, 2);
  assert.equal(h.broadcasts[0].message.enabled, false);
  assert.equal(JSON.stringify(h.broadcasts).includes(TOKEN), false);
});

test("wrong token and oversized bridge replies fail safely", async () => {
  const unauthorized = harness(async () => new Response("{}", {status: 401}));
  await ready(unauthorized);
  assert.equal((await unauthorized.send({type: "VERIFY_MESSAGE", payload})).error, "UNAUTHORIZED");
  const oversized = harness(async () => new Response("x".repeat(1048577)));
  await ready(oversized);
  assert.equal((await oversized.send({type: "VERIFY_MESSAGE", payload})).ok, false);
});

test("pending job is polled before returning a completed verdict", async () => {
  let polls = 0;
  const jobId = "j".repeat(24);
  const h = harness(async (url, init) => {
    if (url.endsWith("/jobs")) return new Response(JSON.stringify({id: payload.id, job_id: jobId, status: "PENDING"}), {status: 202});
    polls += 1;
    return new Response(JSON.stringify({
      id: payload.id, job_id: jobId, status: polls === 1 ? "PENDING" : "CONTRADICTED",
    }), {status: polls === 1 ? 202 : 200});
  });
  await ready(h);
  const response = await h.send({type: "VERIFY_MESSAGE", payload});
  assert.equal(response.result.status, "CONTRADICTED");
  assert.equal(polls, 2);
  assert.equal(h.requests.every(r => r.url !== "http://127.0.0.1:8765/verify"), true);
});

test("malformed job ID never becomes a request path", async () => {
  const h = harness(async () => new Response(JSON.stringify({
    id: payload.id, job_id: "../../arbitrary-path", status: "PENDING",
  }), {status: 202}));
  await ready(h);
  assert.equal((await h.send({type: "VERIFY_MESSAGE", payload})).ok, false);
  assert.equal(h.requests.length, 1);
});

test("disabling during job creation still cancels the newly created job", async () => {
  let created;
  let started;
  const creation = new Promise(resolve => { created = resolve; });
  const begin = new Promise(resolve => { started = resolve; });
  const jobId = "j".repeat(24);
  const h = harness(async (url, init) => {
    if (url.endsWith("/jobs")) {
      started();
      return creation;
    }
    assert.equal(url.endsWith("/cancel"), true);
    return new Response(JSON.stringify({id: payload.id, job_id: jobId, status: "CANCELED"}));
  });
  await ready(h);
  const verification = h.send({type: "VERIFY_MESSAGE", payload});
  await begin;
  await h.send({type: "SET_CHAT_STATE", payload: {chatId: payload.chatId, enabled: false}});
  assert.equal(h.requests[0].init.signal.aborted, false);
  created(new Response(JSON.stringify({id: payload.id, job_id: jobId, status: "PENDING"}), {status: 202}));
  const response = await verification;
  assert.equal(response.error, "CANCELLED");
  assert.equal(h.requests.length, 2);
  assert.equal(h.requests[1].url, `http://127.0.0.1:8765/jobs/${jobId}/cancel`);
});

test("country and language start from browser locale without geolocation calls", async () => {
  const h = harness(undefined, {locale: "de-DE"});
  const response = await h.send({type: "GET_PREFERENCES"});
  assert.equal(response.ok, true);
  assert.equal(response.preferences.country, "DE");
  assert.equal(response.preferences.language, "de");
  assert.equal(h.requests.length, 0);
});

test("only options can update valid preferences and they persist", async () => {
  const h = harness();
  const next = {country: "FR", language: "fr"};
  const message = {type: "SET_PREFERENCES", payload: {preferences: next}};
  assert.equal((await h.send(message)).error, "FORBIDDEN");
  const saved = await h.send(message, h.optionsSender);
  assert.equal(saved.ok, true);
  assert.equal(h.storage.factttlPreferences.country, "FR");
  const resumed = harness(undefined, {storage: h.storage});
  const read = await resumed.send({type: "GET_PREFERENCES"});
  assert.equal(read.preferences.country, "FR");
  assert.equal(read.preferences.language, "fr");
  assert.equal(h.requests.length, 0);
});

test("unsupported and header-injection preferences are rejected", async () => {
  const h = harness();
  for (const preferences of [
    {country: "XX", language: "it"}, {country: "IT", language: "xx"},
    {country: "IT", language: "it\r\nAuthorization: bad"},
    {country: "IT", language: "it", endpoint: "https://evil.example"},
  ]) {
    const response = await h.send({type: "SET_PREFERENCES", payload: {preferences}}, h.optionsSender);
    assert.equal(response.error, "INVALID_PREFERENCES");
  }
  assert.equal(h.storage.factttlPreferences, undefined);
});

test("job preferences and language header come from privileged settings, not content", async () => {
  const h = harness();
  await ready(h);
  await h.send({type: "SET_PREFERENCES", payload: {preferences: {country: "ES", language: "es"}}}, h.optionsSender);
  const supplied = {...payload, preferences: {country: "US", language: "en"}};
  assert.equal((await h.send({type: "VERIFY_MESSAGE", payload: supplied})).ok, true);
  const request = h.requests[0];
  assert.equal(JSON.parse(request.init.body).preferences.country, "ES");
  assert.equal(JSON.parse(request.init.body).preferences.language, "es");
  assert.equal(request.init.headers["Accept-Language"], "es-ES,es;q=0.9");
  assert.equal(manifest.permissions.includes("geolocation"), false);
});

test("flat options preferences broadcast invalidation to registered content tabs", async () => {
  const h = harness();
  await ready(h);
  const response = await h.send({type: "SET_PREFERENCES", payload: {country: "US", language: "en"}}, h.optionsSender);
  assert.equal(response.ok, true);
  assert.equal(h.broadcasts[0].message.type, "PREFERENCES_CHANGED");
  assert.equal(h.broadcasts[0].message.preferences.country, "US");
  assert.equal(JSON.stringify(h.broadcasts).includes(TOKEN), false);
});

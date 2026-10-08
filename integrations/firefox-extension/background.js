/* The bridge token is accessible only to trusted extension contexts. */
"use strict";
if (typeof importScripts === "function" && typeof FactTTLAmazonURL === "undefined") importScripts("amazon-url.js");
const amazonURL = typeof FactTTLAmazonURL !== "undefined" ? FactTTLAmazonURL : null;

const extensionAPI = typeof browser !== "undefined" ? browser : chrome;
const isFirefox = extensionAPI.runtime.getURL("").startsWith("moz-extension://");
let privateLocalStorage = false;
const COUNTRIES = new Set(["IT", "US", "GB", "DE", "FR", "ES"]);
const LANGUAGES = new Set(["it", "en", "de", "fr", "es"]);
let preferences = localePreferences();

const BRIDGE = "http://127.0.0.1:8765";
const AMAZON_HOSTS = new Set(["amazon.it", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es"]);
const merchantCache = new Map();
function merchantKey(value) {
  try {
    const resolved = amazonURL?.resolveAmazonProductURL(value);
    const url = new URL(resolved || value);
    const host = url.hostname.replace(/^www\./, "");
    const asin = url.pathname.match(/\/(?:dp|gp\/product|gp\/aw\/d)\/([A-Z0-9]{10})(?:[/.]|$)/i)?.[1]?.toUpperCase();
    if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443") || !AMAZON_HOSTS.has(host) || !asin) return null;
    // Variant/seller query parameters retain their scope; no different offer reuse.
    const tracking = new Set(["ref", "ref_", "tag", "linkcode", "creative", "creativeasin", "camp", "ascsubtag"]);
    const parameters = [...url.searchParams].filter(([name]) => !tracking.has(name.toLowerCase())).sort(([a, x], [b, y]) => a.localeCompare(b) || x.localeCompare(y));
    return `${host}/${asin}?${new URLSearchParams(parameters)}`;
  } catch { return null; }
}
let merchantBusy = false;
async function observeMerchant(url, signal) {
  const key = merchantKey(url);
  if (!key || typeof extensionAPI.tabs.create !== "function") return null;
  const cached = merchantCache.get(key);
  if (cached && Date.now() - cached.time < 60000) return {...cached.value};
  let tab;
  try {
    if (signal.aborted) throw aborted();
    tab = await extensionAPI.tabs.create({url: amazonURL?.resolveAmazonProductURL(url) || url, active: false});
    const deadline = Date.now() + 22000;
    while (Date.now() < deadline) {
      if (signal.aborted) throw aborted();
      try {
        const value = await extensionAPI.tabs.sendMessage(tab.id, {type: "READ_PRODUCT_OFFER"});
        if (value && merchantKey(value.url) === key && value.source === "browser_rendered_amazon" && ["OBSERVED", "BLOCKED"].includes(value.status)) {
          if (value.status === "OBSERVED") {
            if (merchantCache.size >= 32) merchantCache.delete(merchantCache.keys().next().value);
            merchantCache.set(key, {time: Date.now(), value});
          }
          return value;
        }
      } catch { /* Page/content script may still be loading; never solve a challenge. */ }
      await pause(500, signal);
    }
    return null;
  } finally {
    if (tab?.id !== undefined) await extensionAPI.tabs.remove(tab.id).catch(() => {});
  }
}
async function merchantObservations(request, signal) {
  const urls = [...new Map(request.links.filter(merchantKey).map(url => [merchantKey(url), url])).values()].slice(0, 2);
  const until = Date.now() + 5000;
  while (merchantBusy && Date.now() < until) await pause(200, signal);
  if (signal.aborted) throw aborted();
  if (merchantBusy || !urls.length) return [];
  merchantBusy = true;
  try {
    const values = [];
    for (const url of urls) {
      if (signal.aborted) throw aborted();
      const value = await observeMerchant(url, signal);
      if (value) values.push(value);
    }
    return values;
  } finally {merchantBusy = false;}
}
const active = new Map();
const epochs = new Map();
const chats = new Map();
const knownTabs = new Map();
const correctionLedger = new Map();
const correctionBudget = new Map();
const correctionModes = new Map();
let persistQueue = Promise.resolve();

const initialized = (async () => {
  if (typeof extensionAPI.storage.local.setAccessLevel === "function") {
    try {
      await extensionAPI.storage.local.setAccessLevel(
        isFirefox ? "TRUSTED_CONTEXTS" : {accessLevel: "TRUSTED_CONTEXTS"}
      );
      privateLocalStorage = true;
    } catch { /* Older Firefox uses extension-origin IndexedDB for secrets. */ }
  }
  if (!privateLocalStorage) await extensionAPI.storage.local.remove("bridgeToken");
  const stored = await extensionAPI.storage.local.get("factttlChats");
  if (stored.factttlChats && typeof stored.factttlChats === "object") {
    for (const [id, enabled] of Object.entries(stored.factttlChats).slice(-1000)) {
      if (validId(id) && typeof enabled === "boolean") chats.set(id, enabled);
    }
  }
  const storedPreferences = await extensionAPI.storage.local.get("factttlPreferences");
  const corrections = await extensionAPI.storage.local.get("factttlCorrections");
  for (const [key, value] of Object.entries(corrections.factttlCorrections?.modes || {}).slice(-1000)) {
    if (validId(key) && typeof value === "boolean") correctionModes.set(key, value);
  }
  for (const [key, value] of Object.entries(corrections.factttlCorrections?.ledger || {}).slice(-200)) {
    if (typeof value === "string") correctionLedger.set(key, value);
  }
  for (const [key, value] of Object.entries(corrections.factttlCorrections?.budget || {}).slice(-1000)) {
    if (validId(key) && Number.isInteger(value) && value >= 0 && value <= 2) correctionBudget.set(key, value);
  }
  try { preferences = validatePreferences(storedPreferences.factttlPreferences); }
  catch { /* Browser locale is an editable hint, never geolocation evidence. */ }
})();

function localePreferences() {
  const locale = typeof navigator !== "undefined" ? navigator.language : "it-IT";
  const parts = typeof locale === "string" ? locale.split("-") : [];
  const language = (parts[0] || "it").toLowerCase();
  const country = (parts.find(part => /^[A-Za-z]{2}$/.test(part) && part !== parts[0]) || "IT").toUpperCase();
  return {
    country: COUNTRIES.has(country) ? country : "IT",
    language: LANGUAGES.has(language) ? language : "it",
  };
}

function validatePreferences(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).some(key => key !== "country" && key !== "language") ||
      typeof value.country !== "string" || typeof value.language !== "string") {
    throw new Error("INVALID_PREFERENCES");
  }
  const country = value.country.trim().toUpperCase();
  const language = value.language.trim().toLowerCase();
  if (!COUNTRIES.has(country) || !LANGUAGES.has(language)) throw new Error("INVALID_PREFERENCES");
  return {country, language};
}

async function tokenDatabase(writeToken) {
  const database = await new Promise((resolve, reject) => {
    const request = indexedDB.open("factttl-private", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("secrets");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("PRIVATE_STORAGE_ERROR"));
  });
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction("secrets", writeToken === undefined ? "readonly" : "readwrite");
      const request = writeToken === undefined
        ? transaction.objectStore("secrets").get("bridgeToken")
        : transaction.objectStore("secrets").put(writeToken, "bridgeToken");
      transaction.oncomplete = () => resolve(writeToken === undefined ? request.result : undefined);
      transaction.onerror = transaction.onabort = () => reject(new Error("PRIVATE_STORAGE_ERROR"));
    });
  } finally { database.close(); }
}

async function saveToken(token) {
  if (privateLocalStorage) await extensionAPI.storage.local.set({bridgeToken: token});
  else await tokenDatabase(token);
}

async function readToken() {
  if (privateLocalStorage) return (await extensionAPI.storage.local.get("bridgeToken")).bridgeToken;
  return tokenDatabase();
}

function validId(value) {
  return typeof value === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
}

function optionsSender(sender) {
  return sender.id === extensionAPI.runtime.id && sender.url === extensionAPI.runtime.getURL("options.html");
}

const CHAT_ORIGINS = new Set([
  "https://chatgpt.com",
  "https://chat.openai.com",
  "https://claude.ai",
  "https://www.claude.ai",
  "https://gemini.google.com",
]);

function chatSender(sender) {
  if (sender.id !== extensionAPI.runtime.id || !sender.tab || !sender.url) return false;
  try {
    const url = new URL(sender.url);
    return CHAT_ORIGINS.has(url.origin) && sender.frameId === 0;
  } catch {
    return false;
  }
}

function fail(error, message, payload = {}) {
  return {ok: false, id: payload.id, chatId: payload.chatId, error, message};
}

function validatePayload(payload) {
  if (!payload || !validId(payload.id) || !validId(payload.chatId) ||
      typeof payload.text !== "string" || !payload.text.trim() ||
      payload.text.length > 20000 || !Array.isArray(payload.links) || payload.links.length > 20) {
    throw new Error("INVALID_PAYLOAD");
  }
  const links = payload.links.map(value => {
    if (typeof value !== "string" || value.length > 4096) throw new Error("INVALID_PAYLOAD");
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password ||
        (url.port && url.port !== "443")) throw new Error("INVALID_PAYLOAD");
    return value;
  });
  return {
    id: payload.id, chatId: payload.chatId, text: payload.text,
    links: [...new Set(links)], preferences: {...preferences},
  };
}

function cancelChat(chatId, tabId) {
  if (tabId === undefined) epochs.set(chatId, (epochs.get(chatId) || 0) + 1);
  for (const request of active.values()) {
    if (request.chatId === chatId && (tabId === undefined || request.tabId === tabId)) request.controller.abort();
  }
}

async function bridgeRequest(path, token, controller, payload, timeout = 10000) {
  // Every response arrives promptly; long verification work runs as a server job.
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(BRIDGE + path, {
      method: payload ? "POST" : "GET",
      headers: {
        Authorization: "Bearer " + token,
        "X-FactTTL-Origin": extensionAPI.runtime.getURL("").replace(/\/$/, ""),
        "Accept-Language": `${preferences.language}-${preferences.country},${preferences.language};q=0.9`,
        ...(payload ? {"Content-Type": "application/json"} : {}),
      },
      body: payload ? JSON.stringify(payload) : undefined,
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      signal: controller.signal,
    });
    if (response.status === 401 || response.status === 403) throw new Error("UNAUTHORIZED");
    if (!response.ok) throw new Error("BRIDGE_ERROR");
    const reader = response.body.getReader();
    const chunks = [];
    let bytes = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > 1048576) {
        await reader.cancel();
        throw new Error("BRIDGE_ERROR");
      }
      chunks.push(value);
    }
    const body = new Uint8Array(bytes);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    const result = JSON.parse(new TextDecoder().decode(body));
    if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("BRIDGE_ERROR");
    return result;
  } finally {
    clearTimeout(timer);
  }
}

function aborted() {
  return new DOMException("Verification canceled", "AbortError");
}

function pause(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(aborted()); return; }
    const cancel = () => { clearTimeout(timer); reject(aborted()); };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", cancel);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", cancel, {once: true});
  });
}

async function verificationJob(token, controller, request, activeRequest) {
    const expiry = setTimeout(() => controller.abort(), 180000);
  let jobId;
  let finished = false;
  try {
    // Complete the short creation response even when disabled during creation,
    // so the newly allocated job ID remains available for cooperative cancel.
    const created = await bridgeRequest("/jobs", token, new AbortController(), request);
    if (created.id !== request.id || typeof created.job_id !== "string" ||
        !/^[A-Za-z0-9_-]{24}$/.test(created.job_id) || created.status !== "PENDING") {
      throw new Error("BRIDGE_ERROR");
    }
    jobId = created.job_id;
    activeRequest.jobId = jobId;
    let delay = 750;
    while (true) {
      if (controller.signal.aborted) throw aborted();
      await pause(delay, controller.signal);
      const result = await bridgeRequest("/jobs/" + jobId, token, controller);
      if (result.id !== request.id) throw new Error("BRIDGE_ERROR");
      if (result.status === "CANCELED") throw aborted();
      if (result.status !== "PENDING") {
        finished = true;
        return result;
      }
      if (result.job_id !== jobId) throw new Error("BRIDGE_ERROR");
      delay = Math.min(2000, delay * 1.35);
    }
  } finally {
    clearTimeout(expiry);
    if (jobId && !finished) {
      // An already-running source fetch may finish, but the server cancels
      // subsequent work and avoids persisting checks completed after cancellation.
      await bridgeRequest("/jobs/" + jobId + "/cancel", token, new AbortController(), {}, 3000).catch(() => {});
    }
  }
}

async function handle(message, sender) {
  await initialized;
  if (!message || typeof message.type !== "string") return fail("INVALID_MESSAGE", "Richiesta non valida.");
  const isOptions = optionsSender(sender);
  const isChat = chatSender(sender);
  if (!isOptions && !isChat) return fail("FORBIDDEN", "Origine non consentita.");
  const payload = message.payload || {};

  if (message.type === "GET_PREFERENCES") return {ok: true, preferences: {...preferences}};
  if (message.type === "SET_PREFERENCES") {
    if (!isOptions) return fail("FORBIDDEN", "Modifica paese e lingua nelle impostazioni dell'estensione.");
    let next;
    try { next = validatePreferences(payload.preferences || payload); }
    catch { return fail("INVALID_PREFERENCES", "Paese o lingua non supportati."); }
    await extensionAPI.storage.local.set({factttlPreferences: next});
    const changed = next.country !== preferences.country || next.language !== preferences.language;
    preferences = next;
    if (changed) {
      for (const request of active.values()) request.controller.abort();
      for (const tabId of knownTabs.keys()) {
        extensionAPI.tabs.sendMessage(tabId, {
          type: "PREFERENCES_CHANGED", preferences: {...preferences},
        }).catch(() => knownTabs.delete(tabId));
      }
    }
    return {ok: true, preferences: {...preferences}};
  }

  if (message.type === "SET_TOKEN") {
    if (!isOptions) return fail("FORBIDDEN", "Configura il token nelle impostazioni dell'estensione.");
    if (typeof payload.token !== "string" || !/^[A-Za-z0-9._~-]{16,256}$/.test(payload.token)) {
      return fail("INVALID_TOKEN", "Il token locale non è valido.");
    }
    for (const request of active.values()) request.controller.abort();
    await saveToken(payload.token);
    return {ok: true};
  }
  if (message.type === "OPEN_OPTIONS") {
    await extensionAPI.runtime.openOptionsPage();
    return {ok: true};
  }
  if (message.type === "GET_CHAT_STATE" || message.type === "SET_CHAT_STATE") {
    if (!isChat || !validId(payload.chatId)) return fail("INVALID_PAYLOAD", "Chat non valida.");
    knownTabs.set(sender.tab.id, payload.chatId);
    if (knownTabs.size > 1000) knownTabs.delete(knownTabs.keys().next().value);
    if (message.type === "SET_CHAT_STATE") {
      if (typeof payload.enabled !== "boolean") return fail("INVALID_PAYLOAD", "Stato non valido.");
      chats.set(payload.chatId, payload.enabled);
      if (!payload.enabled) cancelChat(payload.chatId);
      if (chats.size > 1000) chats.delete(chats.keys().next().value);
      persistQueue = persistQueue.catch(() => {}).then(() =>
        extensionAPI.storage.local.set({factttlChats: Object.fromEntries(chats)}));
      await persistQueue;
      for (const [tabId, chatId] of knownTabs) {
        if (chatId === payload.chatId && tabId !== sender.tab.id) {
          extensionAPI.tabs.sendMessage(tabId, {
            type: "CHAT_STATE_CHANGED", chatId, enabled: payload.enabled,
          }).catch(() => knownTabs.delete(tabId));
        }
      }
    }
    return {ok: true, chatId: payload.chatId, enabled: chats.get(payload.chatId) === true, autoCorrection: correctionModes.get(payload.chatId) !== false};
  }
  if (message.type === "CANCEL_CHAT") {
    if (!isChat || !validId(payload.chatId)) return fail("INVALID_PAYLOAD", "Chat non valida.");
    cancelChat(payload.chatId, sender.tab.id);
    return {ok: true, chatId: payload.chatId};
  }

  if (["RESERVE_CORRECTION", "RELEASE_CORRECTION", "RESET_CORRECTION_BUDGET", "SET_CORRECTION_MODE"].includes(message.type)) {
    if (!isChat || !validId(payload.chatId) || chats.get(payload.chatId) !== true) return fail("DISABLED", "Correzione disattivata.");
    if (message.type === "SET_CORRECTION_MODE" && typeof payload.enabled !== "boolean") return fail("INVALID_PAYLOAD", "Stato non valido.");
    if (!["RESET_CORRECTION_BUDGET", "SET_CORRECTION_MODE"].includes(message.type) && (typeof payload.key !== "string" || !/^[a-f0-9]{64}$/.test(payload.key))) return fail("INVALID_PAYLOAD", "Correzione non valida.");
    let result;
    // Serialize reservations across tabs: the same answer can create one send.
    persistQueue = persistQueue.catch(() => {}).then(async () => {
      if (chats.get(payload.chatId) !== true) {result = fail("DISABLED", "Correzione disattivata."); return;}
      const key = `${payload.chatId}:${payload.key}`;
      if (message.type === "SET_CORRECTION_MODE") {
        correctionModes.set(payload.chatId, payload.enabled);
        if (correctionModes.size > 1000) correctionModes.delete(correctionModes.keys().next().value);
        result = {ok: true, autoCorrection: payload.enabled};
      }
      else if (message.type === "RESET_CORRECTION_BUDGET") correctionBudget.set(payload.chatId, 0);
      else if (message.type === "RELEASE_CORRECTION") {
        if (correctionLedger.get(key) === payload.reservation) {correctionLedger.delete(key); correctionBudget.set(payload.chatId, Math.max(0, (correctionBudget.get(payload.chatId) || 0) - 1));}
      } else if (correctionModes.get(payload.chatId) === false) {
        result = fail("DISABLED", "Correzione automatica disattivata."); return;
      } else if (correctionLedger.has(key) || (correctionBudget.get(payload.chatId) || 0) >= 2) {
        result = {ok: true, reserved: false, budget_exhausted: (correctionBudget.get(payload.chatId) || 0) >= 2}; return;
      } else {
        const reservation = `${sender.tab.id}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
        correctionLedger.set(key, reservation); correctionBudget.set(payload.chatId, (correctionBudget.get(payload.chatId) || 0) + 1);
        if (correctionLedger.size > 200) correctionLedger.delete(correctionLedger.keys().next().value);
        if (correctionBudget.size > 1000) correctionBudget.delete(correctionBudget.keys().next().value);
        result = {ok: true, reserved: true, reservation};
      }
      await extensionAPI.storage.local.set({factttlCorrections: {ledger: Object.fromEntries(correctionLedger), budget: Object.fromEntries(correctionBudget), modes: Object.fromEntries(correctionModes)}});
      if (message.type === "SET_CORRECTION_MODE") for (const [tabId, chatId] of knownTabs) {
        if (chatId === payload.chatId && tabId !== sender.tab.id) extensionAPI.tabs.sendMessage(tabId, {type: "CORRECTION_MODE_CHANGED", chatId, enabled: payload.enabled}).catch(() => knownTabs.delete(tabId));
      }
      result ||= {ok: true};
    });
    await persistQueue; return result;
  }

  if (message.type === "GET_HEALTH" && isChat &&
      (!validId(payload.chatId) || chats.get(payload.chatId) !== true)) {
    return fail("DISABLED", "FactTTL è disattivato in questa chat.", payload);
  }

  const token = await readToken();
  if (typeof token !== "string" || !/^[A-Za-z0-9._~-]{16,256}$/.test(token)) {
    return {...fail("NOT_CONFIGURED", "Configura il token locale nelle impostazioni FactTTL.", payload), configured: false};
  }
  if (message.type === "GET_HEALTH") {
    try {
      const status = await bridgeRequest("/health", token, new AbortController());
      return {ok: true, configured: true, status};
    } catch (error) {
      return {...safeError(error, payload), configured: true};
    }
  }

  if (message.type === "GET_MEMORY_CONTEXT") {
    if (!isChat || !validId(payload.chatId) || chats.get(payload.chatId) !== true ||
        typeof payload.query !== "string" || !payload.query.trim() || payload.query.length > 2000 ||
        (payload.urls && (!Array.isArray(payload.urls) || payload.urls.length > 10 || payload.urls.some(url => typeof url !== "string" || url.length > 4096)))) {
      return fail("DISABLED", "Memoria non disponibile per questa chat.", payload);
    }
    try {
      const context = await bridgeRequest("/context", token, new AbortController(), {query: payload.query, urls: payload.urls || [], limit: 6}, 3500);
      if (chats.get(payload.chatId) !== true) return fail("DISABLED", "FactTTL disattivato.");
      return {ok: true, context};
    } catch (error) { return safeError(error, payload); }
  }
  if (message.type !== "VERIFY_MESSAGE" || !isChat) return fail("INVALID_MESSAGE", "Richiesta non consentita.");
  let request;
  try {
    request = validatePayload(payload);
  } catch {
    return fail("INVALID_PAYLOAD", "Risposta o link troppo lunghi oppure non validi.", payload);
  }
  if (chats.get(request.chatId) !== true) return fail("DISABLED", "FactTTL è disattivato in questa chat.", request);
  if (active.size >= 4) return fail("BUSY", "Attendi le verifiche già in corso.", request);
  const key = `${sender.tab.id}:${request.chatId}:${request.id}`;
  active.get(key)?.controller.abort();
  const controller = new AbortController();
  const epoch = epochs.get(request.chatId) || 0;
  const activeRequest = {controller, chatId: request.chatId, tabId: sender.tab.id};
  active.set(key, activeRequest);
  try {
    const observations = await merchantObservations(request, controller.signal);
    if (observations.length) request.browser_observations = observations;
    const result = await verificationJob(token, controller, request, activeRequest);
    if (controller.signal.aborted || chats.get(request.chatId) !== true || (epochs.get(request.chatId) || 0) !== epoch) {
      return fail("CANCELLED", "Verifica annullata.", request);
    }
    return {ok: true, id: request.id, chatId: request.chatId, result};
  } catch (error) {
    return safeError(error, request);
  } finally {
    if (active.get(key)?.controller === controller) active.delete(key);
  }
}

function safeError(error, payload) {
  if (error?.name === "AbortError") return fail("CANCELLED", "Verifica annullata o tempo scaduto.", payload);
  if (error?.message === "UNAUTHORIZED") return fail("UNAUTHORIZED", "Il token locale non corrisponde: aggiornalo nelle impostazioni.", payload);
  return fail("UNAVAILABLE", "Il servizio FactTTL locale non risponde. Avvialo sul PC.", payload);
}

extensionAPI.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handle(message, sender).then(sendResponse, () => sendResponse(
    fail("UNAVAILABLE", "Impossibile avviare FactTTL: ricarica l'estensione.", message?.payload)));
  return true;
});
extensionAPI.action.onClicked.addListener(() => extensionAPI.runtime.openOptionsPage());

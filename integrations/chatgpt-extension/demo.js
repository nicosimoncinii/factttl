/* Local UI fixture only: never included by manifest.json or loaded on ChatGPT. */
"use strict";
history.replaceState(null, "", "/c/factttl-demo");
let demoEnabled = false;
let demoAuto = true;
const demoCorrections = new Set();
const demoResults = fetch("/demo-results").then(r => r.json());
window.chrome = {runtime: {onMessage: {addListener() {}}, async sendMessage(message) {
  if (message.type === "GET_CHAT_STATE") return {ok: true, enabled: demoEnabled, autoCorrection: demoAuto};
  if (message.type === "SET_CHAT_STATE") {demoEnabled = message.payload.enabled; return {ok: true, enabled: demoEnabled};}
  if (message.type === "CANCEL_CHAT") return {ok: true};
  if (message.type === "SET_CORRECTION_MODE") {demoAuto = message.payload.enabled; return {ok: true};}
  if (message.type === "RESET_CORRECTION_BUDGET") return {ok: true};
  if (message.type === "RESERVE_CORRECTION") {if (demoCorrections.has(message.payload.key)) return {ok: true, reserved: false}; demoCorrections.add(message.payload.key); return {ok: true, reserved: true, reservation: message.payload.key};}
  if (message.type === "RELEASE_CORRECTION") {demoCorrections.delete(message.payload.key); return {ok: true};}
  if (message.type === "GET_MEMORY_CONTEXT") {
    const response = await fetch("/context-preview", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({query: message.payload.query, urls: message.payload.urls, limit: 6})});
    return response.ok ? {ok: true, context: await response.json()} : {ok: false};
  }
  if (message.type === "OPEN_OPTIONS") {location.href = "/settings"; return {ok: true};}
  if (message.type === "VERIFY_MESSAGE") {
    const results = await demoResults;
    const result = message.payload.links.some(url => url.includes("ollama.com")) ? results.news : message.payload.links.length ? results.product : results.generic;
    return {ok: true, id: message.payload.id, chatId: message.payload.chatId, result};
  }
  return {ok: false};
}}};
addEventListener("DOMContentLoaded", () => {
  document.querySelector("#demo-send")?.addEventListener("click", () => {
    document.querySelector("#demo-outgoing").textContent = document.querySelector("#prompt-textarea").value;
    document.querySelector("#prompt-textarea").value = "";
  });
});

/* Local UI fixture only: never included by manifest.json or loaded on ChatGPT. */
"use strict";
history.replaceState(null, "", "/c/factttl-demo");
let demoEnabled = false;
const demoResults = fetch("/demo-results").then(r => r.json());
window.chrome = {runtime: {onMessage: {addListener() {}}, async sendMessage(message) {
  if (message.type === "GET_CHAT_STATE") return {ok: true, enabled: demoEnabled};
  if (message.type === "SET_CHAT_STATE") {demoEnabled = message.payload.enabled; return {ok: true, enabled: demoEnabled};}
  if (message.type === "CANCEL_CHAT") return {ok: true};
  if (message.type === "OPEN_OPTIONS") {location.href = "/settings"; return {ok: true};}
  if (message.type === "VERIFY_MESSAGE") {
    const results = await demoResults;
    const result = message.payload.links.some(url => url.includes("ollama.com")) ? results.news : message.payload.links.length ? results.product : results.generic;
    return {ok: true, id: message.payload.id, chatId: message.payload.chatId, result};
  }
  return {ok: false};
}}};

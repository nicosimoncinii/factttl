/* FactTTL reads completed assistant messages only in explicitly enabled chats. */
(() => {
  "use strict";
  const MESSAGE_SELECTOR = [
    '[data-markdown-text-style="assistant-message"]',
    '[data-message-author-role="assistant"] .markdown',
    '[data-testid="assistant-message"]',
    ".font-claude-message",
    ".model-response-text",
    "message-content.model-response-text",
    '[data-message-author-role="model"]',
  ].join(", ");
  const HOST_PAGES = new Set([
    "chatgpt.com", "www.chatgpt.com", "chat.openai.com",
    "claude.ai", "www.claude.ai",
    "gemini.google.com", "bard.google.com",
  ]);
  const BLOCKS = new Set(["P", "LI", "DIV", "SECTION", "BR", "H1", "H2", "H3", "H4", "TR", "PRE"]);
  const LABELS = {SUPPORTED: "Confermato dalla fonte", CONTRADICTED: "Smentito dalla fonte", PARTIAL: "Verifica parziale", INCONCLUSIVE: "Non verificabile", NO_CLAIMS: "Nessun dato verificabile", ERROR: "Controllo non disponibile"};
  const PAGE_ORIGIN = typeof location !== "undefined" && location.origin ? location.origin : "https://chatgpt.com";

  function hostKind(hostname) {
    if (hostname === "claude.ai" || hostname === "www.claude.ai") return "claude";
    if (hostname === "gemini.google.com" || hostname === "bard.google.com") return "gemini";
    return "chatgpt";
  }

  function chatKey(path, hostname) {
    const host = hostname || (typeof location !== "undefined" ? location.hostname : "chatgpt.com");
    const kind = hostKind(host);
    const patterns = {
      chatgpt: /\/c\/([A-Za-z0-9_-]{1,80})/,
      claude: /\/chat\/([A-Za-z0-9_-]{1,80})/,
      gemini: /\/(?:u\/\d+\/)?app\/([A-Za-z0-9_-]{1,80})/,
    };
    const match = path.match(patterns[kind]);
    return match ? `${kind}:${match[1]}`.slice(0, 128) : null;
  }

  function normalizeChecks(entries) {
    return Array.isArray(entries) ? entries.map(entry => entry.result || entry) : [];
  }

  function destinationKey(value) {
    try {
      const url = new URL(value);
      const host = url.hostname.toLowerCase().replace(/^(?:www|smile)\./, "");
      if (new Set(["amazon.it", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es"]).has(host)) {
        const asin = url.pathname.match(/\/(?:dp|gp\/product|gp\/aw\/d)\/([a-z0-9]{10})(?:[/.]|$)/i)?.[1];
        if (asin) {
          const tracking = new Set(["ref", "ref_", "tag", "linkcode", "creative", "creativeasin", "camp", "ascsubtag"]);
          const parameters = [...url.searchParams].filter(([name]) => !tracking.has(name.toLowerCase())).sort(([a, x], [b, y]) => a.localeCompare(b) || x.localeCompare(y));
          const query = new URLSearchParams(parameters).toString();
          return `https://${host}/asin/${asin.toUpperCase()}${query ? `?${query}` : ""}`;
        }
      }
      url.hash = "";
      return url.href;
    } catch { return null; }
  }

  function serializeMessage(root) {
    const links = new Set();
    function walk(node) {
      if (node.nodeType === 3) return node.textContent || "";
      if (node.nodeType !== 1 || node.closest?.(".factttl-ui") || node.matches?.('[hidden], [aria-hidden="true"], script, style')) return "";
      if (node.tagName === "A") {
        const href = node.getAttribute("href");
        let url;
        try { url = new URL(href, PAGE_ORIGIN); } catch { return node.textContent || ""; }
        if (url.protocol === "https:" && !HOST_PAGES.has(url.hostname) && !url.username && !url.password) {
          links.add(url.href);
          return `[${node.textContent || url.href}](${url.href})`;
        }
        return node.textContent || "";
      }
      const text = Array.from(node.childNodes).map(walk).join("");
      // Block boundaries preserve the association between an assertion and its URL.
      return BLOCKS.has(node.tagName) ? `\n${text}\n` : text;
    }
    return {text: walk(root).replace(/\n{3,}/g, "\n\n").trim(), links: [...links]};
  }

  function itemTargets(root) {
    const externalAnchors = [...root.querySelectorAll("a[href]")].filter(node => {
      if (node.closest(".factttl-ui")) return false;
      try {
        const u = new URL(node.href);
        return u.protocol === "https:" && !HOST_PAGES.has(u.hostname) && !u.username && !u.password;
      } catch { return false; }
    });
    const seenDestinations = new Map();
    const anchors = externalAnchors.filter(node => {
      try {
        const u = new URL(node.href);
        // Deduplicate citations only within their assertion block. A second
        // paragraph can make a different claim about the same destination.
        const block = sourceFor(node) || root;
        let destinations = seenDestinations.get(block);
        if (!destinations) { destinations = new Set(); seenDestinations.set(block, destinations); }
        const key = destinationKey(u.href);
        if (!key || destinations.has(key)) return false;
        destinations.add(key);
        return true;
      }
      catch { return false; }
    });
    const paragraphs = [...root.querySelectorAll("p, li")].filter(node =>
      !node.closest(".factttl-ui") && (node.textContent || "").trim().length > 45 &&
      // A duplicate citation still covers its paragraph; do not turn the
      // paragraph into a second generic badge when its link was deduplicated.
      !externalAnchors.some(a => node.contains(a)) && !(node.tagName === "LI" && node.querySelector("p"))
    );
    return [...anchors, ...paragraphs];
  }

  function sourceFor(node) { return node.tagName === "A" ? node.closest("li") || node.closest("p, tr") || node.parentElement : node; }

  const exported = {chatKey, hostKind, serializeMessage, normalizeChecks, destinationKey, itemTargets, sourceFor, LABELS};
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  if (typeof document === "undefined" || (typeof chrome === "undefined" && typeof browser === "undefined")) return;
  const extensionAPI = typeof browser !== "undefined" ? browser : chrome;
  if (document.querySelector("#factttl-controller")) return;

  let currentChat = null;
  let enabled = false;
  let epoch = 0;
  let routeVersion = 0;
  let sequence = 0;
  let queue = [];
  let running = 0;
  let timer;
  const states = new Map();
  const control = document.createElement("div");
  control.id = "factttl-controller";
  control.className = "factttl-ui factttl-controller";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.setAttribute("role", "switch");
  toggle.setAttribute("aria-label", "Verifica automatica FactTTL per questa chat");
  const settings = document.createElement("button");
  settings.type = "button";
  settings.textContent = "⚙";
  settings.title = "Collega il controllo locale";
  settings.setAttribute("aria-label", "Impostazioni FactTTL");
  settings.addEventListener("click", () => send({type: "OPEN_OPTIONS"}));
  control.append(toggle, settings);
  document.body.append(control);

  async function send(message) {
    try { return await extensionAPI.runtime.sendMessage(message); }
    catch { return {ok: false, message: "Estensione aggiornata: ricarica questa pagina."}; }
  }
  const memory = typeof FactTTLMemory !== "undefined" ? FactTTLMemory.install({getState: () => ({enabled, chatId: currentChat}), send, control}) : null;

  function updateToggle() {
    memory?.refresh();
    toggle.textContent = enabled ? "● FactTTL attivo" : "○ FactTTL disattivo";
    toggle.setAttribute("aria-checked", String(enabled));
    toggle.disabled = !currentChat;
    toggle.title = currentChat ? "Controlla automaticamente le risposte di questa chat" : "Avvia una conversazione per attivare FactTTL";
    control.dataset.enabled = String(enabled);
  }

  function reset() {
    epoch += 1;
    queue = [];
    states.clear();
    FactTTLItemUI.close();
    document.querySelectorAll(".factttl-result").forEach(node => node.remove());
  }

  toggle.addEventListener("click", async () => {
    if (!currentChat) return;
    const chat = currentChat;
    const next = !enabled;
    // Hiding controls and invalidating work must not wait for background storage.
    if (!next) { enabled = false; reset(); updateToggle(); }
    toggle.disabled = true;
    const saved = await send({type: "SET_CHAT_STATE", payload: {chatId: chat, enabled: next}});
    if (chat !== currentChat) return;
    enabled = saved.ok ? next : false;
    reset();
    updateToggle();
    if (enabled) scan();
  });

  async function syncRoute() {
    const next = chatKey(location.pathname);
    if (next === currentChat) return;
    if (currentChat) send({type: "CANCEL_CHAT", payload: {chatId: currentChat}});
    currentChat = next;
    enabled = false;
    reset();
    updateToggle();
    const version = ++routeVersion;
    if (next) {
      const state = await send({type: "GET_CHAT_STATE", payload: {chatId: next}});
      if (version !== routeVersion || next !== currentChat) return;
      enabled = Boolean(state.ok && state.enabled);
      updateToggle();
      if (enabled) scan();
    }
  }

  function resultUI(node) {
    const state = FactTTLItemUI.create(node, () => {
      state.finishedAt = 0; state.signature = ""; schedule();
    });
    return state;
  }

  function showResult(state, response) { FactTTLItemUI.update(state, response); }

  function isStreaming() {
    return Boolean(document.querySelector('[data-testid="stop-button"], button[aria-label="Interrompi la generazione"], button[aria-label="Stop generating"], button[aria-label="Stop"], button[aria-label="Stop response"], [data-is-streaming="true"]'));
  }

  function scan() {
    if (!enabled || !currentChat) return;
    const messages = [...new Set([...document.querySelectorAll(MESSAGE_SELECTOR)].flatMap(itemTargets))];
    const liveTargets = new Set(messages);
    for (const [node, state] of states) {
      if (!node.isConnected || !liveTargets.has(node)) { state.box.remove(); states.delete(node); }
    }
    const now = Date.now();
    for (const node of messages) {
      const itemSource = sourceFor(node);
      const payload = serializeMessage(itemSource);
      if (!payload.text) continue;
      let state = states.get(node);
      if (!state) {
        // Keep the same object captured by the badge click handler.
        state = Object.assign(resultUI(node), {signature: "", lastText: "", changedAt: now, pending: false, finishedAt: 0});
        states.set(node, state);
      }
      const signature = JSON.stringify(payload);
      if (state.lastText !== signature) {
        state.lastText = signature;
        state.changedAt = now;
        FactTTLItemUI.invalidate(state, node);
      }
      if (signature === state.signature && now - state.finishedAt < 300000) continue;
      if (state.pending || now - state.changedAt < 1400 || isStreaming()) continue;
      // Oversized answers are not silently truncated and marked as verified.
      if (payload.text.length > 20000 || payload.links.length > 20) {
        showResult(state, {ok: false, message: "Messaggio troppo lungo: non verificato"});
        state.signature = signature;
        state.finishedAt = now;
        continue;
      }
      state.pending = true;
      queue.push({node, source: itemSource, state, signature, epoch, chatId: currentChat, payload: {...payload, id: crypto.randomUUID(), chatId: currentChat}});
    }
    pump();
  }

  async function pump() {
    if (!enabled) return;
    while (queue.length && running < 2) {
      const job = queue.shift();
      if (job.epoch !== epoch || job.chatId !== currentChat || !job.node.isConnected) continue;
      running += 1;
      job.state.badge.textContent = "Controllo…";
      send({type: "VERIFY_MESSAGE", payload: job.payload}).then(response => {
        if (!enabled || epoch !== job.epoch || currentChat !== job.chatId || !job.node.isConnected) return;
        // A replaced/edited answer must never receive the result for its old text.
        if (JSON.stringify(serializeMessage(job.source)) !== job.signature) return;
        showResult(job.state, response);
        job.state.signature = job.signature;
        job.state.finishedAt = Date.now();
      }).finally(() => {
        job.state.pending = false;
        running -= 1;
        if (enabled) { scan(); pump(); }
      });
    }
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(() => { syncRoute(); scan(); }, 1600);
  }
  new MutationObserver(records => {
    if (records.some(r => !(r.target.nodeType === 1 ? r.target : r.target.parentElement)?.closest(".factttl-ui"))) schedule();
  }).observe(document.body, {subtree: true, childList: true, characterData: true});
  addEventListener("popstate", () => { syncRoute(); schedule(); });
  extensionAPI.runtime.onMessage.addListener(message => {
    if (message.type === "PREFERENCES_CHANGED") { reset(); if (enabled) scan(); }
    if (message.type === "CHAT_STATE_CHANGED" && message.chatId === currentChat) {
      enabled = Boolean(message.enabled);
      reset(); updateToggle(); if (enabled) scan();
    }
  });
  // SPA navigation need not emit popstate; route is also checked periodically.
  setInterval(() => { syncRoute(); if (!document.hidden) scan(); }, 2000);
  updateToggle();
  syncRoute();
})();

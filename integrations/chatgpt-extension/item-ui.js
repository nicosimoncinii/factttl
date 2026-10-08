/* User-facing evidence sheets. Loaded only in the extension's isolated world. */
(() => {
  "use strict";
  const kinds = {product_availability: "Disponibilità", product_price: "Prezzo", product_discount: "Sconto", link_available: "Apertura del link", news: "Notizia"};
  const sameURL = (a, b) => { try { const x = new URL(a); const y = new URL(b); x.hash = y.hash = ""; return x.href === y.href; } catch { return false; } };
  function summarize(result, url) {
    const all = (result.checks || []).map(c => c.result || c);
    const checks = url ? all.filter(c => sameURL(c.url, url)) : all;
    const factual = checks.filter(c => c.kind !== "link_available");
    const assessed = c => (c.evidence || []).some(e => e.provider === "ai_assessed_live_source" && ["current_source_consistency", "excerpt_consistency"].includes(e.scope) && e.assessment === c.outcome && (e.citations || []).length);
    const excerpt = c => (c.evidence || []).some(e => e.source_analysis_truncated === true || e.scope === "excerpt_consistency");
    let status = "INCONCLUSIVE", label = "Non verificato";
    const conflicting = checks.some(c => c.kind === "news" && (c.evidence || []).some(e => e.provider === "provided_source_comparison" && e.conflicting_sources === true));
    if (conflicting) label = "Fonti in contrasto";
    else if (checks.some(c => c.outcome === "CONTRADICTED" && (c.kind !== "news" || assessed(c)))) { status = "CONTRADICTED"; label = factual.some(c => c.outcome === "CONTRADICTED") ? "Dato smentito" : "Link non disponibile"; }
    else if (checks.some(c => c.kind === "news")) {
      const news = checks.filter(c => c.kind === "news");
      if (news.every(c => c.outcome === "SUPPORTED" && assessed(c)) && !(result.prior_corrections || []).length) {
        status = news.some(excerpt) ? "PARTIAL" : "SUPPORTED";
        label = news.some(excerpt) ? "Coerente con estratto" : "Coerente con la fonte";
      }
      else label = "Notizia non verificata";
    }
    else if (factual.length && factual.every(c => c.outcome === "SUPPORTED") && !(result.unchecked_claims || []).length && !(result.prior_corrections || []).length) { status = "SUPPORTED"; label = "Dati confermati"; }
    else if (factual.some(c => c.outcome === "SUPPORTED")) { status = "PARTIAL"; label = "Verifica parziale"; }
    else if (checks.length && checks.every(c => c.kind === "link_available" && c.outcome === "SUPPORTED")) { status = "ACCESSIBLE"; label = "Link accessibile"; }
    if (status === "CONTRADICTED" && checks.some(c => c.kind === "news" && c.outcome === "CONTRADICTED" && assessed(c))) label = checks.some(c => c.kind === "news" && c.outcome === "CONTRADICTED" && excerpt(c)) ? "In contrasto con estratto" : "In contrasto con la fonte";
    if (result.status === "ERROR") { status = "ERROR"; label = "Controllo non riuscito"; }
    return {status, label, checks};
  }
  const exported = {summarize, sameURL};
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  if (typeof document === "undefined") return;
  let dialog;
  let lastFocus;
  function text(parent, tag, value, className) {
    const node = document.createElement(tag); node.textContent = value;
    if (className) node.className = className;
    parent.append(node); return node;
  }
  function evidenceText(parent, tag, value, limit, className) {
    const content = String(value);
    text(parent, tag, content.length > limit ? `${content.slice(0, limit).trimEnd()}…` : content, className);
    if (content.length > limit) {
      const details = document.createElement("details"); details.className = "factttl-full-evidence";
      text(details, "summary", "Leggi prove complete");
      text(details, tag, content, className);
      parent.append(details);
    }
  }
  function close() { if (dialog) { dialog.close(); dialog.remove(); dialog = null; lastFocus?.focus(); } }
  function open(state) {
    close(); lastFocus = state.badge;
    dialog = document.createElement("dialog"); dialog.className = "factttl-ui factttl-sheet";
    dialog.setAttribute("aria-labelledby", "factttl-sheet-title");
    const header = document.createElement("header");
    text(header, "span", "FactTTL", "factttl-sheet-brand");
    const exit = text(header, "button", "Chiudi", "factttl-close"); exit.type = "button"; exit.addEventListener("click", close);
    dialog.append(header);
    const title = text(dialog, "h2", state.title || "Contenuto da verificare"); title.id = "factttl-sheet-title";
    const summary = summarize(state.result || {}, state.url);
    const conclusion = text(dialog, "p", summary.label, "factttl-conclusion"); conclusion.dataset.status = summary.status;
    const intro = summary.status === "CONTRADICTED"
      ? "Il dato indicato non coincide con la fonte consultata."
      : summary.status === "ACCESSIBLE"
        ? "Il link si apre; questo non conferma disponibilità o veridicità."
        : summary.status === "SUPPORTED"
          ? "La fonte conferma le proprietà elencate qui, non l’intera risposta."
          : summary.status === "PARTIAL"
            ? "Solo alcune proprietà hanno trovato riscontro."
            : null;
    if (intro) text(dialog, "p", intro, "factttl-sheet-intro");
    if (state.result?.discovery?.enabled === true) text(dialog, "p", `Ricerca esterna Bing: inviate ${Number.isInteger(state.result.discovery.queries_sent) ? state.result.discovery.queries_sent : 0} query sul tema. I risultati RSS indicano fonti da leggere; i loro riassunti non sono prove.`, "factttl-sheet-note");
    const list = document.createElement("div"); list.className = "factttl-facts";
    for (const check of summary.checks) {
      const row = document.createElement("section"); row.className = "factttl-fact-row";
      text(row, "h3", kinds[check.kind] || "Informazione");
      let value = "Non determinato";
      if (check.kind === "link_available") value = check.outcome === "SUPPORTED" ? "La pagina si apre" : check.outcome === "CONTRADICTED" ? "La pagina non è disponibile" : "Non siamo riusciti ad aprire la pagina";
      if (check.kind === "product_availability") value = check.observed_value === "available" ? "Disponibile sulla pagina pubblica" : check.observed_value === "unavailable" ? "Non disponibile sulla pagina pubblica" : "Disponibilità non confermata";
      if (check.kind === "product_price") value = check.observed_value ? `Prezzo letto: ${check.observed_value}` : "Prezzo non leggibile";
      if (check.kind === "product_discount") value = check.outcome === "SUPPORTED" ? "La fonte conferma lo sconto indicato" : check.outcome === "CONTRADICTED" ? "La fonte smentisce lo sconto indicato" : "Manca un confronto chiaro con il prezzo precedente";
      if (check.kind === "news") value = check.published_at ? `Pubblicata il ${new Date(check.published_at).toLocaleDateString("it-IT")}` : "Data di pubblicazione non certa";
      text(row, "p", value, "factttl-fact-value");
      if (check.kind === "product_price" && check.expected_value && check.outcome === "CONTRADICTED") text(row, "p", `Nella risposta era indicato ${check.expected_value}. Questo valore non coincide con la fonte.`, "factttl-fact-note");
      if (check.kind === "news") {
        text(row, "p", "La data indica quanto è vecchia la notizia. La sua veridicità richiede prove sul contenuto e fonti aggiornate.", "factttl-fact-note");
        const evidence = (check.evidence || []).find(e => e.source_excerpt);
        if (evidence) evidenceText(row, "blockquote", evidence.source_excerpt, 240);
        const sourceState = (check.evidence || []).find(e => e.source === "live_news_source");
        if (sourceState && sourceState.source_status !== "FETCHED") text(row, "p", "La fonte non ha restituito un testo leggibile: il contenuto della notizia non è stato confrontato.", "factttl-fact-note");
        const assessment = (check.evidence || []).find(e => e.provider === "ai_assessed_live_source");
        const comparison = (check.evidence || []).find(e => e.provider === "provided_source_comparison");
        if (comparison) text(row, "p", comparison.conflicting_sources ? "Le fonti non concordano: questa affermazione non è confermata." : `Fonti previste nel confronto: ${comparison.supplied_source_count ?? comparison.source_count}. Un limite o un errore può impedirne la lettura; controlla gli esiti sotto. L’indipendenza non è stata accertata.`, "factttl-fact-note");
        const discovery = (check.evidence || []).find(e => e.provider === "public_source_discovery");
        if (discovery) {
          const messages = {FOUND: `Lette ${discovery.fetched_source_count} fonti trovate tramite ricerca esterna. La loro indipendenza non è stata accertata.`, EMPTY: "La ricerca esterna non ha trovato fonti utilizzabili.", ERROR: "La ricerca esterna non è riuscita: questo non conferma né smentisce la notizia.", PRIVACY_REJECTED: "Query non inviata per proteggere dati potenzialmente privati."};
          text(row, "p", messages[discovery.status] || "Ricerca esterna senza prove sufficienti.", "factttl-fact-note");
        }
        if (assessment) {
          if (assessment.source_analysis_truncated === true || assessment.scope === "excerpt_consistency") text(row, "p", "Il confronto riguarda solo un estratto del testo: non verifica l’intero articolo né la verità della notizia.", "factttl-fact-note");
          text(row, "p", assessment.configured ? "Valutazione AI del testo letto nella fonte. Non è una conferma indipendente della notizia." : "Il motore AI per confrontare la notizia con le fonti non è ancora configurato.", "factttl-fact-note");
          for (const citation of assessment.citations || []) if (citation.quote) evidenceText(row, "blockquote", citation.quote, 350);
          if (assessment.configured && check.rationale) evidenceText(row, "p", check.rationale, 400, "factttl-fact-note");
        }
      }
      list.append(row);
    }
    if (!summary.checks.length) list.hidden = true;
    dialog.append(list);
    const context = state.result?.context || state.result?.preferences || {};
    const countries = {IT: "Italia", US: "Stati Uniti", GB: "Regno Unito", DE: "Germania", FR: "Francia", ES: "Spagna"};
    const regionNote = summary.checks.some(c => c.kind.startsWith("product_")) ? "I prezzi e la consegna del tuo account possono essere diversi dalla pagina pubblica." : "È una preferenza di riferimento, non una posizione rilevata tramite GPS.";
    text(dialog, "p", `Paese scelto: ${countries[context.country] || "non specificato"}. ${regionNote}`, "factttl-sheet-note");
    for (const item of state.result?.checks || []) {
      if ((!state.url || sameURL(item.result?.url, state.url)) && item.regional_context?.warning) text(dialog, "p", "Il marketplace della fonte è diverso dal paese scelto: disponibilità e prezzo per la tua destinazione non sono confermati.", "factttl-sheet-note");
    }
    for (const warning of state.result?.region_warnings || []) text(dialog, "p", typeof warning === "string" ? warning : warning.message || "Il mercato della fonte può essere diverso dal paese scelto.", "factttl-sheet-note");
    if (state.result?.checked_at) text(dialog, "p", `Controllato il ${new Date(state.result.checked_at).toLocaleString("it-IT")}`, "factttl-sheet-time");
    const actions = document.createElement("footer");
    if (state.url) {
      const source = text(actions, "a", "Apri la fonte"); source.href = state.url; source.target = "_blank"; source.rel = "noopener noreferrer";
    }
    const retry = text(actions, "button", "Aggiorna il controllo"); retry.type = "button"; retry.addEventListener("click", () => { close(); state.retry(); });
    if (summary.status === "CONTRADICTED") {
      const copy = text(actions, "button", "Copia la correzione per la chat"); copy.type = "button";
      copy.addEventListener("click", async () => {
        const lines = summary.checks.filter(c => c.outcome === "CONTRADICTED").map(c => c.kind === "news" ? `Affermazione: ${c.claim_text || state.title}. Valutazione AI rispetto alla fonte: ${c.rationale || "in contrasto"}. Fonte: ${c.url}` : `${kinds[c.kind] || "Dato"}: indicato ${c.expected_value || "—"}, osservato ${c.observed_value || "—"}. Fonte: ${c.url}`);
        try { await navigator.clipboard.writeText(`FactTTL ha trovato un contrasto con la fonte attuale:\n${lines.join("\n")}\nCorreggi la risposta e ricontrolla prima di ripetere queste indicazioni.`); copy.textContent = "Copiata: incolla nella chat"; } catch { copy.textContent = "Copia non disponibile"; }
      });
    }
    dialog.append(actions); dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
    document.body.append(dialog); dialog.showModal();
  }
  function create(node, retry) {
    const box = document.createElement(node.tagName === "A" ? "span" : "div"); box.className = "factttl-ui factttl-result factttl-item";
    const badge = text(box, "button", "○ Controllo…", "factttl-badge"); badge.type = "button"; badge.dataset.status = "PENDING";
    badge.setAttribute("aria-haspopup", "dialog"); node.after(box);
    const state = {box, badge, url: node.tagName === "A" ? node.href : null, title: (node.textContent || "").trim().slice(0, 180), retry};
    badge.addEventListener("click", () => open(state)); return state;
  }
  function update(state, response) {
    state.result = response?.ok && response.result ? response.result : {status: "ERROR"};
    const summary = summarize(state.result, state.url); state.badge.dataset.status = summary.status;
    state.badge.textContent = `${summary.status === "SUPPORTED" ? "✓" : summary.status === "CONTRADICTED" ? "!" : "○"} ${summary.label}`;
    state.badge.setAttribute("aria-label", `${summary.label}: ${state.title}`);
  }
  function invalidate(state, node) {
    // A reused DOM node can point to a different source after an assistant edit.
    // Old evidence must disappear before the replacement request completes.
    state.url = node.tagName === "A" ? node.href : null;
    state.title = (node.textContent || "").trim().slice(0, 180);
    state.result = undefined;
    close();
    state.badge.textContent = "Attendo…";
    state.badge.dataset.status = "PENDING";
    state.badge.setAttribute("aria-label", `Controllo in attesa: ${state.title}`);
  }
  globalThis.FactTTLItemUI = {create, update, invalidate, close, summarize};
})();

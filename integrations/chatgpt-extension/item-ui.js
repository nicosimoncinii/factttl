/* User-facing evidence sheets. Loaded only in the extension's isolated world. */
(() => {
  "use strict";
  const kinds = {product_availability: "Disponibilità", product_price: "Prezzo", product_discount: "Sconto", link_available: "Apertura del link", news: "Notizia"};
  const sameURL = (a, b) => { try { const x = new URL(a); const y = new URL(b); x.hash = y.hash = ""; return x.href === y.href; } catch { return false; } };
  function amazonSearch(value) {
    try { const u = new URL(value); return u.protocol === "https:" && !u.username && !u.password && (!u.port || u.port === "443") && ["amazon.it", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es"].includes(u.hostname.replace(/^www\./, "")) && /^\/(?:s|gp\/search)\/?$/.test(u.pathname); } catch { return false; }
  }
  function searchDestination(value) {
    if (amazonSearch(value)) return "amazon";
    try {
      const u = new URL(value), queries = u.searchParams.getAll("q");
      return u.protocol === "https:" && !u.username && !u.password && (!u.port || u.port === "443") &&
        ["chatgpt.com", "www.chatgpt.com", "chat.openai.com"].includes(u.hostname) && u.pathname === "/" &&
        u.searchParams.getAll("hints").length === 1 && u.searchParams.get("hints") === "search" && queries.length === 1 &&
        Boolean(queries[0].trim()) && queries[0].length <= 1000 && !/[\u0000-\u001f\u007f]/.test(queries[0]) ? "host" : null;
    } catch { return null; }
  }
  function summarize(result, url) {
    const all = (result.checks || []).map(c => c.result || c);
    const checks = url ? all.filter(c => sameURL(c.url, url)) : all;
    const search = searchDestination(url);
    // A search destination cannot become a verified offer or an out-of-stock
    // product, regardless of a bridge error or an accessible search page.
    if (search) return {status: "SEARCH", label: search === "host" ? "Ricerca ChatGPT: nessuna offerta scelta" : "Ricerca Amazon: nessuna offerta scelta", checks: checks.filter(c => c.kind === "link_available")};
    const factual = checks.filter(c => c.kind !== "link_available");
    const assessed = c => (c.evidence || []).some(e => e.provider === "ai_assessed_live_source" && ["current_source_consistency", "excerpt_consistency"].includes(e.scope) && e.assessment === c.outcome && (e.citations || []).length);
    const excerpt = c => (c.evidence || []).some(e => e.source_analysis_truncated === true || e.scope === "excerpt_consistency");
    const news = checks.filter(c => c.kind === "news");
    const grouped = !url && news.length ? news.map(c => {
      const comparison = (c.evidence || []).find(e => e.provider === "provided_source_comparison");
      if (!comparison || !["SUPPORTED", "CONTRADICTED"].includes(comparison.assessment) || !(comparison.assessment_basis_urls || []).length) return null;
      if (!news.some(member => member.outcome === comparison.assessment && comparison.assessment_basis_urls.some(basis => sameURL(basis, member.url)) && assessed(member))) return null;
      return assessed({...c, outcome: comparison.assessment}) ? {...c, outcome: comparison.assessment} : null;
    }) : [];
    let status = "INCONCLUSIVE", label = "Non verificato";
    const conflicting = checks.some(c => c.kind === "news" && (c.evidence || []).some(e => e.provider === "provided_source_comparison" && e.conflicting_sources === true));
    if (conflicting) label = "Fonti in contrasto";
    else if (grouped.length && grouped.every(Boolean) && grouped.every(c => c.outcome === "SUPPORTED") && !(result.prior_corrections || []).length) {
      status = grouped.some(excerpt) ? "PARTIAL" : "SUPPORTED";
      label = grouped.some(excerpt) ? "Coerente con estratto" : "Coerente con la fonte";
    }
    else if (grouped.some(c => c?.outcome === "CONTRADICTED")) {
      status = "CONTRADICTED";
      label = grouped.some(c => c?.outcome === "CONTRADICTED" && excerpt(c)) ? "In contrasto con estratto" : "In contrasto con la fonte";
    }
    else if (checks.some(c => c.outcome === "CONTRADICTED" && (c.kind !== "news" || assessed(c)))) { status = "CONTRADICTED"; label = factual.some(c => c.outcome === "CONTRADICTED") ? "Dato smentito" : "Link non disponibile"; }
    else if (checks.some(c => c.kind === "news")) {
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
    if (status === "CONTRADICTED" && !checks.some(c => c.kind === "news")) {
      if (checks.some(c => c.kind === "product_availability" && c.outcome === "CONTRADICTED" && c.observed_value === "unavailable")) label = "Prodotto non disponibile";
      else if (checks.some(c => c.kind === "product_price" && c.outcome === "CONTRADICTED")) label = "Prezzo diverso";
      else if (checks.some(c => c.kind === "product_discount" && c.outcome === "CONTRADICTED")) label = "Sconto non confermato";
    }
    if (status === "INCONCLUSIVE" && checks.some(c => c.outcome === "ERROR")) { status = "ERROR"; label = "Controllo incompleto"; }
    if (result.status === "ERROR") { status = "ERROR"; label = "Controllo non riuscito"; }
    if (!["CONTRADICTED", "ERROR"].includes(status)) {
      const stock = checks.find(c => c.kind === "product_availability" && c.outcome === "SUPPORTED" && c.observed_value === "available");
      const price = checks.find(c => c.kind === "product_price" && c.outcome === "SUPPORTED" && /^\d+(?:[.,]\d{1,2})? (EUR|USD|GBP)$/.test(c.observed_value || ""));
      if (stock && price) label = `Disponibile · ${formatPrice(price.observed_value, result.context?.language || result.preferences?.language)}`;
      else if (stock) label = "Disponibile · prezzo da verificare";
      else if (price) label = `${formatPrice(price.observed_value, result.context?.language || result.preferences?.language)} · disponibilità da verificare`;
    }
    return {status, label, checks};
  }
  const exported = {summarize, sameURL, searchDestination};
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
  function sourceLink(parent, url, label) {
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "https:" || parsed.username || parsed.password) return;
      const link = text(parent, "a", label || parsed.hostname.replace(/^www\./, ""), "factttl-source-link");
      link.href = parsed.href; link.target = "_blank"; link.rel = "noopener noreferrer";
    } catch { /* Invalid source metadata cannot become a navigation action. */ }
  }
  function diagnosis(check, response) {
    const evidence = check?.evidence || [];
    const reason = evidence.map(e => `${e.error_reason || ""} ${e.source_status || ""}`).join(" ") + " " + (check?.rationale || "") + " " + (response?.message || "") + " " + (response?.error || "");
    if (/UNAUTHORIZED|INVALID_TOKEN/i.test(reason)) return "Il browser non è autorizzato al servizio locale. Importa nuovamente il file di configurazione nelle impostazioni.";
    if (/FETCH_FAILED|NETWORK_ERROR|not.*connect|non.*colleg|servizio.*rispond/i.test(reason)) return "Il servizio locale non risponde. Avvia FactTTL e riprova il collegamento nelle impostazioni.";
    if (/challenge|captcha|anti.bot|login|sign.in/i.test(reason)) return "Il sito richiede un accesso o blocca il controllo automatico. Apri la fonte per verificare direttamente.";
    if (/not_configured|non.*configurat|absent/i.test(reason)) return "Il motore delle notizie non è configurato. Apri le impostazioni per controllare il collegamento.";
    if (/budget|timeout|deadline|time.*exceed|tempo.*esaurito/i.test(reason)) return "Il controllo non è terminato in tempo. Riprova; nessun dato è stato confermato.";
    if (/citation|schema|invalid.*model|assessment|valutazione.*utilizzabile/i.test(reason)) return "Il modello non ha fornito prove utilizzabili. La notizia resta da verificare.";
    return "Non abbiamo raccolto prove sufficienti per questo contenuto. Riprova oppure consulta la fonte.";
  }
  function formatPrice(value, language) {
    const match = typeof value === "string" && value.match(/^(\d+(?:[.,]\d{1,2})?)\s+(EUR|USD|GBP)$/);
    if (!match) return value;
    const locale = {it: "it-IT", en: "en-US", de: "de-DE", fr: "fr-FR", es: "es-ES"}[language] || "it-IT";
    return new Intl.NumberFormat(locale, {style: "currency", currency: match[2]}).format(Number(match[1].replace(",", ".")));
  }
  function open(state) {
    close(); lastFocus = state.badge;
    dialog = document.createElement("dialog"); dialog.className = "factttl-ui factttl-sheet";
    dialog.setAttribute("aria-labelledby", "factttl-sheet-title");
    const header = document.createElement("header");
    text(header, "span", "FactTTL", "factttl-sheet-brand");
    const exit = text(header, "button", "Chiudi", "factttl-close"); exit.type = "button"; exit.addEventListener("click", close);
    dialog.append(header);
    const summary = summarize(state.result || {}, state.url);
    const product = summary.checks.some(c => c.kind.startsWith("product_"));
    const sourceTitle = summary.checks.flatMap(c => c.evidence || []).map(e => e.product_name || e.product_title || e.title).find(value => typeof value === "string" && value.trim());
    text(dialog, "span", product ? "Controllo del prodotto" : summary.checks.some(c => c.kind === "news") ? "Controllo della notizia" : "Controllo del riferimento", "factttl-sheet-category");
    const title = text(dialog, "h2", sourceTitle || state.title || "Contenuto da verificare"); title.id = "factttl-sheet-title";
    const conclusion = text(dialog, "p", summary.label, "factttl-conclusion"); conclusion.dataset.status = summary.status;
    const intro = summary.status === "SEARCH"
      ? "Questo link apre una ricerca, non un’offerta precisa. Prezzo, disponibilità e compatibilità dei prodotti non sono stati verificati. FactTTL chiede alla chat di cercare link diretti al prodotto nel negozio richiesto."
      : summary.status === "CONTRADICTED"
      ? "Il dato indicato non coincide con la fonte consultata."
      : summary.status === "ACCESSIBLE"
        ? "Il link si apre; questo non conferma disponibilità o veridicità."
        : summary.status === "SUPPORTED"
          ? "La fonte conferma le proprietà elencate qui, non l’intera risposta."
          : summary.status === "PARTIAL"
            ? "Solo alcune proprietà hanno trovato riscontro."
            : null;
    if (intro) text(dialog, "p", intro, "factttl-sheet-intro");
    if (["INCONCLUSIVE", "ERROR"].includes(summary.status)) text(dialog, "p", diagnosis(summary.checks.find(c => c.outcome !== "SUPPORTED"), state.response), "factttl-diagnosis");
    if (state.result?.discovery?.enabled === true && state.result.discovery.queries_sent > 0) text(dialog, "p", `Ricerca esterna Bing: inviate ${Number.isInteger(state.result.discovery.queries_sent) ? state.result.discovery.queries_sent : 0} query sul tema. I risultati RSS indicano fonti da leggere; i loro riassunti non sono prove.`, "factttl-sheet-note");
    const list = document.createElement("div"); list.className = "factttl-facts";
    const visibleChecks = summary.checks.filter(c => c.kind !== "link_available" || !summary.checks.some(other => other.kind !== "link_available") || c.outcome !== "SUPPORTED");
    list.dataset.layout = product ? "product" : "news";
    const seenNews = new Set();
    for (const check of visibleChecks) {
      if (check.kind === "news" && seenNews.has(check.claim_text || check.url)) continue;
      if (check.kind === "news") seenNews.add(check.claim_text || check.url);
      const row = document.createElement("section"); row.className = "factttl-fact-row";
      text(row, "h3", kinds[check.kind] || "Informazione");
      let value = "Non determinato";
      if (check.kind === "link_available") value = check.outcome === "SUPPORTED" ? "La pagina si apre" : check.outcome === "CONTRADICTED" ? "La pagina non è disponibile" : "Non siamo riusciti ad aprire la pagina";
      if (check.kind === "product_availability") value = check.observed_value === "available" ? "Disponibile sulla pagina pubblica" : check.observed_value === "unavailable" ? "Non disponibile sulla pagina pubblica" : "Disponibilità non confermata";
      if (check.kind === "product_price") value = check.observed_value ? `Prezzo letto: ${formatPrice(check.observed_value, state.result?.preferences?.language)}` : "Prezzo non leggibile";
      if (check.kind === "product_discount") value = check.outcome === "SUPPORTED" ? "La fonte conferma lo sconto indicato" : check.outcome === "CONTRADICTED" ? "La fonte smentisce lo sconto indicato" : "Manca un confronto chiaro con il prezzo precedente";
      if (check.kind === "news") value = check.published_at ? `Pubblicata il ${new Date(check.published_at).toLocaleDateString("it-IT")}` : "Data di pubblicazione non certa";
      text(row, "p", value, "factttl-fact-value");
      if (check.kind.startsWith("product_")) {
        const expected = check.kind === "product_availability" ? check.expected_value === "true" ? "Disponibile" : check.expected_value === "false" ? "Non disponibile" : null : check.kind === "product_discount" ? check.expected_value === "true" ? "In sconto" : check.expected_value === "false" ? "Non in sconto" : null : formatPrice(check.expected_value, state.result?.preferences?.language);
        if (expected) text(row, "p", `Nella risposta: ${expected}`, "factttl-asserted-value");
        if (check.outcome === "INCONCLUSIVE" || check.outcome === "ERROR") text(row, "p", diagnosis(check), "factttl-fact-note");
      }
      if (check.kind === "product_price" && check.expected_value && check.outcome === "CONTRADICTED") text(row, "p", "Il prezzo indicato nella risposta non coincide con quello letto nella fonte.", "factttl-fact-note");
      if (check.kind === "news") {
        const methodology = document.createElement("details"); methodology.className = "factttl-methodology";
        text(methodology, "summary", "Come è stato verificato");
        if (check.claim_text) evidenceText(row, "p", check.claim_text, 240, "factttl-claim-text");
        const evidence = (check.evidence || []).find(e => e.source_excerpt);
        const hasQuotes = (check.evidence || []).some(e => e.provider === "ai_assessed_live_source" && (e.citations || []).length);
        if (evidence && !hasQuotes) evidenceText(row, "blockquote", evidence.source_excerpt, 240);
        const sourceState = (check.evidence || []).find(e => e.source === "live_news_source");
        if (sourceState && sourceState.source_status !== "FETCHED") text(row, "p", "La fonte non ha restituito un testo leggibile: il contenuto della notizia non è stato confrontato.", "factttl-fact-note");
        const assessment = (check.evidence || []).find(e => e.provider === "ai_assessed_live_source");
        const comparison = (check.evidence || []).find(e => e.provider === "provided_source_comparison");
        if (comparison) text(methodology, "p", comparison.conflicting_sources ? "Le fonti non concordano: questa affermazione non è confermata." : `Fonti previste nel confronto: ${comparison.supplied_source_count ?? comparison.source_count}. Un limite o un errore può impedirne la lettura. L’indipendenza non è stata accertata.`, "factttl-fact-note");
        if (comparison && (comparison.inconclusive_source_count || comparison.omitted_source_count)) text(row, "p", `${comparison.inconclusive_source_count || 0} fonti senza esito conclusivo; ${comparison.omitted_source_count || 0} fonti non lette. Il riscontro riguarda solo le prove citate.`, "factttl-fact-note");
        const discovery = (check.evidence || []).find(e => e.provider === "public_source_discovery");
        if (discovery) {
          const messages = {FOUND: `Lette ${discovery.fetched_source_count} fonti trovate tramite ricerca esterna. La loro indipendenza non è stata accertata.`, EMPTY: "La ricerca esterna non ha trovato fonti utilizzabili.", ERROR: "La ricerca esterna non è riuscita: questo non conferma né smentisce la notizia.", PRIVACY_REJECTED: "Query non inviata per proteggere dati potenzialmente privati."};
          text(methodology, "p", messages[discovery.status] || "Ricerca esterna senza prove sufficienti.", "factttl-fact-note");
        }
        if (assessment) {
          if (assessment.source_analysis_truncated === true || assessment.scope === "excerpt_consistency") text(row, "p", "Il confronto riguarda solo un estratto del testo: non verifica l’intero articolo né la verità della notizia.", "factttl-fact-note");
          text(methodology, "p", assessment.configured ? "Valutazione AI del testo letto nella fonte. Non è una conferma indipendente della notizia." : "Il motore AI per confrontare la notizia con le fonti non è ancora configurato.", "factttl-fact-note");
          const citations = (check.evidence || []).filter(e => e.provider === "ai_assessed_live_source").flatMap(e => (e.citations || []).map(c => ({...c, verdict: e.assessment})));
          const seenQuotes = new Set();
          for (const citation of citations) if (citation.quote && !seenQuotes.has(citation.quote)) {
            seenQuotes.add(citation.quote);
            const proof = document.createElement("div"); proof.className = "factttl-proof";
            text(proof, "span", citation.verdict === "CONTRADICTED" ? "Prova contraria" : citation.verdict === "SUPPORTED" ? "Riscontro nella fonte" : "Passaggio consultato", "factttl-proof-label");
            evidenceText(proof, "blockquote", citation.quote, 350);
            sourceLink(proof, citation.source_url || check.url);
            row.append(proof);
          }
          if (assessment.configured && check.rationale) evidenceText(methodology, "p", check.rationale, 400, "factttl-fact-note");
        }
        row.append(methodology);
      }
      list.append(row);
    }
    if (!summary.checks.length) list.hidden = true;
    dialog.append(list);
    const provenance = document.createElement("section"); provenance.className = "factttl-provenance";
    text(provenance, "h3", "Fonti e controllo");
    for (const url of new Set(summary.checks.map(c => c.url).filter(Boolean))) sourceLink(provenance, url);
    const checked = state.result?.checked_at || summary.checks.find(c => c.observed_at)?.observed_at;
    if (checked && !Number.isNaN(new Date(checked).getTime())) text(provenance, "p", `Controllato il ${new Date(checked).toLocaleString("it-IT")}`, "factttl-sheet-time");
    dialog.append(provenance);
    const context = state.result?.context || state.result?.preferences || {};
    const countries = {IT: "Italia", US: "Stati Uniti", GB: "Regno Unito", DE: "Germania", FR: "Francia", ES: "Spagna"};
    const regionNote = summary.checks.some(c => c.kind.startsWith("product_")) ? "I prezzi e la consegna del tuo account possono essere diversi dalla pagina pubblica." : "È una preferenza di riferimento, non una posizione rilevata tramite GPS.";
    text(dialog, "p", `Paese scelto: ${countries[context.country] || "non specificato"}. ${regionNote}`, "factttl-sheet-note");
    for (const item of state.result?.checks || []) {
      if ((!state.url || sameURL(item.result?.url, state.url)) && item.regional_context?.warning) text(dialog, "p", "Il marketplace della fonte è diverso dal paese scelto: disponibilità e prezzo per la tua destinazione non sono confermati.", "factttl-sheet-note");
    }
    for (const warning of state.result?.region_warnings || []) text(dialog, "p", typeof warning === "string" ? warning : warning.message || "Il mercato della fonte può essere diverso dal paese scelto.", "factttl-sheet-note");
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
    badge.setAttribute("aria-haspopup", "dialog");
    if (node.parentElement?.tagName === "TR") {
      // A table row accepts cells, never an injected span as a direct child.
      const cell = document.createElement("td"); cell.className = "factttl-ui";
      cell.append(box); node.parentElement.append(cell);
    } else node.after(box);
    const state = {box, badge, url: node.tagName === "A" ? node.href : null, title: (node.textContent || "").trim().slice(0, 180), retry};
    badge.addEventListener("click", () => open(state)); return state;
  }
  function update(state, response) {
    state.response = response;
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
    state.response = undefined;
    close();
    state.badge.textContent = "Attendo…";
    state.badge.dataset.status = "PENDING";
    state.badge.setAttribute("aria-label", `Controllo in attesa: ${state.title}`);
  }
  globalThis.FactTTLItemUI = {create, update, invalidate, close, summarize, searchDestination};
})();

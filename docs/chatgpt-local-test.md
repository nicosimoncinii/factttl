# Prova FactTTL in ChatGPT tramite Secure MCP Tunnel

Questa guida collega i veri strumenti MCP di FactTTL a ChatGPT. I risultati
arrivano al modello come tool result strutturati: l'estensione non scrive prompt
nella barra, non intercetta Invio e non pubblica messaggi di correzione.

L'avvio locale, il tunnel e la selezione del plugin sono tre stati distinti. Un
server pronto su `127.0.0.1` non dimostra che il tunnel sia autenticato o che la
chat corrente possa chiamare gli strumenti.

## Prerequisiti

- ChatGPT con accesso ai plugin/server MCP personalizzati nel proprio account o
  workspace.
- Un tunnel personale associato al contesto ChatGPT corretto, il relativo
  `tunnel_id` e una runtime API key con i permessi richiesti.
- FactTTL installato con l'extra MCP e la runtime `tunnel-client` ufficiale.
- Accesso HTTPS in uscita a `api.openai.com:443` e alle fonti pubbliche da
  verificare. Se è abilitata la discovery Bing, si applica anche la disclosure
  in [privacy e rete](privacy-and-network.md).

Non salvare API key nel repository, nei prompt o nei file di policy. Consulta la
guida ufficiale [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
per creare il tunnel e la guida [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)
per collegarlo a ChatGPT. Disponibilità, nomi delle schermate e permessi possono
variare per account e workspace.

## Avvio locale

Il launcher Windows del progetto è `scripts/Start-FactTTL-Tool.ps1`. Richiede il
proprio tunnel ID e la propria runtime API key; non include credenziali condivise
e non può attestare da solo che l'account ChatGPT abbia completato la connessione.
Usa `Get-Help` sullo script per i parametri della versione presente nel checkout.

Per avviare manualmente il server con i tool di verifica:

```powershell
.\.venv\Scripts\factttl-mcp.exe --transport streamable-http --host 127.0.0.1 --port 8000 --enable-verification --verification-db .factttl/verification.sqlite3
```

L'endpoint locale è `http://127.0.0.1:8000/mcp`. Mantienilo su loopback. La
runtime tunnel v0.0.15 può inoltrarlo con una chiave già fornita tramite
`CONTROL_PLANE_API_KEY`:

```powershell
tunnel-client-runtime.exe run --control-plane.tunnel-id <tunnel_id> --control-plane.api-key env:CONTROL_PLANE_API_KEY --mcp.server-url url=http://127.0.0.1:8000/mcp --health.listen-addr 127.0.0.1:18080
```

Verifica i flag con `--help` se usi una runtime diversa. Non esporre direttamente
la porta 8000 su Internet. Un `200` su `http://127.0.0.1:18080/readyz` conferma
la readiness del client tunnel, non l'installazione o selezione del plugin nella
chat.

## Collegamento in ChatGPT

1. In ChatGPT apri Plugins, aggiungi un server MCP personalizzato e scegli il
   tunnel associato al tuo account.
2. Completa la configurazione richiesta e crea/installa il plugin FactTTL.
3. Aggiorna gli strumenti dopo ogni modifica a nomi, descrizioni o schemi.
4. Avvia una nuova Work chat e seleziona FactTTL. A seconda dell'interfaccia, la
   selezione iniziale può avvenire dal menu Plugin o con `@FactTTL`. Questo serve
   ad abilitare lo strumento nella chat; non inserisce una richiesta di
   correzione e non va ripetuto per ogni risultato. La metadata guida poi la
   scelta del modello.

Il browser bridge su `127.0.0.1:8765` è un servizio diverso. Serve ai badge
passivi dell'estensione e il suo stato “collegato” non prova la connessione MCP.
La porta 8000 serve il protocollo MCP; la porta 18080 espone solo la health della
runtime tunnel.

## Prova end-to-end del comportamento richiesto

Prima controlla il trasporto con `evaluate_fact_freshness` usando timestamp
espliciti. Poi prova la funzione che conta davvero:

> Prepara una bozza di due prodotti Amazon Italia con link diretti. Prima della
> risposta finale usa FactTTL `verify_recommendations` per controllare stock e
> prezzi. Se il risultato è RUNNING, usa `get_answer_verification`. Sostituisci
> gli elementi contraddetti e verifica nuovamente i link sostitutivi.

Una prova riuscita deve mostrare nella traccia strumenti una vera chiamata MCP e
un risultato `COMPLETED`. Nel risultato cerca:

- `interaction_mode: native_mcp_tool_result`;
- `memory_before_check`, anche se vuoto;
- verifiche separate per disponibilità, prezzo e sconto;
- `required_revisions` per elementi contraddetti o inconcludenti;
- `provider_memory_or_weights_modified: false`.

Un link accessibile non basta. `RUNNING`, `FAILED`, `ERROR` o `INCONCLUSIVE` non
provano disponibilità né indisponibilità. Una pagina di ricerca Amazon non è
un'offerta diretta. La verifica non certifica automaticamente compatibilità,
spedizione, venditore selezionato o totale del carrello.

## Limite del controllo automatico

Il server fornisce istruzioni e descrizioni dettagliate per indurre il modello a
verificare bozze con contenuti volatili. Il client scopre i tool e il modello
sceglie quando chiamarli. Il collegamento non garantisce che ogni modello o ogni
chat li invochi in modo automatico, e FactTTL non può modificare in silenzio un
messaggio già generato. Per collaudare la selezione usa richieste dirette e
indirette e registra tool, argomenti, risultato ed errori, come raccomandato dalla
[guida ufficiale OpenAI](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## Dopo una modifica

- Riavvia server e client tunnel.
- Controlla readiness locale e stato del tunnel nell'account.
- Aggiorna gli strumenti del plugin e apri una nuova chat.
- Verifica una chiamata reale; non dedurre la connessione da un badge del browser
  o da una frase prodotta dal modello.
- Non condividere log o configurazioni prima di rimuovere token, tunnel ID e dati
  sensibili.

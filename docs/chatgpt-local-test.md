# Prova FactTTL in ChatGPT tramite Secure MCP Tunnel

Questa guida descrive una prova locale; non implica che il tunnel o l'app siano già configurati. ChatGPT non avvia direttamente un server MCP stdio locale. Secure MCP Tunnel fa da ponte senza rendere pubblico il server.

## Prerequisiti

- ChatGPT web con accesso a server MCP personalizzati. Verifica la disponibilità effettiva dalla sezione Plugin e i permessi del tuo account/workspace.
- Un tunnel creato in OpenAI Platform, associato al contesto ChatGPT personale corretto, e i permessi tunnel richiesti. Il client locale necessita di una runtime API key e accesso HTTPS in uscita a `api.openai.com:443`. Non salvare chiavi in questo repository, nei file di policy o nei prompt.
- FactTTL installato con l'extra MCP e `tunnel-client` installato secondo la guida OpenAI. Il client tunnel deve poter avviare FactTTL in stdio oppure raggiungere il suo endpoint HTTP locale.

Consulta la guida ufficiale [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) per installazione, creazione del tunnel, permessi e configurazione del client. Le istruzioni e le schermate OpenAI possono cambiare.

Procedi se la funzione MCP è effettivamente abilitata nel tuo account.
La guida OpenAI descrive disponibilità e permessi per piano e workspace,
che possono variare.

Per una prova breve, una runtime API key con scadenza di un giorno è sufficiente.
Il server FactTTL in modalità stdio non autentica autonomamente le chiamate:
è avviato come processo figlio dal tunnel client e non apre una porta di rete.
L'accesso remoto dipende comunque dalle associazioni e dai permessi del tunnel e
dell'app/workspace ChatGPT. Se usi HTTP invece di stdio, mantieni il server
vincolato a `127.0.0.1` e non esporlo direttamente in rete.

## Prova

### Configurazione HTTP verificata il 6 ottobre 2026

La prova su un account personale è riuscita con FactTTL installato in ChatGPT
e una chiamata reale al tool tramite tunnel privato. Il server e il client devono
rimanere in esecuzione sul PC. La chiave temporanea della prova scade dopo un
giorno; dopo la scadenza serve una nuova chiave runtime con Tunnels Read + Use.

Il server locale usa:

```powershell
.\.venv\Scripts\factttl-mcp.exe --transport streamable-http --host 127.0.0.1 --port 8000
```

Il runtime ufficiale v0.0.15 usa la chiave già presente nella variabile
`CONTROL_PLANE_API_KEY` e questi argomenti (sostituisci l'ID del tuo tunnel):

```powershell
tunnel-client-runtime.exe run --control-plane.tunnel-id <tunnel_id> --mcp.server-url url=http://127.0.0.1:8000/mcp --health.listen-addr 127.0.0.1:18080
```

`http://127.0.0.1:18080/readyz` deve rispondere `200`. In ChatGPT la connessione
usa **Tunnel** e **Nessuna autenticazione**, con accesso limitato dalle
associazioni del tunnel. Per riprovare, apri FactTTL nei Plugin e scegli
**Prova in chat**. Non inserire la chiave API nella chat.

### Procedura generale

1. Nel checkout FactTTL, verifica che l'entrypoint esista:

   ```powershell
   .\.venv\Scripts\factttl-mcp.exe --help
   ```

2. Configura un target MCP stdio che avvii `factttl-mcp` (usa il percorso assoluto dell'entrypoint nel checkout; aggiungi `--policy <percorso-assoluto>` solo se vuoi provare una policy locale). Con la ZIP runtime, passa il target agli argomenti/env del comando `run`; la gestione di profili e la diagnostica del client completo non fanno parte del runtime ridotto. Segui la sintassi della versione installata di `tunnel-client`; non copiare credenziali nella configurazione del repository.

3. Avvia il client tunnel. Il runtime ridotto espone solo `run`, `--help` e `--version`; non supporta i comandi diagnostici del client completo come `doctor`. Verifica la connessione dagli indicatori health/readiness disponibili nella versione installata e dallo stato del tunnel in OpenAI Platform/ChatGPT. Se usi il client completo, puoi seguire la diagnostica `tunnel-client doctor --profile <profilo> --explain` documentata per quel client.

4. In ChatGPT web, apri la sezione Plugins/Apps, scegli **+ → Add custom MCP server**, seleziona **Tunnel**, scegli il tunnel associato al tuo account, completa l'autenticazione richiesta e crea l'app/plugin. I nomi e la posizione delle voci possono variare in base al piano e al rollout. Se il tunnel non compare, controlla l'associazione al contesto ChatGPT e i permessi `Tunnels Use`.

5. In una nuova chat, seleziona l'app e chiedi esplicitamente di chiamare `evaluate_fact_freshness` con questi argomenti:

   ```json
   {
     "evaluation_time": "2026-10-06T12:00:00Z",
     "last_checked_at": "2026-10-06T10:00:00Z",
     "ttl_seconds": 3600
   }
   ```

   Il risultato atteso è `STALE`, con `review_due_at` uguale a `2026-10-06T11:00:00.000000Z`. Questa verifica dimostra il trasporto end-to-end e la valutazione deterministica; non verifica la verità di un'affermazione.

## Riavvio dopo modifiche

### Versione con verifica e memoria

La prova personale del 6 ottobre è stata aggiornata per usare
`--enable-verification --verification-db .factttl/verification.sqlite3`.
La pagina di gestione dell'app offre **Aggiorna strumenti**: usalo dopo aver
aggiunto strumenti e avvia una nuova chat con FactTTL selezionato.

Esempio pratico: «Prima di consigliarmi questo link, consulta i controlli precedenti
e verifica adesso disponibilità e prezzo. Se non riesci a verificarli, dillo e
non presentare il prodotto come disponibile o scontato».

Per controllare la memoria, verifica un URL in una chat e in un'altra chiedi
«Usa FactTTL per recuperare i controlli precedenti di questo URL». Una smentita
resterà registrata anche se il successivo controllo fallisce. Il database è
locale, condiviso tra le chat che selezionano questo server; il plugin non può
obbligare una chat che non lo usa a consultare quel registro.

- Se cambi codice, dipendenze o policy, arresta e riavvia il server MCP locale tramite il processo che lo gestisce (normalmente `tunnel-client`), quindi riavvia il client tunnel se necessario.
- Ripeti il controllo di readiness/diagnostica prima di provare da ChatGPT.
- Se cambia lo schema o la descrizione degli strumenti, aggiorna/scansiona gli strumenti dell'app dalla sua pagina di gestione; alcune viste ChatGPT mantengono una copia delle definizioni finché non vengono aggiornate.
- Ripeti la chiamata di prova con gli stessi timestamp e confronta stato e scadenza. Non condividere log o configurazioni prima di aver rimosso token e altri dati sensibili.

Riferimenti ufficiali: [aggiungere un server MCP personalizzato a ChatGPT](https://developers.openai.com/api/docs/guides/custom-mcp-server) e [disponibilità e developer mode MCP](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).

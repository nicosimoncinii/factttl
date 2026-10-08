# FactTTL sotto le risposte ChatGPT

Estensione locale per **Firefox, Chrome o Edge desktop**, con un interruttore indipendente
per ogni conversazione e badge accanto ai riferimenti dell'assistente. Non serve
menzionare `@FactTTL`. Ogni chat parte disattivata: attivandola autorizzi il
controllo delle risposte presenti e delle successive risposte in quella chat.

## Prima prova su Firefox

1. In Firefox apri `about:debugging#/runtime/this-firefox`. Premi **Carica
   componente aggiuntivo temporaneo** e seleziona il file `manifest.json` in
   `integrations/firefox-extension`, il pacchetto specifico generato con
   `node integrations/build-firefox.mjs`. Il manifest condiviso in questa
   cartella contiene anche proprietà Chromium che Firefox può segnalare come
   sconosciute; usa il pacchetto Firefox. Servono Firefox 121 o successivo;
   questa installazione di
   sviluppo viene rimossa quando riavvii Firefox.

2. Apri le **Opzioni** di FactTTL in `about:addons` o premi l'icona di FactTTL
   nella barra del browser. La pagina mostra **Origine di questa estensione**,
   per esempio `moz-extension://<identificatore-assegnato-da-Firefox>`. Premi
   **Copia origine**. È un identificatore pubblico, non un token.

3. Avvia il servizio locale dalla cartella del progetto autorizzando esattamente
   l'origine appena copiata:

   ```powershell
   .venv\Scripts\python.exe -m factttl.browser_bridge --extension-origin "moz-extension://IDENTIFICATORE-MOSTRATO-NELLE-OPZIONI"
   ```

   Se il servizio è già aperto con l'origine di Chrome, fermalo prima e
   riavvialo con l'origine Firefox. Non modificare le preferenze di firma di
   Firefox e non autorizzare origini generiche.

4. Nelle opzioni premi **Collega questo browser** e scegli il file
   `.factttl/extension-config.json` appena generato. Dopo il collegamento, apri
   [ChatGPT](https://chatgpt.com) **in Firefox**, accedi al tuo account e ricarica
   la pagina. Apri una conversazione e attiva FactTTL con l'interruttore.

L'ID del componente è `factttl-local@factttl.dev`; l'origine `moz-extension://`
è assegnata da Firefox e non è lo stesso ID. Una distribuzione persistente per
tutti richiederà il pacchetto firmato; la prova temporanea descritta qui non lo
sostituisce. Se Firefox cambia l'origine durante una nuova installazione, copia
la nuova origine dalle opzioni e riavvia il servizio con quella esatta.

## Motore locale per le notizie su Windows

Il setup scarica un runtime Ollama ufficiale verificato con SHA256 e il modello
locale `qwen3:4b` nella cartella ignorata `.factttl/runtime`. Richiede Windows
x64, PowerShell 7.4 e almeno 10 GB liberi durante l'installazione. Non modifica
PATH o servizi Windows e disabilita il cloud nel processo locale.

```powershell
./scripts/Setup-FactTTL-News.ps1
./scripts/Start-FactTTL-Browser.ps1 -NewsModel qwen3:4b
```

Se il bridge era già attivo senza modello, riavvialo prima di applicare la
configurazione. Gli avvii successivi leggono il modello salvato e riavviano il
runtime già installato senza download. Le impostazioni distinguono il modello
configurato da quello disponibile nel servizio locale.

L'analisi confronta l'affermazione con il testo della fonte e richiede citazioni
presenti in quel testo. Fonti bloccate, citazioni mancanti e timeout restano
inconcludenti. Il confronto resta riferito alle prove raccolte. La ricerca di
altre fonti usa l'opzione separata `-NewsDiscovery bing`: invia a Bing una breve
query sul tema, anche per alcune affermazioni pubbliche senza URL. È disattivata
per impostazione predefinita; la presenza di più domini non prova indipendenza.

## Prima prova su Chrome o Edge

1. Avvia il servizio locale dalla cartella del progetto:

   ```powershell
   .venv\Scripts\python.exe -m factttl.browser_bridge
   ```

   Il servizio ascolta solo su `127.0.0.1:8765` e genera il token locale di
   collegamento. Mantieni aperto il servizio durante la prova. Il database locale
   `.factttl/verification.sqlite3` conserva i controlli e le correzioni.

2. In Chrome apri `chrome://extensions`; in Edge apri `edge://extensions`.
   Attiva **Modalità sviluppatore**, premi **Carica estensione non pacchettizzata**
   e seleziona questa cartella:

   ```text
   <cartella-del-progetto>\integrations\chatgpt-extension
   ```

3. L'ID previsto è `nfnnmjcbjidblifbdfkhbdiidgcjbiem`. Apri le **Opzioni**
   dell'estensione o premi la sua icona nella barra del browser. Premi **Importa
   configurazione locale** e seleziona `.factttl/extension-config.json`, generato
   dal servizio. In alternativa, incolla il suo token e premi **Salva e verifica**.
   È un token FactTTL, non una chiave API OpenAI. Non condividere il file di
   configurazione: contiene il token locale.

4. Apri [ChatGPT](https://chatgpt.com) nello **stesso Chrome o Edge**, accedi con il
   tuo account e ricarica la pagina se era già aperta. Apri una conversazione e
   attiva **FactTTL**. I badge compaiono sotto le risposte completate; premi un
   badge per vedere prove, prezzi osservati e limiti del controllo.

5. Per fermare i controlli in quella chat, disattiva l'interruttore. Le richieste
   in coda vengono fermate e i risultati in arrivo non vengono mostrati. Il servizio
   controlla l'annullamento prima di avviare altri controlli e prima di salvare
   ciascun risultato. Una richiesta a una fonte già iniziata può terminare; un
   controllo che ha superato il punto di salvataggio appena prima dell'annullamento
   può comunque finire nella memoria locale. I controlli già conclusi restano salvati.

L'estensione non è installata automaticamente nel browser integrato di Codex e
non cambia l'app desktop ChatGPT. Questa prova richiede un browser desktop e
il caricamento locale descritto sopra. Non è ancora una pubblicazione sullo store.

## Cosa controlla

La UI segnala le prove raccolte per URL, disponibilità e prezzi esplicitamente
riconosciuti. Un badge positivo riguarda i controlli effettuati e **non certifica
l'intera risposta**. CAPTCHA, accesso negato, claim non riconosciuti e mancanza
di prove producono risultati inconcludenti o parziali.

Le correzioni sono conservate da FactTTL. Con **Memoria attiva**, al tuo prossimo
invio lo strumento allega alla bozza un blocco visibile con i controlli pertinenti:
affermazione precedente, valore osservato, fonte e scadenza. Questo permette al
modello di ricevere la correzione anche in una nuova chat attivata. Non modifica
la memoria interna del provider e non invia messaggi da solo. Spegnere la memoria
o FactTTL rimuove un suo allegato ancora nella bozza; un allegato modificato va
rimosso manualmente prima dell'invio con lo strumento spento. Puoi anche usare
**Copia la correzione per la chat**. Dettagli in [prompt memory](../../docs/prompt-memory.md).

Per un link prodotto Amazon, il lettore può aprire una scheda inattiva e leggere
l'offerta principale nel browser: prezzo, disponibilità e prezzo di riferimento
se presente. La scheda viene chiusa dopo il controllo. Venditori e varianti
restano distinti; lo strumento non effettua acquisti né aggira CAPTCHA.

## Dati e accesso

- Il controllo legge le risposte dell'assistente nelle chat attive. La memoria
  legge la bozza solo per preparare il tuo invio quando è attivata.
- Testo e link vengono inviati al servizio FactTTL sul tuo PC; il servizio può
  consultare le fonti web indicate per verificarli.
- Il token rimane nello storage locale limitato ai contesti fidati. Su Firefox
  senza quell'API, il token viene conservato in IndexedDB sull'origine privata
  dell'estensione; non viene salvato nello storage accessibile al content script.
  Le preferenze delle chat sono locali. Lo script della pagina non riceve il token.
- Il trasporto dei controlli usa soltanto `http://127.0.0.1:8765`, non endpoint
  scelti dalle pagine. Nessun cookie o credenziale di ChatGPT/Amazon viene
  inoltrato al bridge. Il lettore Amazon usa la normale sessione del browser
  sui sei marketplace autorizzati; invia al bridge solo i campi dell'offerta.
- Al tuo invio, il provider della chat riceve anche il blocco delle verifiche
  pertinenti quando la memoria è attiva. Non vengono allegati HTML o citazioni
  integrali delle fonti. Vedi [privacy](../../docs/privacy-and-network.md).
- Le opzioni e gli script sono locali; non viene caricato codice remoto.

Le verifiche passano attraverso job locali con risposte HTTP immediate e polling
progressivo. Non dipendono da una singola richiesta HTTP lunga: ciascuna richiesta
ha un limite di 10 secondi e il controllo complessivo di 90 secondi. L'annullamento
del job è cooperativo; se il servizio è irraggiungibile viene tentato per 3 secondi.
Se la connessione si interrompe proprio mentre il servizio sta creando un job e la
risposta con il suo identificativo va persa, il job potrebbe non poter essere
annullato dal browser e restare attivo fino alla scadenza locale (massimo 5 minuti).

L'origine autorizzata su Chrome/Edge è
`chrome-extension://nfnnmjcbjidblifbdfkhbdiidgcjbiem`; su Firefox si usa quella
esatta mostrata nelle opzioni. La chiave **pubblica** nel
manifest mantiene stabile l'ID durante lo sviluppo; non contiene un segreto.
Puoi ricalcolarlo dalla cartella dell'estensione:

```powershell
node -e "const c=require('node:crypto');const m=require('./manifest.json');const h=c.createHash('sha256').update(Buffer.from(m.key,'base64')).digest('hex').slice(0,32);console.log(Array.from(h,x=>String.fromCharCode(97+parseInt(x,16))).join(''));"
```

Il manifest usa Manifest V3. Il content script gira su ChatGPT, Claude e Gemini
(`chatgpt.com`, `claude.ai`, `gemini.google.com`) in Chrome, Edge e Firefox.
Riferimenti: [caricare un'estensione locale](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world#load-unpacked),
[ID stabile](https://developer.chrome.com/docs/extensions/reference/manifest/key),
[storage e accesso dei content script](https://developer.chrome.com/docs/extensions/reference/api/storage).

Compatibilità Firefox: [background cross-browser](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background),
[caricamento temporaneo](https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/),
[livelli di accesso dello storage](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/StorageArea/setAccessLevel).

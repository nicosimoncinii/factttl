# Pacchetto locale e distribuzione

## Pacchetto per la prova

Dalla cartella del progetto, in PowerShell 7:

```powershell
./integrations/chatgpt-extension/build-package.ps1 -Browser Firefox
./integrations/chatgpt-extension/build-package.ps1 -Browser Chromium
```

I pacchetti vengono creati in `dist`, con versione e browser nel nome. Se un
pacchetto esiste già, specifica un nuovo `-OutputPath` dentro il progetto. Lo
script non sovrascrive archivi esistenti.

Il pacchetto Firefox contiene il manifest specifico Gecko e ha estensione
`.xpi`; quello Chromium contiene il manifest specifico Chromium e ha estensione
`.zip`. Entrambi includono `item-ui.js` e gli altri moduli runtime. Sono esclusi
test, demo, token, database e configurazioni locali. La chiave pubblica del
manifest Chromium non è un segreto.

**Questi sono pacchetti di prova non firmati.** Il file Firefox può essere
caricato temporaneamente tramite `about:debugging#/runtime/this-firefox`;
un'estensione temporanea viene rimossa al riavvio. Per Chrome/Edge, estrai il
pacchetto e usa il caricamento non pacchettizzato in modalità sviluppatore.
Il servizio locale FactTTL deve essere avviato separatamente.

## Installazione persistente per tutti

Per Firefox release serve la firma Mozilla, sia per una pubblicazione sullo
store sia per distribuire un pacchetto non elencato. La firma passa attraverso
AMO e la sua validazione: il pacchetto locale generato qui non la sostituisce.
[Documentazione Mozilla su firma e distribuzione](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/).

La fase di pubblicazione richiede l'account Mozilla del proprietario, il consenso
alle condizioni di distribuzione, la dichiarazione dei dati trattati e la scelta
tra distribuzione pubblica o non elencata. Le credenziali di firma non vanno
inserite nel codice, nel pacchetto o nel file di configurazione locale.

L'installazione definitiva dovrà anche predisporre il servizio locale e la sua
origine autorizzata, offrire avvio/arresto e aggiornamenti e collegare il token
senza mostrarlo nella chat. Non modificare le preferenze di verifica delle firme
per simulare una distribuzione definitiva.

Paese e lingua selezionati dall'utente sono preferenze di ricerca e lettura.
Non attestano la posizione GPS, l'indirizzo di consegna o le condizioni di un
account Amazon. Un risultato deve conservare il contesto in cui è stato ottenuto.

# Valutazione automatica delle notizie con un modello locale

## Che cosa valuta

Il modulo `factttl.semantic_provider` implementa un adattatore Ollama funzionante.
Confronta una singola affermazione con il testo di una singola fonte appena
recuperata dal fetcher protetto. `SUPPORTED` indica che il modello giudica la
fonte coerente con l'affermazione; `CONTRADICTED` indica una contraddizione
esplicita nella fonte. Il risultato descrive **la coerenza con quella fonte**.
Non dimostra indipendentemente che la fonte o la notizia siano vere.

Data recente, HTTP 200 e titolo non sono prove sufficienti. Una citazione deve
comparire nel corpo del testo letto live: solo gli spazi vengono normalizzati.
Schema non valido, assenza di citazioni per un verdetto conclusivo, runtime non
disponibile o timeout producono `INCONCLUSIVE`.

Paese e lingua orientano interpretazione e recupero. Il paese dichiarato non
dimostra la posizione dell'utente. Affermazione e fonte sono dati non fidati;
il modello non riceve strumenti per navigare, eseguire codice o seguire i link.

## Attivazione esplicita

Per preparare il motore sul proprio PC Windows x64 con PowerShell 7.4 o
successivo, lo script di setup scarica **esplicitamente** runtime e modello:

```powershell
.\scripts\Setup-FactTTL-News.ps1
.\scripts\Start-FactTTL-Browser.ps1 -NewsModel qwen3:4b
```

Il profilo predefinito `balanced` richiede 8.192 token di contesto. Per usare
esplicitamente la CPU aggiungi `-InferenceProfile cpu`; non è obbligatoria una
GPU. Hardware e misure reali sono descritti in
[limiti del motore locale](../../docs/local-engine-hardware.md).

## Ricerca facoltativa di fonti

La ricerca è disattivata per impostazione predefinita. Per attivarla:

```powershell
.\scripts\Start-FactTTL-Browser.ps1 -NewsModel qwen3:4b -NewsDiscovery bing
```

Il bridge invia a Bing RSS una query limitata ricavata dall'affermazione e usa
paese e lingua come contesto. Non invia l'intera conversazione come query, ma
il testo ricavato può comunque contenere informazioni personali: il filtro
non garantisce l'eliminazione di dati privati. Leggi
[privacy e rete](../../docs/privacy-and-network.md) prima di attivarlo.

I risultati indicano URL candidati. Il controllo legge i corpi pubblici delle
fonti tramite il fetcher protetto e analizza localmente i testi: titolo e snippet
RSS non sono prove. Più domini non garantiscono fonti realmente indipendenti.
Fonti mancanti, ambigue o discordanti devono restare inconcludenti.
Usa `-NewsDiscovery disabled` per disattivare la ricerca. La scelta viene salvata
localmente; un bridge già attivo va riavviato per applicare il cambiamento.
`-DisableNews` disattiva sia l'analisi locale sia la ricerca esterna, anche se
in precedenza era stato salvato Bing come provider.

Il runtime standalone ufficiale Ollama v0.40.0 e Qwen3:4b sono conservati in
`.factttl/runtime`, esclusa da Git. Il setup verifica lo SHA256 pubblicato per
l'archivio, conserva i modelli nel progetto e avvia un processo nascosto con
`OLLAMA_NO_CLOUD=1`. Non modifica PATH, registro, servizi Windows o avvio
automatico. L'archivio già estratto viene eliminato per recuperare spazio.
È richiesto almeno 10 GB liberi durante il setup. Qwen3:4b occupa circa 2.5 GB
e usa licenza Apache 2.0, indicata nella
[scheda ufficiale del modello](https://ollama.com/library/qwen3:4b).

Per riavviare il runtime già installato senza download:

```powershell
.\scripts\Setup-FactTTL-News.ps1 -StartOnly
```

È necessario Ollama già avviato sul PC, con un modello locale già installato
che supporti output strutturati e `think: false`. L'adattatore usa esclusivamente
`http://127.0.0.1:11434`; non scarica modelli, non usa chiavi API, non seleziona un
modello automaticamente e non configura il cloud.

Per configurare un modello **già presente** nella sessione PowerShell:

```powershell
$env:FACTTTL_NEWS_MODEL = "NOME_DEL_MODELLO_LOCALE_GIA_INSTALLATO"
python -m factttl.browser_bridge
```

Il servizio accetta anche `--news-model NOME_DEL_MODELLO_LOCALE_GIA_INSTALLATO`.
Il nome deve corrispondere al modello locale scelto dall'utente. Senza
configurazione non parte alcuna richiesta Ollama e le notizie restano
inconcludenti. Configurazione presente non significa che runtime e modello siano
effettivamente disponibili; il primo utilizzo controlla il servizio.

Prima di inviare affermazione e testo, `/api/show` deve riportare un modello GGUF
con metadati di architettura locali, senza `remote_host` o `remote_model`.
I nomi cloud e gli URL sono rifiutati. Anche la risposta finale viene controllata
per metadati remoti. Si assume che il daemon Ollama locale sia affidabile;
l'adattatore non controlla altri processi o le loro connessioni di rete.

## API dell'adattatore

```python
from factttl.semantic_provider import assess_news_claim

assessment = assess_news_claim(
    claim_text=claim,
    source_text=fetched_body,
    source_url=final_source_url,
    source_observed_at=actual_fetch_timestamp,
    language="it",
    country="IT",
)
```

Limiti:

- Affermazione: 4.000 caratteri; corpo della fonte: 12.000 caratteri.
- Una fonte HTTPS già recuperata; nessun secondo fetch nel provider.
- Istante di recupero con timezone obbligatorio, massimo 300 secondi di età;
  controllato anche dopo l'inferenza.
- Massimo tre citazioni, ciascuna da 20 a 1.000 caratteri; razionale massimo 2.000.
- Schema rigoroso, senza campi aggiuntivi, chiavi JSON duplicate o valori non
  finiti. Gli URL delle citazioni vengono assegnati dal codice, mai dal modello.
- Il verdetto viene scelto dopo prove e spiegazione; conflitti espliciti tra
  spiegazione ed etichetta fanno astenere il provider. Questo controllo non
  costituisce una seconda verifica semantica indipendente.
- Risposta HTTP massima 1 MiB e scadenza complessiva di 60 secondi, compreso il
  controllo preliminare. Nessun redirect o proxy.
- Profili limitati: `cpu` e `balanced` richiedono 8.192 token; `extended` richiede
  32.768 token solo se scelto esplicitamente. Il budget UTF-8 include istruzioni
  e schema: un input troppo grande produce astensione. Gli estratti limitati
  conservano l'indicazione che il corpo completo non è stato valutato. Memoria
  e latenza dipendono dal modello e dall'hardware.

Paesi accettati: IT, US, GB, DE, FR, ES. Lingue: it, en, de, fr, es.

Il risultato contiene `outcome`, `rationale`, `citations`,
`scope="current_source_consistency"`, `provider="ai_assessed_live_source"`,
`engine`, `configured`, `model`, `source_observed_at` e `limitation`.
Una citazione restituita ha `source_id="source-1"`, `quote` e `source_url`.
In caso di astensione tecnica è presente un codice limitato `error_reason`;
il corpo degli errori del daemon non viene esposto.

## Prove e riuso

Il chiamante conserva URL, istante reale di lettura, citazioni, nome del modello,
ambito e limite della valutazione. Controlla di nuovo le citazioni prima di
registrare un risultato definitivo. Il confronto usa lo stesso testo live
fornito al modello, senza aggiungere una nuova richiesta HTTP.

Una correzione precedente non viene cancellata da un risultato inconcludente.
Il riuso deve rispettare il tempo di validità e conservare l'ambito: un giudizio
AI su una sola fonte non diventa una conferma indipendente della notizia.

## Riferimenti tecnici

L'implementazione segue [API chat Ollama](https://docs.ollama.com/api/chat),
[output strutturati](https://docs.ollama.com/capabilities/structured-outputs) e
[controlli thinking](https://docs.ollama.com/capabilities/thinking).
I [tipi ufficiali Ollama](https://github.com/ollama/ollama/blob/main/api/types.go)
documentano i campi di modello remoto controllati durante il preflight.
Ollama può usare modelli cloud anche attraverso il daemon locale: vedere
[documentazione cloud](https://docs.ollama.com/cloud).

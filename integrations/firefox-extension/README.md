# FactTTL per Firefox

Pacchetto generato con `node integrations/build-firefox.mjs`.

Carica questo `manifest.json` da `about:debugging#/runtime/this-firefox` usando **Carica componente aggiuntivo temporaneo**.

Apri le opzioni e copia l'origine `moz-extension://…` per collegare il servizio locale. Istruzioni complete in `../chatgpt-extension/README.md`.

Dopo modifiche ai sorgenti, rigenera il pacchetto e ricarica il componente in Firefox.

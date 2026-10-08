"use strict";

const extensionAPI = globalThis.browser || globalThis.chrome;
const extensionOrigin = extensionAPI?.runtime?.getURL("")?.replace(/\/$/, "") || "";
const copy = {
  it: {
    documentTitle: "FactTTL · Impostazioni", brandLabel: "FactTTL, inizio",
    localTag: "Elaborazione locale", eyebrow: "Il contesto cambia",
    headline: "Risposte più attente a ciò che cambia.",
    intro: "FactTTL controlla in locale alcune informazioni aggiornabili nelle risposte di ChatGPT, Claude e Gemini. Sei tu a decidere in quali conversazioni attivarlo.",
    stepOne: "Passo 1 · Collegamento", connectTitle: "Collega FactTTL",
    connectCopy: "Avvia FactTTL sul tuo computer, poi importa il file di configurazione che genera. Il file collega questo browser al servizio sul tuo PC.",
    connectButton: "Collega questo browser", retry: "Riprova il collegamento",
    checking: "Controllo in corso", connected: "Servizio collegato", offline: "Servizio non raggiungibile", notConfigured: "Da collegare",
    newsEngineTitle: "Controllo delle notizie", newsEngineMissing: "Motore locale non configurato", newsEngineReady: "Modello locale disponibile",
    newsEngineMissingNote: "Le notizie restano non verificate automaticamente. I controlli di link e prodotti possono continuare.",
    newsEngineReadyNote: "Disponibile per confrontare una notizia con la fonte letta. La valutazione raccoglie prove sulla fonte e non certifica la verità della notizia.",
    newsEngineUnknown: "Stato del motore non disponibile", newsEngineUnknownNote: "Il servizio è collegato, ma non comunica lo stato del controllo delle notizie.",
    newsEngineConfigured: "Modello configurato, disponibilità da verificare", newsEngineConfiguredNote: "La configurazione è salvata. Riavvia o aggiorna il servizio e riprova per verificarne la disponibilità.",
    newsEngineUnavailable: "Modello locale non ancora disponibile", newsEngineUnavailableNote: "Il servizio risponde, ma il modello non è disponibile. Avvia il motore locale o completa la preparazione, poi riprova.",
    extensionContext: "Apri le impostazioni dal pulsante FactTTL del browser. Questa pagina, aperta come file o sito, non può collegare l'estensione.",
    advancedTitle: "Problemi con il file? Usa il metodo manuale",
    advancedCopy: "Incolla il token locale mostrato dal servizio FactTTL. Non usare una chiave API OpenAI.",
    tokenLabel: "Token locale FactTTL", tokenPlaceholder: "Incolla il token locale", saveToken: "Salva token",
    originLabel: "Origine di questa estensione", copyOrigin: "Copia origine", originCopied: "Origine copiata", originCopyFallback: "Seleziona e copia l'origine mostrata sopra.",
    stepTwo: "Passo 2 · Preferenze", preferencesTitle: "Il tuo contesto",
    preferencesCopy: "Scegli paese e lingua da usare nei controlli. Sono preferenze modificabili, non una localizzazione automatica. Questa pagina segue la lingua scelta; i badge in chat sono per ora in italiano.",
    countryLabel: "Paese di riferimento", languageLabel: "Lingua dei controlli",
    preferencesNote: "La scelta iniziale si basa solo sulla lingua del browser. Puoi cambiarla quando vuoi.",
    savePreferences: "Salva preferenze", preferencesSaved: "Preferenze salvate sul dispositivo.", preferencesError: "Non è stato possibile salvare le preferenze. Riprova.",
    stepThree: "Passo 3 · Nelle chat", previewTitle: "Tu mantieni il controllo",
    previewCopy: "Apri una conversazione su ChatGPT, Claude o Gemini e attiva FactTTL con l'interruttore. Puoi spegnerlo in qualsiasi momento.",
    browserNote: "Funziona in Chrome, Edge e Firefox. Attivalo solo nella conversazione che stai leggendo.",
    sampleAnswer: "Esempio di un risultato", sampleText: "Il controllo riguarda solo le informazioni e le fonti esaminate. Il resto della risposta potrebbe non essere verificato.",
    sampleBadge: "Verifica parziale", sampleNote: "Un badge descrive le prove raccolte: non certifica tutta la risposta.",
    correctionCopy: "Con Memoria attiva, le verifiche pertinenti vengono allegate al messaggio che scegli di inviare. Il modello vede prezzi, disponibilità e correzioni con la loro scadenza. Puoi spegnere la memoria nella chat.",
    footerLocal: "Token e risultati sono salvati localmente; per verificare i link FactTTL contatta le fonti.", projectLink: "Progetto open source",
    connectedMessage: "Il servizio sul computer risponde. Attiva FactTTL solo nelle conversazioni che scegli.",
    offlineMessage: "Avvia il servizio FactTTL sul computer e riprova.", missingMessage: "Importa il file creato dal servizio FactTTL per collegare questo browser.",
    genericError: "Non è stato possibile completare l'operazione. Riprova.", tokenError: "Il token locale non è valido.", authError: "Il token non corrisponde. Importa di nuovo il file di configurazione.",
    configError: "File di configurazione non valido. Seleziona quello generato da FactTTL.", originMismatch: "Questo file appartiene a un'altra estensione. Copia l'origine qui sotto, autorizzala nel servizio FactTTL e importa il nuovo file.",
    extensionError: "Impossibile comunicare con l'estensione. Ricarica la pagina e riprova.",
    countries: {IT: "Italia", US: "Stati Uniti", GB: "Regno Unito", DE: "Germania", FR: "Francia", ES: "Spagna"},
  },
  en: {
    documentTitle: "FactTTL · Settings", brandLabel: "FactTTL, home",
    localTag: "Local processing", eyebrow: "Context changes",
    headline: "Answers that pay attention to what changes.",
    intro: "FactTTL checks some changeable details in ChatGPT, Claude, and Gemini answers locally. You choose which conversations to turn it on for.",
    stepOne: "Step 1 · Connection", connectTitle: "Connect FactTTL",
    connectCopy: "Start FactTTL on your computer, then import the configuration file it creates. The file connects this browser to the service on your PC.",
    connectButton: "Connect this browser", retry: "Check connection again",
    checking: "Checking connection", connected: "Service connected", offline: "Service unavailable", notConfigured: "Not connected",
    newsEngineTitle: "News checks", newsEngineMissing: "Local model not configured", newsEngineReady: "Local model available",
    newsEngineMissingNote: "News remain unchecked automatically. Link and product checks can still run.",
    newsEngineReadyNote: "Available to compare a news claim with the source it reads. The assessment gathers source evidence and does not certify the claim's truth.",
    newsEngineUnknown: "Engine status unavailable", newsEngineUnknownNote: "The service is connected but did not report the news-check status.",
    newsEngineConfigured: "Model configured, availability unconfirmed", newsEngineConfiguredNote: "The configuration is saved. Restart or update the service, then check availability again.",
    newsEngineUnavailable: "Local model not available yet", newsEngineUnavailableNote: "The service responds but the model is unavailable. Start the local engine or finish its preparation, then try again.",
    extensionContext: "Open settings from the FactTTL browser button. This page cannot connect the extension when opened as a file or website.",
    advancedTitle: "Having trouble with the file? Connect manually",
    advancedCopy: "Paste the local token shown by the FactTTL service. Do not use an OpenAI API key.",
    tokenLabel: "FactTTL local token", tokenPlaceholder: "Paste the local token", saveToken: "Save token",
    originLabel: "This extension's origin", copyOrigin: "Copy origin", originCopied: "Origin copied", originCopyFallback: "Select and copy the origin shown above.",
    stepTwo: "Step 2 · Preferences", preferencesTitle: "Your context",
    preferencesCopy: "Choose a country and language for checks. These are editable preferences, not automatic location detection. This page follows your choice; chat badges are currently in Italian.",
    countryLabel: "Reference country", languageLabel: "Language for checks",
    preferencesNote: "The initial choice uses only your browser language. Change it whenever you like.",
    savePreferences: "Save preferences", preferencesSaved: "Preferences saved on this device.", preferencesError: "Preferences could not be saved. Try again.",
    stepThree: "Step 3 · In chat", previewTitle: "You stay in control",
    previewCopy: "Open a conversation in ChatGPT, Claude, or Gemini and switch FactTTL on. You can turn it off at any time.",
    browserNote: "Works in Chrome, Edge, and Firefox. Turn it on only in the conversation you are reading.",
    sampleAnswer: "Example result", sampleText: "The check covers only the details and sources it examined. The rest of the answer may not be verified.",
    sampleBadge: "Partially checked", sampleNote: "A badge describes the evidence collected; it does not certify the whole answer.",
    correctionCopy: "With Memory enabled, relevant findings are attached to the message you choose to send. The model sees prices, stock and corrections with their expiry. You can turn memory off in the chat.",
    footerLocal: "Your token and results are stored locally; FactTTL contacts sources to check links.", projectLink: "Open source project",
    connectedMessage: "The service on your computer is responding. Turn FactTTL on only in conversations you choose.",
    offlineMessage: "Start the FactTTL service on your computer and try again.", missingMessage: "Import the file created by FactTTL to connect this browser.",
    genericError: "The operation could not be completed. Try again.", tokenError: "The local token is invalid.", authError: "The token does not match. Import the configuration file again.",
    configError: "Invalid configuration file. Select the one created by FactTTL.", originMismatch: "This file belongs to another extension. Copy the origin below, allow it in FactTTL, then import the new file.",
    extensionError: "Could not contact the extension. Reload this page and try again.",
    countries: {IT: "Italy", US: "United States", GB: "United Kingdom", DE: "Germany", FR: "France", ES: "Spain"},
  },
  de: {
    documentTitle: "FactTTL · Einstellungen", brandLabel: "FactTTL, Startseite",
    localTag: "Lokale Verarbeitung", eyebrow: "Kontext ändert sich",
    headline: "Antworten, die Veränderungen im Blick behalten.",
    intro: "FactTTL prüft bestimmte veränderliche Angaben in ChatGPT-, Claude- und Gemini-Antworten lokal. Du entscheidest, in welchen Unterhaltungen du es aktivierst.",
    stepOne: "Schritt 1 · Verbindung", connectTitle: "FactTTL verbinden",
    connectCopy: "Starte FactTTL auf deinem Computer und importiere anschließend die erstellte Konfigurationsdatei. Sie verbindet diesen Browser mit dem Dienst auf deinem PC.",
    connectButton: "Diesen Browser verbinden", retry: "Verbindung erneut prüfen",
    checking: "Verbindung wird geprüft", connected: "Dienst verbunden", offline: "Dienst nicht erreichbar", notConfigured: "Nicht verbunden",
    newsEngineTitle: "Nachrichtenprüfung", newsEngineMissing: "Lokales Modell nicht eingerichtet", newsEngineReady: "Lokales Modell verfügbar",
    newsEngineMissingNote: "Nachrichten bleiben automatisch ungeprüft. Links und Produktangaben können weiterhin geprüft werden.",
    newsEngineReadyNote: "Vergleicht eine Nachricht mit ihrer Quelle; bestätigt nicht, dass sie wahr ist.",
    newsEngineUnknown: "Modellstatus nicht verfügbar", newsEngineUnknownNote: "Der Dienst ist verbunden, hat aber keinen Status zur Nachrichtenprüfung gemeldet.",
    newsEngineConfigured: "Modell eingerichtet, Verfügbarkeit unbestätigt", newsEngineConfiguredNote: "Die Konfiguration ist gespeichert. Starte oder aktualisiere den Dienst und prüfe erneut.",
    newsEngineUnavailable: "Lokales Modell noch nicht verfügbar", newsEngineUnavailableNote: "Der Dienst antwortet, aber das Modell ist nicht verfügbar. Starte den lokalen Motor oder schließe die Vorbereitung ab und versuche es erneut.",
    extensionContext: "Öffne die Einstellungen über die FactTTL-Schaltfläche im Browser. Als Datei oder Website kann diese Seite die Erweiterung nicht verbinden.",
    advancedTitle: "Probleme mit der Datei? Manuell verbinden", advancedCopy: "Füge das lokale Token aus dem FactTTL-Dienst ein. Verwende keinen OpenAI-API-Schlüssel.",
    tokenLabel: "FactTTL-Token", tokenPlaceholder: "Lokales Token einfügen", saveToken: "Token speichern",
    originLabel: "Herkunft dieser Erweiterung", copyOrigin: "Herkunft kopieren", originCopied: "Herkunft kopiert", originCopyFallback: "Wähle die oben angezeigte Herkunft aus und kopiere sie.",
    stepTwo: "Schritt 2 · Einstellungen", preferencesTitle: "Dein Kontext", preferencesCopy: "Wähle Land und Sprache für die Prüfungen. Die Einstellungen sind änderbar; es gibt keine automatische Standortbestimmung. Diese Seite folgt deiner Wahl, Chat-Badges sind derzeit auf Italienisch.",
    countryLabel: "Referenzland", languageLabel: "Sprache der Prüfungen", preferencesNote: "Die Vorauswahl basiert nur auf der Browsersprache. Du kannst sie jederzeit ändern.",
    savePreferences: "Einstellungen speichern", preferencesSaved: "Einstellungen auf diesem Gerät gespeichert.", preferencesError: "Einstellungen konnten nicht gespeichert werden. Versuch es erneut.",
    stepThree: "Schritt 3 · Im Chat", previewTitle: "Du behältst die Kontrolle", previewCopy: "Öffne eine Unterhaltung in ChatGPT, Claude oder Gemini und schalte FactTTL ein. Du kannst es jederzeit ausschalten.",
    browserNote: "Funktioniert in Chrome, Edge und Firefox. Aktiviere es nur in der Unterhaltung, die du gerade liest.",
    sampleAnswer: "Beispiel für ein Ergebnis", sampleText: "Die Prüfung umfasst nur die untersuchten Angaben und Quellen. Der Rest der Antwort ist möglicherweise ungeprüft.", sampleBadge: "Teilweise geprüft", sampleNote: "Ein Badge beschreibt die gesammelten Belege und bestätigt nicht die gesamte Antwort.",
    correctionCopy: "Bei aktivem Speicher werden relevante Prüfungen an deine gesendete Nachricht angehängt. Das Modell sieht Preise, Verfügbarkeit und Korrekturen mit Ablaufdatum. Du kannst den Speicher im Chat ausschalten.",
    footerLocal: "Token und Ergebnisse werden lokal gespeichert; zum Prüfen von Links kontaktiert FactTTL die Quellen.", projectLink: "Open-Source-Projekt", connectedMessage: "Der Dienst auf deinem Computer ist erreichbar. Aktiviere FactTTL nur in ausgewählten Unterhaltungen.",
    offlineMessage: "Starte den FactTTL-Dienst auf deinem Computer und versuche es erneut.", missingMessage: "Importiere die von FactTTL erstellte Datei, um diesen Browser zu verbinden.", genericError: "Der Vorgang konnte nicht abgeschlossen werden. Versuch es erneut.",
    tokenError: "Das lokale Token ist ungültig.", authError: "Das Token stimmt nicht überein. Importiere die Konfigurationsdatei erneut.", configError: "Ungültige Konfigurationsdatei. Wähle die von FactTTL erstellte Datei.",
    originMismatch: "Diese Datei gehört zu einer anderen Erweiterung. Kopiere die Herkunft unten, gib sie in FactTTL frei und importiere die neue Datei.", extensionError: "Die Erweiterung ist nicht erreichbar. Lade diese Seite neu und versuche es erneut.",
    countries: {IT: "Italien", US: "Vereinigte Staaten", GB: "Vereinigtes Königreich", DE: "Deutschland", FR: "Frankreich", ES: "Spanien"},
  },
  fr: {
    documentTitle: "FactTTL · Paramètres", brandLabel: "FactTTL, accueil",
    localTag: "Traitement local", eyebrow: "Le contexte évolue",
    headline: "Des réponses attentives à ce qui change.",
    intro: "FactTTL vérifie localement certaines informations susceptibles d'évoluer dans les réponses de ChatGPT, Claude et Gemini. Vous choisissez les conversations où l'activer.",
    stepOne: "Étape 1 · Connexion", connectTitle: "Connecter FactTTL",
    connectCopy: "Lancez FactTTL sur votre ordinateur, puis importez le fichier de configuration créé. Il contient une connexion locale, pas une clé API.",
    connectButton: "Connecter ce navigateur", retry: "Vérifier à nouveau",
    checking: "Vérification en cours", connected: "Service connecté", offline: "Service inaccessible", notConfigured: "Non connecté",
    newsEngineTitle: "Vérification des actualités", newsEngineMissing: "Modèle local non configuré", newsEngineReady: "Modèle local disponible",
    newsEngineMissingNote: "Les actualités restent non vérifiées automatiquement. Les liens et les produits peuvent toujours être contrôlés.",
    newsEngineReadyNote: "Compare une actualité à sa source, sans certifier qu'elle est vraie.",
    newsEngineUnknown: "État du modèle indisponible", newsEngineUnknownNote: "Le service est connecté, mais n'a pas indiqué l'état de vérification des actualités.",
    newsEngineConfigured: "Modèle configuré, disponibilité à vérifier", newsEngineConfiguredNote: "La configuration est enregistrée. Redémarrez ou mettez à jour le service, puis vérifiez à nouveau.",
    newsEngineUnavailable: "Modèle local pas encore disponible", newsEngineUnavailableNote: "Le service répond, mais le modèle est indisponible. Démarrez le moteur local ou terminez sa préparation, puis réessayez.",
    extensionContext: "Ouvrez les paramètres depuis le bouton FactTTL du navigateur. Cette page ne peut pas connecter l'extension lorsqu'elle est ouverte comme fichier ou site web.",
    advancedTitle: "Un problème avec le fichier ? Connexion manuelle", advancedCopy: "Collez le jeton local affiché par FactTTL. N'utilisez pas de clé API OpenAI.",
    tokenLabel: "Jeton local FactTTL", tokenPlaceholder: "Coller le jeton local", saveToken: "Enregistrer le jeton",
    originLabel: "Origine de cette extension", copyOrigin: "Copier l'origine", originCopied: "Origine copiée", originCopyFallback: "Sélectionnez et copiez l'origine affichée ci-dessus.",
    stepTwo: "Étape 2 · Préférences", preferencesTitle: "Votre contexte", preferencesCopy: "Choisissez un pays et une langue pour les vérifications. Ce sont des préférences modifiables, sans géolocalisation automatique. Cette page suit votre choix ; les badges du chat sont actuellement en italien.",
    countryLabel: "Pays de référence", languageLabel: "Langue des vérifications", preferencesNote: "Le choix initial dépend uniquement de la langue du navigateur. Vous pouvez le modifier à tout moment.",
    savePreferences: "Enregistrer les préférences", preferencesSaved: "Préférences enregistrées sur cet appareil.", preferencesError: "Impossible d'enregistrer les préférences. Réessayez.",
    stepThree: "Étape 3 · Dans le chat", previewTitle: "Vous gardez le contrôle", previewCopy: "Ouvrez une conversation dans ChatGPT, Claude ou Gemini et activez FactTTL. Vous pouvez le désactiver à tout moment.",
    browserNote: "Fonctionne dans Chrome, Edge et Firefox. Activez-le uniquement dans la conversation que vous lisez.",
    sampleAnswer: "Exemple de résultat", sampleText: "Le contrôle porte uniquement sur les informations et les sources examinées. Le reste de la réponse peut ne pas être vérifié.", sampleBadge: "Vérification partielle", sampleNote: "Un badge décrit les éléments recueillis ; il ne certifie pas toute la réponse.",
    correctionCopy: "Avec la mémoire active, les vérifications pertinentes sont jointes au message que vous choisissez d'envoyer. Le modèle voit les prix, la disponibilité et les corrections avec leur expiration. Vous pouvez désactiver la mémoire dans la conversation.",
    footerLocal: "Le jeton et les résultats sont enregistrés localement ; FactTTL contacte les sources pour vérifier les liens.", projectLink: "Projet open source", connectedMessage: "Le service sur votre ordinateur répond. Activez FactTTL uniquement dans les conversations de votre choix.",
    offlineMessage: "Lancez FactTTL sur votre ordinateur, puis réessayez.", missingMessage: "Importez le fichier créé par FactTTL pour connecter ce navigateur.", genericError: "L'opération n'a pas abouti. Réessayez.",
    tokenError: "Le jeton local est invalide.", authError: "Le jeton ne correspond pas. Importez à nouveau le fichier de configuration.", configError: "Fichier invalide. Sélectionnez celui généré par FactTTL.",
    originMismatch: "Ce fichier appartient à une autre extension. Copiez l'origine ci-dessous, autorisez-la dans FactTTL et importez le nouveau fichier.", extensionError: "Impossible de joindre l'extension. Rechargez cette page et réessayez.",
    countries: {IT: "Italie", US: "États-Unis", GB: "Royaume-Uni", DE: "Allemagne", FR: "France", ES: "Espagne"},
  },
  es: {
    documentTitle: "FactTTL · Ajustes", brandLabel: "FactTTL, inicio",
    localTag: "Procesamiento local", eyebrow: "El contexto cambia",
    headline: "Respuestas atentas a lo que cambia.",
    intro: "FactTTL comprueba localmente algunos datos que pueden cambiar en las respuestas de ChatGPT, Claude y Gemini. Tú decides en qué conversaciones activarlo.",
    stepOne: "Paso 1 · Conexión", connectTitle: "Conecta FactTTL",
    connectCopy: "Inicia FactTTL en tu ordenador e importa el archivo de configuración que genera. El archivo contiene una conexión local, no una clave API.",
    connectButton: "Conectar este navegador", retry: "Comprobar conexión otra vez",
    checking: "Comprobando conexión", connected: "Servicio conectado", offline: "Servicio no disponible", notConfigured: "Sin conectar",
    newsEngineTitle: "Comprobación de noticias", newsEngineMissing: "Modelo local no configurado", newsEngineReady: "Modelo local disponible",
    newsEngineMissingNote: "Las noticias seguirán sin comprobarse automáticamente. Se pueden seguir revisando enlaces y productos.",
    newsEngineReadyNote: "Compara una noticia con su fuente; no certifica que sea verdadera.",
    newsEngineUnknown: "Estado del modelo no disponible", newsEngineUnknownNote: "El servicio está conectado, pero no indicó el estado de comprobación de noticias.",
    newsEngineConfigured: "Modelo configurado, disponibilidad por confirmar", newsEngineConfiguredNote: "La configuración está guardada. Reinicia o actualiza el servicio y vuelve a comprobarlo.",
    newsEngineUnavailable: "Modelo local aún no disponible", newsEngineUnavailableNote: "El servicio responde, pero el modelo no está disponible. Inicia el motor local o termina su preparación y vuelve a intentarlo.",
    extensionContext: "Abre los ajustes desde el botón FactTTL del navegador. Esta página no puede conectar la extensión si se abre como archivo o sitio web.",
    advancedTitle: "¿Problemas con el archivo? Conecta manualmente", advancedCopy: "Pega el token local que muestra FactTTL. No uses una clave API de OpenAI.",
    tokenLabel: "Token local de FactTTL", tokenPlaceholder: "Pega el token local", saveToken: "Guardar token",
    originLabel: "Origen de esta extensión", copyOrigin: "Copiar origen", originCopied: "Origen copiado", originCopyFallback: "Selecciona y copia el origen que aparece arriba.",
    stepTwo: "Paso 2 · Preferencias", preferencesTitle: "Tu contexto", preferencesCopy: "Elige un país y un idioma para las comprobaciones. Son preferencias editables, no una detección automática de ubicación. Esta página sigue tu elección; las etiquetas del chat están actualmente en italiano.",
    countryLabel: "País de referencia", languageLabel: "Idioma de comprobación", preferencesNote: "La selección inicial se basa solo en el idioma del navegador. Puedes cambiarla cuando quieras.",
    savePreferences: "Guardar preferencias", preferencesSaved: "Preferencias guardadas en este dispositivo.", preferencesError: "No se pudieron guardar las preferencias. Inténtalo de nuevo.",
    stepThree: "Paso 3 · En el chat", previewTitle: "Tú tienes el control", previewCopy: "Abre una conversación en ChatGPT, Claude o Gemini y activa FactTTL. Puedes desactivarlo cuando quieras.",
    browserNote: "Funciona en Chrome, Edge y Firefox. Actívalo solo en la conversación que estás leyendo.",
    sampleAnswer: "Ejemplo de resultado", sampleText: "La comprobación solo cubre los datos y las fuentes examinados. Puede que el resto de la respuesta no esté verificado.", sampleBadge: "Comprobación parcial", sampleNote: "Una etiqueta describe las pruebas recopiladas; no certifica toda la respuesta.",
    correctionCopy: "Con la memoria activa, las verificaciones pertinentes se adjuntan al mensaje que decides enviar. El modelo ve precios, disponibilidad y correcciones con su caducidad. Puedes desactivar la memoria en el chat.",
    footerLocal: "El token y los resultados se guardan localmente; FactTTL contacta con las fuentes para comprobar enlaces.", projectLink: "Proyecto de código abierto", connectedMessage: "El servicio de tu ordenador responde. Activa FactTTL solo en las conversaciones que elijas.",
    offlineMessage: "Inicia el servicio FactTTL en tu ordenador e inténtalo de nuevo.", missingMessage: "Importa el archivo creado por FactTTL para conectar este navegador.", genericError: "No se pudo completar la operación. Inténtalo de nuevo.",
    tokenError: "El token local no es válido.", authError: "El token no coincide. Vuelve a importar el archivo de configuración.", configError: "Archivo no válido. Selecciona el archivo generado por FactTTL.",
    originMismatch: "Este archivo pertenece a otra extensión. Copia el origen de abajo, autorízalo en FactTTL e importa el nuevo archivo.", extensionError: "No se pudo contactar con la extensión. Recarga esta página e inténtalo de nuevo.",
    countries: {IT: "Italia", US: "Estados Unidos", GB: "Reino Unido", DE: "Alemania", FR: "Francia", ES: "España"},
  },
};

const form = document.getElementById("configuration");
const tokenInput = document.getElementById("token");
const statusElement = document.getElementById("status");
const importButton = document.getElementById("import-config");
const configFile = document.getElementById("config-file");
const originText = document.getElementById("extension-origin");
const copyOrigin = document.getElementById("copy-origin");
const connectionState = document.getElementById("connection-state");
const connectionLabel = document.getElementById("connection-label");
const newsEngineState = document.getElementById("news-engine-state");
const newsEngineLabel = document.getElementById("news-engine-label");
const newsEngineDescription = document.getElementById("news-engine-description");
const newsDiscoveryDescription = document.getElementById("news-discovery-description");
const preferencesForm = document.getElementById("preferences-form");
const countrySelect = document.getElementById("country");
const languageSelect = document.getElementById("language");
const preferencesStatus = document.getElementById("preferences-status");
let language = "it";
let reportedNewsEngine;
let hasNewsEngineStatus = false;

originText.textContent = extensionOrigin;

function t(key) {
  return copy[language][key] || copy.it[key] || key;
}

function renderLanguage() {
  document.documentElement.lang = language;
  document.title = t("documentTitle");
  document.querySelectorAll("[data-i18n]").forEach(element => {
    const key = element.dataset.i18n;
    if (copy[language][key]) element.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach(element => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
  for (const option of countrySelect.options) {
    option.textContent = t("countries")[option.value];
  }
  const stateKey = {
    checking: "checking", connected: "connected", offline: "offline", unconfigured: "notConfigured",
  }[connectionState.dataset.state] || "checking";
  connectionLabel.textContent = t(stateKey);
  if (hasNewsEngineStatus) renderNewsEngine(reportedNewsEngine);
}

function browserDefaults() {
  let locale;
  try { locale = new Intl.Locale(navigator.language || "it-IT"); }
  catch { locale = new Intl.Locale("it-IT"); }
  const knownCountries = new Set(["IT", "US", "GB", "DE", "FR", "ES"]);
  return {
    country: knownCountries.has(locale.region) ? locale.region : "IT",
    language: ["it", "en", "de", "fr", "es"].includes(locale.language) ? locale.language : "en",
  };
}

async function requestRuntime(message) {
  if (!extensionAPI?.runtime?.sendMessage) throw new Error("EXTENSION_CONTEXT");
  let timer;
  try {
    return await Promise.race([
      extensionAPI.runtime.sendMessage(message),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("EXTENSION_TIMEOUT")), 12000);
      }),
    ]);
  } finally { clearTimeout(timer); }
}

function show(message, tone = "") {
  statusElement.textContent = message;
  statusElement.dataset.tone = tone;
}

function connection(state, labelKey) {
  connectionState.dataset.state = state;
  connectionLabel.textContent = t(labelKey);
}

function renderNewsEngine(engine) {
  newsEngineState.hidden = false;
  const discoveryCopy = {
    it: ["Ricerca esterna Bing attivata: query sul tema sono inviate a Bing. I riassunti RSS non sono prove; leggiamo le fonti trovate. L’indipendenza delle fonti non è garantita.", "Ricerca esterna disattivata: confronto solo con i link forniti. Per attivarla sul PC usa Start-FactTTL-Browser.ps1 -NewsDiscovery bing e riavvia il servizio.", "Stato della ricerca esterna non disponibile."],
    en: ["External Bing search enabled: topic queries are sent to Bing. RSS snippets are not evidence; discovered sources are read. Source independence is not guaranteed.", "External search disabled: only supplied links are compared. Enable it with Start-FactTTL-Browser.ps1 -NewsDiscovery bing and restart the service.", "External search status unavailable."],
    de: ["Externe Bing-Suche aktiviert: Themenanfragen werden an Bing gesendet. RSS-Auszüge sind keine Belege; gefundene Quellen werden gelesen. Unabhängigkeit ist nicht garantiert.", "Externe Suche deaktiviert: nur angegebene Links werden verglichen. Aktivieren mit Start-FactTTL-Browser.ps1 -NewsDiscovery bing und Dienst neu starten.", "Status der externen Suche nicht verfügbar."],
    fr: ["Recherche Bing externe activée : les requêtes thématiques sont envoyées à Bing. Les extraits RSS ne sont pas des preuves ; les sources trouvées sont lues. Leur indépendance n’est pas garantie.", "Recherche externe désactivée : seuls les liens fournis sont comparés. Activer avec Start-FactTTL-Browser.ps1 -NewsDiscovery bing puis redémarrer le service.", "État de recherche externe indisponible."],
    es: ["Búsqueda externa Bing activada: las consultas temáticas se envían a Bing. Los extractos RSS no son pruebas; se leen las fuentes encontradas. Su independencia no está garantizada.", "Búsqueda externa desactivada: solo se comparan los enlaces proporcionados. Activar con Start-FactTTL-Browser.ps1 -NewsDiscovery bing y reiniciar el servicio.", "Estado de búsqueda externa no disponible."],
  };
  const discoveryState = engine?.discovery_provider === "bing" && engine.discovery_sends_query === true ? 0 : engine?.discovery_provider === "disabled" ? 1 : 2;
  newsDiscoveryDescription.textContent = discoveryCopy[language][discoveryState];
  if (!engine || typeof engine.configured !== "boolean") {
    newsEngineState.dataset.state = "unknown";
    newsEngineLabel.textContent = t("newsEngineUnknown");
    newsEngineDescription.textContent = t("newsEngineUnknownNote");
    return;
  }
  const state = !engine.configured ? "missing"
    : engine.ready === true ? "ready"
    : engine.ready === false ? "unavailable" : "configured";
  const key = {missing: "newsEngineMissing", ready: "newsEngineReady",
    unavailable: "newsEngineUnavailable", configured: "newsEngineConfigured"}[state];
  newsEngineState.dataset.state = state;
  newsEngineLabel.textContent = t(key);
  newsEngineDescription.textContent = t(`${key}Note`);
}

function friendlyError(result) {
  const error = result?.error;
  if (error === "INVALID_TOKEN") return t("tokenError");
  if (error === "UNAUTHORIZED") return t("authError");
  if (error === "NOT_CONFIGURED") return t("missingMessage");
  return t("genericError");
}

async function health({quiet = false} = {}) {
  connection("checking", "checking");
  try {
    const result = await requestRuntime({type: "GET_HEALTH"});
    if (result?.ok && result.status?.status === "ready" && result.status?.service === "FactTTL") {
      reportedNewsEngine = result.status?.news_engine;
      hasNewsEngineStatus = true;
      renderNewsEngine(reportedNewsEngine);
      connection("connected", "connected");
      if (!quiet) show(t("connectedMessage"), "good");
      return true;
    }
    const configured = result.configured !== false && result.error !== "NOT_CONFIGURED";
    newsEngineState.hidden = true;
    hasNewsEngineStatus = false;
    connection(configured ? "offline" : "unconfigured", configured ? "offline" : "notConfigured");
    if (!quiet) show(configured ? t("offlineMessage") : t("missingMessage"), "error");
    return false;
  } catch {
    connection("offline", "offline");
    newsEngineState.hidden = true;
    hasNewsEngineStatus = false;
    if (!quiet) show(t("extensionError"), "error");
    return false;
  }
}

async function setToken(value) {
  const saved = await requestRuntime({type: "SET_TOKEN", payload: {token: value}});
  if (!saved.ok) {
    show(friendlyError(saved), "error");
    return false;
  }
  return health();
}

async function importConfiguration(file) {
  if (!file || file.size > 16384) throw new Error("INVALID_CONFIGURATION");
  const config = JSON.parse(await file.text());
  if (!config || config.base_url !== "http://127.0.0.1:8765") throw new Error("INVALID_CONFIGURATION");
  if (config.allowed_origin !== extensionOrigin) throw new Error("ORIGIN_MISMATCH");
  if (typeof config.token !== "string" || !/^[A-Za-z0-9._~-]{16,256}$/.test(config.token)) {
    throw new Error("INVALID_CONFIGURATION");
  }
  const saved = await requestRuntime({type: "SET_TOKEN", payload: {token: config.token}});
  if (!saved.ok) {
    show(friendlyError(saved), "error");
    return false;
  }
  return health();
}

async function loadPreferences() {
  const fallback = browserDefaults();
  countrySelect.value = fallback.country;
  language = fallback.language;
  languageSelect.value = language;
  renderLanguage();
  try {
    const result = await requestRuntime({type: "GET_PREFERENCES"});
    const preferences = result?.ok && result.preferences ? result.preferences : fallback;
    countrySelect.value = ["IT", "US", "GB", "DE", "FR", "ES"].includes(preferences.country)
      ? preferences.country : fallback.country;
    language = ["it", "en", "de", "fr", "es"].includes(preferences.language)
      ? preferences.language : fallback.language;
    languageSelect.value = language;
    renderLanguage();
  } catch {
    countrySelect.value = fallback.country;
    language = fallback.language;
    languageSelect.value = language;
    renderLanguage();
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const button = form.querySelector("button[type='submit']");
  button.disabled = true;
  const value = tokenInput.value.trim();
  tokenInput.value = "";
  try { await setToken(value); }
  catch { show(t("extensionError"), "error"); }
  finally { button.disabled = false; }
});

importButton.addEventListener("click", () => configFile.click());
configFile.addEventListener("change", async () => {
  const file = configFile.files[0];
  if (!file) return;
  importButton.disabled = true;
  show(language === "it" ? "Lettura del file di configurazione…" : "Reading configuration file…");
  try {
    await importConfiguration(file);
  } catch (error) {
    show(error?.message === "ORIGIN_MISMATCH" ? t("originMismatch") : t("configError"), "error");
  } finally {
    configFile.value = "";
    importButton.disabled = false;
  }
});

document.getElementById("retry-health").addEventListener("click", () => health());

copyOrigin.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(extensionOrigin);
    copyOrigin.textContent = t("originCopied");
  } catch {
    show(t("originCopyFallback"));
  }
});

languageSelect.addEventListener("change", () => {
  language = languageSelect.value;
  renderLanguage();
});

preferencesForm.addEventListener("submit", async event => {
  event.preventDefault();
  const button = preferencesForm.querySelector("button[type='submit']");
  button.disabled = true;
  preferencesStatus.textContent = "";
  try {
    const result = await requestRuntime({
      type: "SET_PREFERENCES",
      payload: {preferences: {country: countrySelect.value, language: languageSelect.value}},
    });
    if (!result?.ok) throw new Error("SAVE_FAILED");
    preferencesStatus.textContent = t("preferencesSaved");
  } catch {
    preferencesStatus.textContent = t("preferencesError");
  } finally {
    button.disabled = false;
  }
});

loadPreferences();
if (extensionOrigin) health({quiet: true});
else {
  connection("unconfigured", "notConfigured");
  importButton.disabled = true;
  form.querySelector("button[type='submit']").disabled = true;
  show(t("extensionContext"), "error");
}

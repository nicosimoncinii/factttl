/* Local visual fixture only, excluded from every extension package. */
let previewPreferences = {country: "IT", language: "it"};
window.chrome = {runtime: {
  getURL: () => "moz-extension://11111111-1111-4111-8111-111111111111/",
  async sendMessage(message) {
    if (message.type === "GET_HEALTH") {try {const response = await fetch("/health-preview"); return response.ok ? {ok: true, status: await response.json()} : {ok: false};} catch {return {ok: false};}}
    if (message.type === "GET_PREFERENCES") return {ok: true, preferences: previewPreferences};
    if (message.type === "SET_PREFERENCES") {previewPreferences = message.payload.preferences; return {ok: true, preferences: previewPreferences};}
    return {ok: false, error: "Anteprima: importa la configurazione nelle opzioni dell’estensione installata."};
  }
}};

// Produce a Firefox-only package from the shared extension sources.
import {readFile, writeFile, mkdir, copyFile, rm} from "node:fs/promises";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const source = join(root, "chatgpt-extension");
const target = join(root, "firefox-extension");
const manifest = JSON.parse(await readFile(join(source, "manifest.json"), "utf8"));
// Firefox uses an event page and its Gecko ID, rather than Chromium's public key.
delete manifest.key;
delete manifest.minimum_chrome_version;
manifest.background = {scripts: ["amazon-url.js", "background.js"]};
await mkdir(target, {recursive: true});
for (const name of ["amazon-url.js", "background.js", "item-ui.js", "merchant.js", "content.js", "content.css", "options.js", "options.html", "options.css"]) {
  await copyFile(join(source, name), join(target, name));
}
// These modules belonged to the retired composer-injection design. Remove an
// older generated copy so rebuilding can never leave executable stale code.
for (const name of ["memory.js", "correction.js"]) {
  await rm(join(target, name), {force: true});
}
await writeFile(join(target, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
await writeFile(join(target, "README.md"), "# FactTTL per Firefox\n\nPacchetto generato con `node integrations/build-firefox.mjs`.\n\nCarica questo `manifest.json` da `about:debugging#/runtime/this-firefox` usando **Carica componente aggiuntivo temporaneo**.\n\nApri le opzioni e copia l'origine `moz-extension://…` per collegare il servizio locale. Istruzioni complete in `../chatgpt-extension/README.md`.\n\nDopo modifiche ai sorgenti, rigenera il pacchetto e ricarica il componente in Firefox.\n");
console.log("Pacchetto Firefox pronto: " + join(target, "manifest.json"));

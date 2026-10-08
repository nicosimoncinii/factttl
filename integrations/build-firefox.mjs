// Produce a Firefox-only package from the shared extension sources.
import {readFile, writeFile, mkdir, copyFile} from "node:fs/promises";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const source = join(root, "chatgpt-extension");
const target = join(root, "firefox-extension");
const manifest = JSON.parse(await readFile(join(source, "manifest.json"), "utf8"));
// Firefox uses an event page and its Gecko ID, rather than Chromium's public key.
delete manifest.key;
delete manifest.minimum_chrome_version;
manifest.background = {scripts: ["background.js"]};
await mkdir(target, {recursive: true});
for (const name of ["background.js", "item-ui.js", "memory.js", "merchant.js", "content.js", "content.css", "options.js", "options.html", "options.css"]) {
  await copyFile(join(source, name), join(target, name));
}
await writeFile(join(target, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
await writeFile(join(target, "README.md"), "# FactTTL per Firefox\n\nPacchetto generato con `node integrations/build-firefox.mjs`.\n\nCarica questo `manifest.json` da `about:debugging#/runtime/this-firefox` usando **Carica componente aggiuntivo temporaneo**.\n\nApri le opzioni e copia l'origine `moz-extension://…` per collegare il servizio locale. Istruzioni complete in `../chatgpt-extension/README.md`.\n\nDopo modifiche ai sorgenti, rigenera il pacchetto e ricarica il componente in Firefox.\n");
console.log("Pacchetto Firefox pronto: " + join(target, "manifest.json"));

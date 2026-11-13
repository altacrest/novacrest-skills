// render.mjs: renders the cards and overlays a spec lists, from gfx/cards.html and gfx/shorts.html, with Playwright.
//   node engine/render.mjs <spec.json> [--force]
// spec.json: {"brand": {...brand.json, "dir": "<brand folder>"}, "out": "<folder for the PNGs>",
//             "items": [{"file": "x.png", "page": "cards.html", "kind": "title", "extra": {...},
//                        "size": [1920, 1080], "transparent": true}]}
// A PNG that already exists is kept unless --force. Needs Playwright with Chromium (the Claude workspace has both).
import { createRequire } from "module";
import { readFileSync, mkdirSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require("playwright")); }
catch (e) { ({ chromium } = createRequire(resolve(process.cwd(), "x.js"))("playwright")); }
const HERE = dirname(fileURLToPath(import.meta.url));
const specPath = resolve(process.argv[2]);
const spec = JSON.parse(readFileSync(specPath, "utf8"));
const out = resolve(spec.out || dirname(specPath));
mkdirSync(out, { recursive: true });
const force = process.argv.includes("--force");
const browser = await chromium.launch();
const contexts = {};
let n = 0;
for (const s of spec.items) {
  const dest = `${out}/${s.file}`;
  if (!force && existsSync(dest)) continue;
  const [w, h] = s.size || (s.page === "shorts.html" ? [1080, 1920] : [1920, 1080]);
  const key = `${w}x${h}`;
  contexts[key] = contexts[key] || await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const pg = await contexts[key].newPage();
  await pg.addInitScript(([b, x]) => { window.BRAND = b; window.EXTRA = x; }, [spec.brand, Object.assign({ kind: s.kind }, s.extra || {})]);
  await pg.goto(`file://${HERE}/gfx/${s.page || "cards.html"}?kind=${encodeURIComponent(s.kind)}`);
  await pg.evaluate(() => document.fonts.ready);
  await pg.waitForFunction(() => window.READY === true, null, { timeout: 20000 });
  await pg.screenshot({ path: dest, omitBackground: s.transparent !== false });
  await pg.close(); n++;
}
await browser.close();
console.log(`rendered ${n} of ${spec.items.length} cards into ${out}`);

// youtube_studio.js: page helpers that put the shorts on YouTube from YouTube Studio in Chrome (Claude in Chrome).
//
// One Chrome tab on studio.youtube.com, with the brand channel's manager signed in (never sign in for the user):
//  1. The shorts sit in the session's uploads or outputs folder. Claude in Chrome's file_upload takes under 10 MB per
//     call, so a bigger short is re-encoded first with shrink_short.sh (two-pass x264 to 9.6 MB, audio copied).
//  2. Paste this file into the page (javascript tool). Then set window.__ROWS from out/shorts/shorts_upload.csv
//     ({"<short id>": {"youtube_title": ..., "youtube_description": ...}, ...}) and window.__CFG.fullVideo /
//     fullVideoTitle (the long video's link and title, for the Related video picker). Run await __openUpload().
//     For each short (the last first, so the first ends up on top of the channel's Shorts tab):
//       find the upload dialog's hidden file input  ->  file_upload(<short id>.mp4)  ->  await __doShort("<short id>")
//     __doShort fills the title and description, sets "not made for kids", paid promotion No, altered content Yes,
//     saves the short as PRIVATE and opens the next upload dialog. The file input is new each time, so find it again.
//  3. Why private first: publishing a short before YouTube's copyright check finishes brings up "We're still checking
//     your content ... you may get a strike". The check takes a few minutes per short and runs in the background.
//  4. When the checks are done and the user says to publish, on any /video/<id>/edit page: await __finish(id) for each
//     id. It sets Related video to the full video and visibility Public, then saves. If YouTube still warns that
//     checks are running, it backs out, undoes, and reports it; run that one again later.
//  Keep each javascript call under 45 seconds (the tool times out): about 3 __finish calls per call.
// Keep the video IDs in out/shorts/youtube_ids.json.

window.__CFG = window.__CFG || {
  fullVideo: "",           // the long video's link, e.g. https://youtu.be/...
  fullVideoTitle: "",      // its exact title: how the Related video picker finds it
};
window.__ROWS = window.__ROWS || {};
window.__sleep = ms => new Promise(r => setTimeout(r, ms));
window.__vis = e => !!(e && e.offsetParent !== null);

// the text meta.py writes to out/shorts/shorts_upload.csv, by short id
window.__text = (id) => {
  const r = __ROWS[id];
  if (!r) throw new Error("no row for " + id + " in __ROWS");
  return {title: r.youtube_title, desc: r.youtube_description};
};

window.__closeInfo = async () => {      // the "Video processing" / "Video published" dialogs that follow a save
  let n = 0;
  for (let k = 0; k < 4; k++) {
    const d = [...document.querySelectorAll("ytcp-dialog")].filter(__vis).find(x => /Video processing|Video published|still processing/i.test(x.innerText));
    const c = d && (d.querySelector("ytcp-button#close-button") || d.querySelector("#close-icon-button"));
    if (!c) break;
    c.click(); n++; await __sleep(800);
  }
  return n;
};

window.__openUpload = async () => {
  const picker = () => [...document.querySelectorAll("ytcp-uploads-file-picker")].find(__vis);
  for (let attempt = 0; attempt < 4; attempt++) {
    for (let i = 0; i < 6; i++) { await __sleep(500); if (await __closeInfo()) break; }
    if (picker()) return "picker open";
    document.body.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true})); await __sleep(300);
    const create = [...document.querySelectorAll('ytcp-button.ytcpAppHeaderCreateIcon, button[aria-label="Create"]')].find(__vis);
    if (!create) continue;
    create.click(); await __sleep(900);
    const item = [...document.querySelectorAll('tp-yt-paper-item, [role="menuitem"]')].find(e => /Upload videos/i.test(e.innerText) && __vis(e));
    if (!item) continue;
    item.click();
    for (let i = 0; i < 12; i++) { await __sleep(300); if (picker()) return "picker open"; }
  }
  return "picker not visible";
};

window.__fill = async (n, label, level, hook) => {
  const {title, desc} = __text(n, label, level, hook);
  let dlg, tbox;
  for (let i = 0; i < 80; i++) { dlg = document.querySelector("ytcp-uploads-dialog"); tbox = dlg && dlg.querySelector("#title-textarea #textbox"); if (__vis(tbox)) break; await __sleep(500); }
  if (!__vis(tbox)) return {n, err: "no details form"};
  const set = async (box, text) => { box.focus(); document.execCommand("selectAll", false, null); document.execCommand("insertText", false, text); await __sleep(500); };
  await set(tbox, title);
  const dbox = dlg.querySelector("#description-textarea #textbox");
  await set(dbox, desc);
  const radio = name => dlg.querySelector(`tp-yt-paper-radio-button[name="${name}"]`);
  radio("VIDEO_MADE_FOR_KIDS_NOT_MFK").click(); await __sleep(300);
  const more = [...dlg.querySelectorAll("ytcp-button")].find(b => b.innerText.trim() === "Show more" && __vis(b));
  if (more) { more.click(); await __sleep(900); }
  const paid = radio("VIDEO_PAID_PRODUCT_PLACEMENT_NO"); if (paid) { paid.click(); await __sleep(250); }
  radio("VIDEO_HAS_ALTERED_CONTENT_YES").click(); await __sleep(400);
  const norm = s => s.replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").trim();
  return {n, title: tbox.innerText.trim() === title, desc: norm(dbox.innerText) === norm(desc),
          mfk: radio("VIDEO_MADE_FOR_KIDS_NOT_MFK").getAttribute("aria-checked"),
          alt: radio("VIDEO_HAS_ALTERED_CONTENT_YES").getAttribute("aria-checked"),
          link: (dlg.innerText.match(/youtube\.com\/shorts\/[\w-]+/) || [""])[0]};
};

window.__saved = window.__saved || {};
window.__doShort = async (n, label, level, hook) => {
  const f = await __fill(n, label, level, hook);
  if (!(f.title && f.desc && f.mfk === "true" && f.alt === "true")) return JSON.stringify({n, stop: "form check failed", f});
  const dlg = document.querySelector("ytcp-uploads-dialog");
  const next = dlg.querySelector("#next-button");
  for (let i = 0; i < 3; i++) { next.click(); await __sleep(1200); }
  const priv = dlg.querySelector('tp-yt-paper-radio-button[name="PRIVATE"]');
  if (!__vis(priv)) return JSON.stringify({n, stop: "visibility step not reached"});
  priv.click(); await __sleep(700);
  const done = dlg.querySelector("#done-button");
  if (priv.getAttribute("aria-checked") !== "true" || !/Save/i.test(done.innerText)) return JSON.stringify({n, stop: "private not set"});
  done.click();
  let closed = false;
  for (let i = 0; i < 20; i++) { await __sleep(500); if (!__vis(dlg.querySelector("#title-textarea"))) { closed = true; break; } }
  if (!closed) return JSON.stringify({n, stop: "dialog did not close after Save", link: f.link});
  __saved[n] = f.link;
  return JSON.stringify({n, saved: f.link, next: await __openUpload()});
};

window.__pickLong = async () => {         // the full video's card in the Related video picker (search if it isn't on top)
  const find = () => [...document.querySelectorAll("ytcp-entity-card")].filter(__vis).find(c => c.innerText.includes(__CFG.fullVideoTitle));
  for (let i = 0; i < 6; i++) { await __sleep(400); if (find()) return find(); }
  const d = [...document.querySelectorAll("ytcp-dialog")].filter(__vis).find(x => /Choose specific video/.test(x.innerText));
  const input = d && d.querySelector("input#search-yours");
  if (!input) return null;
  input.focus(); document.execCommand("selectAll", false, null); document.execCommand("insertText", false, __CFG.fullVideoTitle);
  for (let i = 0; i < 15; i++) { await __sleep(400); if (find()) return find(); }
  return null;
};

window.__finish = async (id) => {
  if (!location.pathname.includes(id)) { history.pushState({}, "", `/video/${id}/edit`); window.dispatchEvent(new PopStateEvent("popstate", {state: {}})); }
  let ready = false;
  for (let i = 0; i < 30; i++) { await __sleep(400); if (location.pathname.includes(id) && __vis(document.querySelector("#title-textarea #textbox")) && __vis(document.querySelector("#linked-video-editor-link"))) { ready = true; break; } }
  if (!ready) return {id, err: "page not ready"};
  await __sleep(900);
  const res = {id, title: document.querySelector("#title-textarea #textbox").innerText.trim().replace(/^.*#/, "#")};
  const related = () => document.querySelector("#linked-video-editor-link").innerText.includes(__CFG.fullVideoTitle);
  if (!related()) {
    document.querySelector("#linked-video-editor-link ytcp-dropdown-trigger").click();
    const card = await __pickLong();
    if (!card) { document.body.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true})); return Object.assign(res, {err: "no related card"}); }
    card.click(); await __sleep(1200);
  }
  res.related = related();
  const isPublic = () => /Visibility\s*\n\s*Public/.test(document.body.innerText);
  if (!isPublic()) {
    [...document.querySelectorAll("ytcp-icon-button#select-button")].find(e => __vis(e) && /visibility/i.test(e.getAttribute("aria-label") || "")).click();
    await __sleep(1200);
    const pub = [...document.querySelectorAll('tp-yt-paper-radio-button[name="PUBLIC"]')].find(__vis);
    if (!pub) return Object.assign(res, {err: "no public radio"});
    pub.click(); await __sleep(500);
    [...document.querySelectorAll("ytcp-button#save-button")].find(__vis).click(); await __sleep(900);
  }
  const save = [...document.querySelectorAll("ytcp-button#save")].find(__vis);
  if (save.getAttribute("aria-disabled") === "true") return Object.assign(res, {saved: "nothing to save", pub: isPublic()});
  save.click();
  for (let i = 0; i < 25; i++) {
    await __sleep(400);
    const warn = [...document.querySelectorAll("ytcp-dialog")].filter(__vis).find(d => /still checking/i.test(d.innerText));
    if (warn) {
      warn.querySelector("ytcp-button#primary-action-button").click(); await __sleep(800);
      const undo = [...document.querySelectorAll("ytcp-button#discard")].find(__vis); undo && undo.click(); await __sleep(800);
      return Object.assign(res, {saved: "checks still running, undone"});
    }
    if (save.getAttribute("aria-disabled") === "true") return Object.assign(res, {saved: "saved", pub: isPublic()});
  }
  return Object.assign(res, {saved: "unknown", pub: isPublic()});
};
window.__runFinish = async (ids) => { const out = []; for (const id of ids) out.push(await __finish(id)); return JSON.stringify(out); };
"youtube_studio.js loaded";

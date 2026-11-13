// instagram_web.js: page helpers that post the shorts as Instagram Reels from instagram.com in Chrome (Claude in Chrome).
//
// Dry-run tested through every step except the Share click; that step is one click plus __igWait. The caption's line
// breaks have to go in as a paste (see __igFill).
//
// How it goes (one Chrome tab on instagram.com, with the brand's account already signed in by the user; never sign in for them):
//  1. Put the shorts and their covers in the session's shared uploads folder (/mnt/user-data/uploads/shorts/ and
//     /mnt/user-data/uploads/shorts/covers/). Claude in Chrome's file_upload takes under 10 MB per call, so shrink
//     bigger shorts first with shrink_short.sh, as for YouTube. A cover is the short's frame at 0.27 s, when the head
//     block is up and no caption has appeared yet:
//       ffmpeg -ss 0.27 -i short_NN.mp4 -frames:v 1 -q:v 2 cover_NN.jpg
//     Without a custom cover, Instagram uses the first frame, which comes before the head block.
//  2. Paste this file into the page with the javascript tool. It also saves itself to localStorage, because closing
//     the "Reel shared" dialog takes the tab back to the profile and wipes the page's scripts. Start every later
//     javascript call with:
//       if (!window.__igShare) new Function(localStorage.getItem("__igHelpers"))();
//  3. For each reel, in number order (#1 first, so the newest, #60, ends up at the top of the grid):
//       await __igOpen()                         -> "picker open" (Create, Post, the "Create new post" dialog)
//       find the dialog's hidden file input       -> file_upload(short_NN.mp4)
//       await __igPrep()                         -> {step: "edit"}  (crop set to Original, then Next)
//       find the Edit step's cover file input     -> file_upload(covers/cover_NN.jpg)  ("Cover photo", "Select from computer")
//       await __igShare(n, hook)                 -> {"n":..,"ok":"share clicked"}
//       await __igWait(n)                        -> {"n":..,"ok":"shared"}  (call again if "still sharing")
//       await __igClose()                        -> closes the "Reel shared" dialog
//     Set window.__ROWS from out/shorts/shorts_upload.csv first; n is the short's id and the caption is its instagram_caption.
//     In a browser_batch, make each step throw on a bad result so the batch stops there.
//  4. Never press Escape in the composer: it opens "Discard post?". Each javascript call has to finish within 45
//     seconds, which is why __igWait gives up after 37 s and is called again.
//  5. Check the profile's post count at the end: it should rise by exactly the number of reels posted.

window.__igInstall = function () {
  const W = window;
  W.__s = ms => new Promise(r => setTimeout(r, ms));
  W.__v = e => !!e && e.getClientRects().length > 0;
  W.__txt = e => ((e && e.innerText) || "").trim();
  W.__top = () => [...document.querySelectorAll('div[role="dialog"]')].filter(__v).pop() || null;
  W.__btn = (re, root) => [...(root || document).querySelectorAll('div[role="button"], button, a')]
    .filter(__v).find(b => re.test(__txt(b) || b.getAttribute("aria-label") || ""));
  W.__icon = (re, root) => {
    const svg = [...(root || document).querySelectorAll("svg[aria-label]")].filter(__v).find(s => re.test(s.getAttribute("aria-label")));
    return svg ? (svg.closest('div[role="button"], button, a') || svg) : null;
  };
  W.__cap = (n, hook) => (window.__ROWS && window.__ROWS[n]) ? window.__ROWS[n].instagram_caption : hook;   // shorts_upload.csv

  W.__igOpen = async () => {
    const picker = () => { const d = __top(); return d && /Create new post/.test(d.innerText) && /Select from computer/.test(d.innerText); };
    for (let attempt = 0; attempt < 3; attempt++) {
      if (picker()) return "picker open";
      const create = __icon(/^(New post|Create)$/);
      if (!create) { await __s(800); continue; }
      create.click(); await __s(900);
      if (picker()) return "picker open";
      const post = [...document.querySelectorAll('a, div[role="button"], div[role="menuitem"], span')].filter(__v).find(e => __txt(e) === "Post");
      if (post) (post.closest('a, div[role="button"], div[role="menuitem"]') || post).click();
      for (let i = 0; i < 15; i++) { await __s(300); if (picker()) return "picker open"; }
    }
    return "picker not open";
  };

  W.__igPrep = async () => {
    let d = null;
    for (let i = 0; i < 60; i++) {                        // wait for the Crop step (the video takes a moment to load)
      await __s(500);
      d = __top();
      if (!d) continue;
      if (/shared as reels/i.test(d.innerText)) { const ok = __btn(/^OK$/, d); if (ok) { ok.click(); continue; } }
      if (__icon(/^Select crop$/, d) && __btn(/^Next$/, d)) break;
    }
    const crop = d && __icon(/^Select crop$/, d);
    if (!crop) return {err: "no crop step"};
    crop.click(); await __s(700);                         // the default is 1:1, which cuts the head block off
    const orig = [...d.querySelectorAll('div[role="button"], button, span')].filter(__v).find(e => __txt(e) === "Original");
    if (!orig) return {err: "no Original option"};
    (orig.closest('div[role="button"], button') || orig).click(); await __s(700);
    __btn(/^Next$/, d).click();
    for (let i = 0; i < 25; i++) { await __s(400); const t = __top(); if (t && /Cover photo/.test(t.innerText)) return {step: "edit"}; }
    return {err: "edit step not reached"};
  };

  W.__igAiSwitch = () => {                                // the switch next to "AI label", wherever the panel puts it
    const label = [...document.querySelectorAll("span, div")].filter(__v).find(e => /^(Add )?AI label$/i.test(__txt(e)));
    for (let e = label, k = 0; e && k < 10; e = e.parentElement, k++) {
      const sw = e.querySelectorAll('input[role="switch"]');
      if (sw.length === 1) return sw[0];
      if (sw.length > 1) return null;
    }
    return null;
  };

  // Everything up to the Share click: Next, the caption, the AI label, and the checks. Shares nothing.
  W.__igFill = async (n, hook) => {
    const d = __top();
    if (!d || !/Cover photo/.test(d.innerText)) return {n, err: "not on the Edit step"};
    await __s(1500);                                      // let the cover upload settle
    __btn(/^Next$/, d).click();
    let box = null;
    for (let i = 0; i < 25; i++) {
      await __s(400);
      box = [...document.querySelectorAll('div[contenteditable="true"][role="textbox"], div[contenteditable="true"][aria-label^="Write a caption"]')].find(__v);
      if (box) break;
    }
    if (!box) return {n, err: "no caption box"};
    const text = __cap(n, hook);
    box.focus(); await __s(200);
    // The box is a Lexical editor. A paste event carries the line breaks; execCommand("insertLineBreak") doesn't
    // (Lexical undoes it, and the caption comes out as one run-on paragraph).
    const dt = new DataTransfer(); dt.setData("text/plain", text);
    box.dispatchEvent(new ClipboardEvent("paste", {clipboardData: dt, bubbles: true, cancelable: true}));
    await __s(800);
    box.blur(); await __s(500);                           // closes the hashtag suggestions
    let sw = __igAiSwitch();
    if (!sw) {                                            // in case it sits under "Advanced settings"
      const adv = __btn(/^Advanced settings$/);
      if (adv) { adv.click(); await __s(800); sw = __igAiSwitch(); }
    }
    if (!sw) return {n, err: "no AI label switch"};
    if (!sw.checked) { sw.click(); await __s(600); }
    const res = {n, caption: box.innerText.trim() === text, ai: sw.checked};   // exact, line breaks included
    if (!res.caption) res.got = box.innerText.slice(0, 400);
    return res;
  };

  W.__igShare = async (n, hook) => {
    const f = await __igFill(n, hook);
    if (f.err || !f.caption || !f.ai) return JSON.stringify(Object.assign(f, {stop: "check failed, nothing shared"}));
    const share = __btn(/^Share$/, __top());
    if (!share) return JSON.stringify({n, err: "no Share button"});
    share.click();
    return JSON.stringify({n, ok: "share clicked"});
  };

  W.__igWait = async (n) => {
    for (let i = 0; i < 74; i++) {                        // 37 s, so the javascript call stays under 45 s
      const t = __txt(__top());
      if (/has been shared/i.test(t)) return JSON.stringify({n, ok: "shared"});
      if (/couldn.t be shared|could not be shared|try again|something went wrong/i.test(t)) return JSON.stringify({n, err: t.slice(0, 200)});
      await __s(500);
    }
    return JSON.stringify({n, ok: "still sharing"});
  };

  W.__igClose = async () => {                             // the X at the top right, outside the dialog
    const x = __icon(/^Close$/);
    if (!x) return "no close button";
    x.click(); await __s(1500);
    return "closed";
  };

  W.__igDiscard = async () => {                           // leave a half-made post without sharing it
    const x = __icon(/^Close$/);
    if (!x) return "no close button";
    x.click(); await __s(900);
    const d = __top();
    const discard = d && /Discard post\?/.test(d.innerText) && __btn(/^Discard$/, d);
    if (!discard) return "no discard prompt";
    discard.click(); await __s(900);
    return __top() ? "a dialog is still open" : "discarded";
  };
};
window.__igInstall();
localStorage.setItem("__igHelpers", "(" + window.__igInstall.toString() + ")();");
"instagram_web.js loaded";

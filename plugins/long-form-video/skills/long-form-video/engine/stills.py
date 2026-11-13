#!/usr/bin/env python3
"""stills.py: one still per look, made in the Gemini web app in the user's signed-in Chrome (Claude in Chrome).

  python3 engine/stills.py prompts <video folder>
      writes images/prompts.json: every look with its brief and an empty "opening" for Claude to fill from the brand's
      opening_template (brands/<brand>/prompt.json, style.md). Existing openings are kept.
  python3 engine/stills.py queue <video folder> [--only seg-003-1,seg-004-1]
      checks every prompt (filled, at most the brand's max_chars with its pre and tail) and writes two page scripts:
      out/gemini_queue.js (sends each prompt in one Gemini chat and waits for each picture) and
      out/gemini_download.js (places each picture's download button for a real click, and logs the clicks)
  python3 stills.py collect --clicks <video folder>/clicks.json --out <video folder>/images [--downloads <folder>] [--dry-run]
      files the downloads as images/<look id>.jpg (runs on the user's computer, from a copy of this file). Gemini names every file Gemini_Generated_Image_<random>, so each
      click's time window must hold exactly one new file; anything unclear stays in Downloads and is reported.
      Downloads defaults to the Downloads folder the video folder sits in (~/Downloads in the user's Terminal,
      $HOME/mnt/Downloads in Claude's shell on their computer).
  python3 engine/stills.py check <video folder>
      the brand's style check on every still (style_check.py) and the looks that have no still yet

How to run the two page scripts (Claude in Chrome, in the user's signed-in Chrome):
  1. Open gemini.google.com in a new tab, start a new chat, and set the image tool's aspect ratio to 16:9 when it
     offers one. A Thinking-mode chat refuses to make pictures.
  2. javascript_tool: the contents of out/gemini_queue.js. It runs by itself, about 15 to 30 seconds a picture.
     Progress: JSON.stringify([window.__iceq.status, window.__iceq.i, window.__iceq.done.length]).
     Contact sheet over the page for the look check: window.__sheet(0, 12, 4), then window.__unsheet().
  3. Downloads need the user's yes first (one yes covers the batch: say how many files, from gemini.google.com, into
     Downloads). Reload the tab, run out/gemini_download.js, then for each look: javascript_tool
     `await window.__go("<look id>")` (returns the button's [x, y]), a real computer left_click on that point, then
     `await window.__wait()`. About ten looks per browser_batch. The click must be a real one: Chrome lets a page start
     one download by script and drops the rest.
  4. javascript_tool `JSON.stringify({clicks: window.__log})`, save it as clicks.json in the video folder, then run
     collect (on the user's computer, where Downloads is) and check.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def engine():
    """the engine's helpers; collect doesn't need them, so it also runs from a lone copy of this file"""
    import common
    return common

RUNNER = r"""
(() => {
  if (window.__iceq && window.__iceq.status === 'running') return 'already running';
  const STYLE = %(style)s, PRE = %(pre)s;
  const items = %(items)s.map(([n, s]) => ({n, s, text: PRE + s + " " + STYLE}));
  const q = window.__iceq = {items, i: 0, done: [], status: 'ready', stopAt: items.length};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const waitFor = (fn, timeout) => new Promise(resolve => {
    let fin = false, mo, iv, to;
    const end = v => { fin = true; mo.disconnect(); clearInterval(iv); clearTimeout(to); resolve(v); };
    const check = () => { if (fin) return; let v = null; try { v = fn(); } catch (e) {} if (v) end(v); };
    mo = new MutationObserver(check); mo.observe(document.body, {childList: true, subtree: true, attributes: true});
    iv = setInterval(check, 3000); to = setTimeout(() => { if (!fin) end(null); }, timeout); check();
  });
  const btn = (root, label) => [...root.querySelectorAll('button')].find(b => (b.getAttribute('aria-label') || '') === label);
  const stopping = () => [...document.querySelectorAll('button')].some(b => /^stop/i.test(b.getAttribute('aria-label') || ''));
  const doneCheck = before => () => {
    const mrs = document.querySelectorAll('model-response');
    if (mrs.length <= before || stopping()) return null;
    const last = mrs[mrs.length - 1];
    const img = [...last.querySelectorAll('img')].find(i => i.naturalWidth > 300 && i.complete);
    if (img && btn(last, 'Download full size image')) return {ok: true, idx: mrs.length - 1, w: img.naturalWidth, h: img.naturalHeight};
    if (!img && btn(last, 'Good response')) return {ok: false, idx: mrs.length - 1, text: last.innerText.slice(0, 300)};
    return null;
  };
  q.run = async () => {
    q.status = 'running';
    while (q.i < q.items.length) {
      if (q.i >= q.stopAt) { q.status = 'paused'; return; }
      const it = q.items[q.i], before = document.querySelectorAll('model-response').length;
      const ed = document.querySelector('rich-textarea .ql-editor');
      if (!ed) { q.status = 'stuck: no editor at ' + it.n; return; }
      ed.focus(); document.execCommand('selectAll', false, null); document.execCommand('delete', false, null);
      document.execCommand('insertText', false, it.text);
      const send = await waitFor(() => { const b = btn(document, 'Send message'); return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true' ? b : null; }, 15000);
      if (!send) { q.status = 'stuck: no send button at ' + it.n; return; }
      send.click();
      const t0 = Date.now();
      let r = await waitFor(doneCheck(before), 240000);
      if (r && !r.ok) { await sleep(15000); r = doneCheck(before)() || r; }
      q.done.push(Object.assign({n: it.n, secs: Math.round((Date.now() - t0) / 1000)}, r || {ok: false, text: 'timeout'}));
      q.i++;
      await sleep(2500);
    }
    q.status = 'finished';
  };
  window.__sheet = (start, count, cols) => {
    document.getElementById('__qa')?.remove();
    const map = {}; q.done.forEach(d => { if (d.ok) map[d.idx] = d.n; });
    const div = document.createElement('div'); div.id = '__qa';
    div.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#000;display:grid;gap:4px;padding:4px;align-content:start;grid-template-columns:repeat(' + cols + ',1fr)';
    [...document.querySelectorAll('model-response')].slice(start, start + count).forEach((mr, j) => {
      const img = [...mr.querySelectorAll('img')].find(i => i.naturalWidth > 300), cell = document.createElement('div');
      cell.style.position = 'relative';
      if (img) { const c = document.createElement('img'); c.src = img.src; c.style.cssText = 'width:100%%;display:block'; cell.appendChild(c); }
      const t = document.createElement('div'); t.textContent = map[start + j] ?? '?';
      t.style.cssText = 'position:absolute;left:4px;top:4px;background:#ff0;color:#000;font:bold 14px sans-serif;padding:1px 4px';
      cell.appendChild(t); div.appendChild(cell);
    });
    document.body.appendChild(div);
  };
  window.__unsheet = () => document.getElementById('__qa')?.remove();
  q.run();
  return 'started ' + items.length;
})()
"""

DOWNLOADER = r"""
(() => {
  window.__KEYS = %(keys)s;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  window.__mapTurns = () => [...document.querySelectorAll('model-response')].map(mr => {
    const cont = mr.closest('.conversation-container'), uq = cont && cont.querySelector('user-query');
    const text = (uq ? uq.textContent : '').replace(/\s+/g, ' ');
    const hit = window.__KEYS.find(([n, k]) => text.includes(k));
    return {mr, n: hit ? hit[0] : null};
  });
  const scroller = el => { while (el && el !== document.body) { const s = getComputedStyle(el); if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 10) return el; el = el.parentElement; } return document.scrollingElement; };
  const dlBtn = mr => [...mr.querySelectorAll('button')].find(b => b.getAttribute('aria-label') === 'Download full size image');
  window.__ov = () => (document.querySelector('.cdk-overlay-container') || {innerText: ''}).innerText;
  window.__log = window.__log || [];
  window.__go = async (n, y = 300) => {
    for (let k = 0; k < 20 && /Downloading full size|Image downloaded/.test(window.__ov()); k++) await sleep(500);
    let t = window.__mapTurns().find(x => x.n === n);
    for (let k = 0; !t && k < 12; k++) { scroller(document.querySelector('model-response')).scrollTop = 0; await sleep(1500); t = window.__mapTurns().find(x => x.n === n); }
    if (!t) throw new Error(n + ' is not in this chat');
    t.mr.scrollIntoView({block: 'center'}); await sleep(400);
    const b = dlBtn(t.mr); if (!b) throw new Error(n + ' has no download button');
    let r = b.getBoundingClientRect(); scroller(t.mr).scrollTop += (r.y + r.height / 2) - y; await sleep(400);
    r = b.getBoundingClientRect();
    if (Math.abs(r.y + r.height / 2 - y) > 4) throw new Error('could not place ' + n);
    window.__pending = n;
    return [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)];
  };
  window.__wait = async () => {
    const n = window.__pending, t = Date.now(); window.__log.push([n, t]);
    for (let k = 0; k < 90; k++) { await sleep(500); if (/Image downloaded/.test(window.__ov())) { await sleep(1200); return n + ' ok'; } }
    throw new Error('no download for ' + n);
  };
  return 'ready: ' + window.__mapTurns().length + ' turns loaded';
})()
"""


def brand_prompt(video):
    p = video.brand_dir / "prompt.json"
    if not p.exists():
        raise SystemExit("the brand pack has no prompt.json")
    return engine().load_json(p)


def all_looks(video):
    man = video.manifest()
    return [(s, lk) for s in man["segments"] for lk in s["looks"] if not lk.get("stat")]


def cmd_prompts(a):
    video = engine().Video(a.video)
    load_json = engine().load_json
    path = video.dir / "images" / "prompts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    old = load_json(path, {"looks": {}}).get("looks", {})
    bp = brand_prompt(video)
    looks = {}
    for s, lk in all_looks(video):
        o = old.get(lk["id"], {})
        looks[lk["id"]] = {"segment": s["id"], "title": s["title"], "brief": lk["brief"], "opening": o.get("opening", "")}
    path.write_text(json.dumps({"template": bp["opening_template"], "looks": looks}, indent=1, ensure_ascii=False) + "\n")
    empty = [k for k, v in looks.items() if not v["opening"].strip()]
    print("wrote %s: %d looks, %d openings still to write" % (path, len(looks), len(empty)))


def cmd_queue(a):
    video = engine().Video(a.video)
    bp = brand_prompt(video)
    d = engine().load_json(video.dir / "images" / "prompts.json")
    only = [x.strip() for x in a.only.split(",") if x.strip()]
    items, probs = [], []
    for lid, v in d["looks"].items():
        if only and lid not in only:
            continue
        o = v.get("opening", "").strip()
        if not o:
            probs.append("%s has no opening yet" % lid)
            continue
        n = len(bp["pre"]) + len(o) + 1 + len(bp["tail"])
        if n > bp["max_chars"]:
            probs.append("%s: %d characters with the style tail (at most %d); shorten its opening" % (lid, n, bp["max_chars"]))
            continue
        items.append([lid, o])
    for p in probs:
        print("PROBLEM " + p)
    if probs and not a.force:
        sys.exit(1)
    out = video.out
    out.mkdir(parents=True, exist_ok=True)
    js = RUNNER % {"style": json.dumps(bp["tail"]), "pre": json.dumps(bp["pre"]), "items": json.dumps(items, ensure_ascii=False)}
    (out / "gemini_queue.js").write_text(js.strip() + "\n")
    keys = [[n, v[:48]] for n, v in items]
    (out / "gemini_download.js").write_text((DOWNLOADER % {"keys": json.dumps(keys, ensure_ascii=False)}).strip() + "\n")
    print("wrote out/gemini_queue.js (%d prompts) and out/gemini_download.js" % len(items))


def downloads_dir(out):
    """where the browser saves: the Downloads folder the video folder sits in (~/Downloads/<slug>/), else the
    connected Downloads in Claude's shell on the user's computer ($HOME/mnt/Downloads), else ~/Downloads"""
    video = Path(out).expanduser().resolve().parent
    for d in (video.parent, Path.home() / "mnt" / "Downloads", Path.home() / "Downloads"):
        if d.name == "Downloads" and d.is_dir():
            return d
    return Path.home() / "Downloads"


def cmd_collect(a):
    from PIL import Image
    data = json.loads(Path(a.clicks).read_text())
    clicks = sorted(((str(n), t / 1000.0) for n, t in data["clicks"]), key=lambda x: x[1])
    dl = Path(a.downloads).expanduser() if a.downloads else downloads_dir(a.out)
    files = [p for p in dl.glob("Gemini_Generated_Image_*") if p.suffix.lower() in (".jpeg", ".jpg", ".png")]
    mt = {p: p.stat().st_mtime for p in files}
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    plan, probs = [], []
    for k, (n, t) in enumerate(clicks):
        end = clicks[k + 1][1] - 0.5 if k + 1 < len(clicks) else t + 120
        hit = [p for p in files if t - 1 <= mt[p] < end]
        if len(hit) != 1:
            probs.append("%s: %d downloads in its window" % (n, len(hit)))
            continue
        plan.append((n, hit[0]))
    for n, p in plan:
        dest = out / (n + (".png" if p.suffix.lower() == ".png" else ".jpg"))
        if dest.exists():
            probs.append("%s: %s already exists, left %s in Downloads" % (n, dest.name, p.name))
            continue
        with Image.open(p) as im:
            size = "%dx%d" % im.size
        print("  %s <- %s (%s)" % (n, p.name, size))
        if not a.dry_run:
            shutil.move(str(p), str(dest))
    for x in probs:
        print("  PROBLEM " + x)
    print("%s %d of %d" % ("would file" if a.dry_run else "filed", len(plan), len(clicks)))


def cmd_check(a):
    video = engine().Video(a.video)
    ENGINE = engine().ENGINE
    have, missing = [], []
    for s, lk in all_looks(video):
        p = next((video.dir / "images" / (lk["id"] + e) for e in (".jpg", ".jpeg", ".png", ".webp")
                  if (video.dir / "images" / (lk["id"] + e)).exists()), None)
        (have if p else missing).append(p or lk["id"])
    if have:
        r = subprocess.run([sys.executable, str(ENGINE / "style_check.py")] + [str(p) for p in have], capture_output=True, text=True)
        bad = [json.loads(x) for x in r.stdout.splitlines() if x.strip() and not json.loads(x)["ok"]]
        for b in bad:
            print("STYLE %s: %s" % (Path(b["file"]).name, "; ".join(b["problems"])))
        print("%d stills, %d fail the style check" % (len(have), len(bad)))
    if missing:
        print("no still yet: %s" % ", ".join(missing))
    sys.exit(1 if missing else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompts")
    p.add_argument("video")
    q = sub.add_parser("queue")
    q.add_argument("video")
    q.add_argument("--only", default="")
    q.add_argument("--force", action="store_true", help="write the scripts even with problems (the bad prompts are left out)")
    c = sub.add_parser("collect")
    c.add_argument("--clicks", required=True)
    c.add_argument("--out", required=True, help="the video folder's images folder")
    c.add_argument("--downloads", help="where the browser saves (default: the Downloads folder the video folder is in)")
    c.add_argument("--dry-run", action="store_true")
    k = sub.add_parser("check")
    k.add_argument("video")
    a = ap.parse_args()
    {"prompts": cmd_prompts, "queue": cmd_queue, "collect": cmd_collect, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()

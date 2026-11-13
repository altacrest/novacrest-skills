#!/usr/bin/env python3
"""clips.py: the Higgsfield clips. Each clip is animated from a look's own still and opens that look in the video.

  python3 engine/clips.py plan <video folder> [--max 16]
      writes clips/plan.json: which looks get a clip, in order (looks with a *(clip: ...)* direction first, then one
      per segment in order, up to --max or video.json's "clips"), each with its still, the motion prompt (the brand's
      clip_prompt with the direction's motion, or the brand's default motion) and the negative prompt.
  python3 clips.py collect --as <look id> --out <video folder>/clips [--downloads ~/Downloads] [--since <epoch seconds>]
      files the newest .mp4 in Downloads (newer than --since) as clips/<look id>.mp4. Download one clip at a time,
      then collect it, so there's never a doubt which file is which. Runs on the user's computer from a copy of this file.
  python3 engine/clips.py check <video folder>
      planned looks with and without a clip, and each clip's length and size (a clip under 2 seconds is dropped)

Making the clips (SKILL.md, Step 6), in the Higgsfield web app in the user's signed-in Chrome (Claude in Chrome):
  1. The Higgsfield connector (https://mcp.higgsfield.ai/mcp) can't make media; it reads the credits (balance), the
     models and their settings (models_list, models_get) and every finished generation with its link
     (show_generations). Check the balance first and say what the clips will cost; get a yes before making them.
  2. Open higgsfield.ai/ai/video, pick the model (Kling 3.0 Turbo), and for each planned look: Start frame, then
     Upload file (the still, from the session's uploads folder; Chrome's file chooser is avoided by finding the
     upload tile's file input and using file_upload on it), the prompt from plan.json, 5 s, 720p, Generate.
     A clip takes about 4 minutes; several can run at once.
  3. When a clip shows in History, show_generations lists it first (kling3_0_turbo, with its .mp4 link). Downloads need
     the user's yes (one yes for the batch: how many files, from Higgsfield, into Downloads). Then collect each one.
  4. Look at three frames of each clip before keeping it (the start, the middle, the end).
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
MODEL = "Kling 3.0 Turbo, 720p, 5 s (7.5 credits a clip when measured in Nov 2026)"


def engine():
    import common
    return common


def cmd_plan(a):
    c = engine()
    video = c.Video(a.video)
    man = video.manifest()
    bp = c.load_json(video.brand_dir / "prompt.json")
    cap = a.max if a.max is not None else int(video.cfg.get("clips", 16))
    looks = [(s, lk) for s in man["segments"] for lk in s["looks"] if not lk.get("stat") and s["kind"] == "segment"]
    marked = [(s, lk) for s, lk in looks if lk.get("clip")]
    seen = {s["id"] for s, lk in marked}          # a segment with a marked clip gets no second one
    firsts = []
    for s, lk in looks:
        if s["id"] not in seen:
            seen.add(s["id"])
            firsts.append((s, lk))
    chosen = (marked + [x for x in firsts if x not in marked])[:cap]
    order = {lk["id"]: i for i, (s, lk) in enumerate(looks)}
    chosen.sort(key=lambda x: order[x[1]["id"]])
    plan = []
    for s, lk in chosen:
        still = next((str(video.dir / "images" / (lk["id"] + e)) for e in (".jpg", ".jpeg", ".png", ".webp")
                      if (video.dir / "images" / (lk["id"] + e)).exists()), None)
        motion = lk.get("clip") or bp.get("clip_default_motion", "the hero subject moves a little")
        plan.append({"look": lk["id"], "segment": s["id"], "title": s["title"], "still": still,
                     "prompt": bp["clip_prompt"].format(motion=motion), "negative": bp["clip_negative"],
                     "seconds": 5, "aspect": "16:9", "model": MODEL})
    out = video.dir / "clips"
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps({"clips": plan}, indent=1, ensure_ascii=False) + "\n")
    no_still = [p["look"] for p in plan if not p["still"]]
    print("wrote clips/plan.json: %d clips (cap %d)%s" % (len(plan), cap, "; no still yet for %s" % ", ".join(no_still) if no_still else ""))


def cmd_collect(a):
    dl = Path(a.downloads).expanduser()
    since = a.since or (time.time() - 3600)
    vids = sorted((p for p in dl.glob("*.mp4") if p.stat().st_mtime >= since), key=lambda p: p.stat().st_mtime)
    if not vids:
        sys.exit("no .mp4 in %s newer than %s" % (dl, time.strftime("%H:%M:%S", time.localtime(since))))
    newest = vids[-1]
    if len(vids) > 1 and not a.newest:
        sys.exit("%d new .mp4 files in Downloads (%s); download one clip at a time, or pass --newest"
                 % (len(vids), ", ".join(p.name for p in vids)))
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (a.as_ + ".mp4")
    if dest.exists() and not a.replace:
        sys.exit("%s exists already (pass --replace)" % dest)
    shutil.move(str(newest), str(dest))
    print("%s <- %s" % (dest.name, newest.name))


def cmd_check(a):
    c = engine()
    video = c.Video(a.video)
    plan = c.load_json(video.dir / "clips" / "plan.json", {"clips": []})["clips"]
    have, missing = 0, []
    for p in plan:
        f = video.dir / "clips" / (p["look"] + ".mp4")
        if not f.exists():
            missing.append(p["look"])
            continue
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height:format=duration", "-of", "json", str(f)], capture_output=True, text=True)
        js = json.loads(r.stdout or "{}")
        st = (js.get("streams") or [{}])[0]
        d = float(js.get("format", {}).get("duration", 0))
        note = "" if d >= 2 else "  TOO SHORT: delete it, the look keeps its still"
        print("%-14s %4.1fs %sx%s%s" % (p["look"], d, st.get("width"), st.get("height"), note))
        have += 1
    print("%d of %d planned clips are here%s" % (have, len(plan), "; still to make: %s" % ", ".join(missing) if missing else ""))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("video")
    p.add_argument("--max", type=int)
    c = sub.add_parser("collect")
    c.add_argument("--as", dest="as_", required=True, help="the look id this clip belongs to")
    c.add_argument("--out", required=True, help="the video folder's clips folder")
    c.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    c.add_argument("--since", type=float, help="only files newer than this (epoch seconds); default the last hour")
    c.add_argument("--newest", action="store_true", help="take the newest even when there are several")
    c.add_argument("--replace", action="store_true")
    k = sub.add_parser("check")
    k.add_argument("video")
    a = ap.parse_args()
    {"plan": cmd_plan, "collect": cmd_collect, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()

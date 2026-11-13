#!/usr/bin/env python3
"""qa.py: the checks the long video and the shorts get before anything is uploaded. Nothing here asks a model.

  python3 engine/qa.py render <video folder> [--tag _pilot]
      length (and that it matches the timeline), streams, loudness (-14 LUFS, true peak under -1.5 dBTP), silences
      over 4 seconds inside the body (a missing take shows up here), black over 1 second, stills still missing, and
      contact sheets of every section card, the middle of every look, every brand card and the end, for a person to
      look at: out/qa/<slug>_sheet_N.jpg
  python3 engine/qa.py shorts <video folder> [--only seg-003 or short-seg-003]
      1080x1920, audio, length (a short over 3 minutes won't post; over 60 seconds gets a note), loudness, and every
      caption drawn alone by libass and measured against the safe margins; a contact sheet out/qa/shorts_all.jpg
Exits 1 on any problem.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Video  # noqa: E402

POP = "{\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}"


def run(*a):
    return subprocess.run([str(x) for x in a], capture_output=True, text=True)


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def frame(src, t, w=640, h=None):
    vf = "scale=%d:%d" % (w, h) if h else "scale=%d:-2" % w
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.2f" % max(0, t), "-i", str(src), "-frames:v", "1", "-vf", vf,
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(BytesIO(r.stdout)).convert("RGB") if r.stdout else Image.new("RGB", (w, h or w * 9 // 16), "red")


def loudness(path):
    ln = run("ffmpeg", "-hide_banner", "-i", path, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-vn", "-f", "null", "-")
    return json.loads(ln.stderr[ln.stderr.rindex("{"):])


def cmd_render(a):
    video = Video(a.video)
    cut = video.out / (video.cfg["slug"] + a.tag + ".mp4")
    tl = json.loads(cut.with_suffix(".json").read_text())
    probs = []
    pr = json.loads(run("ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                        "-of", "json", cut).stdout)
    d = float(pr["format"]["duration"])
    print("length %.1f s (%d:%02d), timeline %.1f s" % (d, d // 60, d % 60, tl["seconds"]))
    kinds = [s["codec_type"] for s in pr["streams"]]
    if "video" not in kinds or "audio" not in kinds:
        probs.append("missing a video or audio stream")
    v = next((s for s in pr["streams"] if s["codec_type"] == "video"), {})
    if (v.get("width"), v.get("height")) != (1920, 1080):
        probs.append("not 1920x1080")
    m = loudness(cut)
    print("loudness %s LUFS, true peak %s dBTP (target -14 / -1.5)" % (m["input_i"], m["input_tp"]))
    if abs(float(m["input_i"]) + 14) > 1:
        probs.append("loudness %s LUFS" % m["input_i"])
    if float(m["input_tp"]) > -1.0:
        probs.append("true peak %s dBTP" % m["input_tp"])
    body = [i for i in tl["items"] if i["kind"] != "end"]
    b0, b1 = 0.0, body[-1]["start"] + body[-1]["length"] if body else 0.0
    sil = run("ffmpeg", "-hide_banner", "-i", cut, "-af", "silencedetect=n=-45dB:d=4", "-vn", "-f", "null", "-").stderr
    gaps = [(float(x), float(y)) for x, y in re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)", sil)]
    gaps = [g for g in gaps if b0 < g[0] < b1]
    print("silences over 4 s inside the body: %s" % (gaps or "none"))
    if gaps:
        probs.append("silence inside the body at %s" % ", ".join("%.0fs" % g[0] for g in gaps))
    blk = run("ffmpeg", "-hide_banner", "-i", cut, "-vf", "blackdetect=d=1:pix_th=0.06", "-an", "-f", "null", "-").stderr
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", blk)
    print("black stretches over 1 s: %s" % (blacks or "none"))
    if blacks:
        probs.append("black frames")
    if tl.get("missing_pictures"):
        probs.append("no picture yet for %s (shown as a title card)" % ", ".join(tl["missing_pictures"]))
    shots = [(1.0, "title")]
    for it in tl["items"]:
        t = it["start"]
        for w in it["windows"]:
            ln = w["frames"] / 30
            label = it["kind"] if it["kind"] != "segment" else "%s %s" % (it["id"], w.get("look") or "")
            if w.get("clip"):
                label += " clip"
            first = it["kind"] == "segment" and w is it["windows"][0]
            shots.append((t + (min(3.0, ln / 2) if first else min(ln / 2, 8)), label.strip()))   # 3 s in shows the lower third
            t += ln
    for p in tl.get("pitch_cards", []):
        shots.append(((p["window"][0] + p["window"][1]) / 2, "%s brand card" % p["id"]))
    shots.append((d - 2, "end"))
    shots.sort()
    qa = video.out / "qa"
    qa.mkdir(exist_ok=True)
    f, per, n = font(20), 16, 0
    for s in range(0, len(shots), per):
        sheet = Image.new("RGB", (4 * 640, 4 * 360), "black")
        for k, (t, label) in enumerate(shots[s:s + per]):
            im = frame(cut, t)
            dr = ImageDraw.Draw(im)
            txt = "%s  %d:%02d" % (label, t // 60, t % 60)
            dr.rectangle([0, 0, 11 * len(txt) + 10, 26], fill="yellow")
            dr.text((4, 2), txt, fill="black", font=f)
            sheet.paste(im, ((k % 4) * 640, (k // 4) * 360))
        n += 1
        sheet.save(qa / ("%s%s_sheet_%d.jpg" % (video.cfg["slug"], a.tag, n)), quality=80)
    print("contact sheets: %d in %s" % (n, qa))
    for p in probs:
        print("PROBLEM " + p)
    print("ok" if not probs else "%d problem(s)" % len(probs))
    sys.exit(1 if probs else 0)


def stamp(t):
    return "0:%02d:%02d.%02d" % (t // 60, t % 60, round((t % 1) * 100) % 100)


def caption_problems(ass_path, tmp):
    W, H = 1080, 1920
    src = Path(ass_path).read_text()
    head, ev = src.split("[Events]\n", 1)
    fmt, *rows = [r for r in ev.splitlines() if r.strip()]
    out = []
    for i, r in enumerate(rows):
        p = r.split(",", 9)
        out.append(",".join(p[:1] + [stamp(i * 0.1), stamp((i + 1) * 0.1)] + p[3:9] + [p[9].replace(POP, "")]))
    f = Path(tmp) / (Path(ass_path).stem + ".ass")
    f.write_text(head + "[Events]\n" + fmt + "\n" + "\n".join(out) + "\n")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=%dx%d:r=10:d=%.1f" % (W, H, len(rows) * 0.1 + 0.05),
                          "-vf", "ass=%s" % f, "-frames:v", str(len(rows)), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W) if raw else []
    bad = []
    for i, fr in enumerate(frames):
        ys, xs = np.nonzero(fr > 60)
        if len(xs) and (xs.min() < 80 or xs.max() > 935 or ys.max() - ys.min() > 200):
            bad.append("%s (x %d to %d, %d px tall)" % (re.sub(r"\{[^}]*\}", "", rows[i].split(",", 9)[9]).replace("\\N", " "),
                                                         xs.min(), xs.max(), ys.max() - ys.min()))
    return len(rows), sorted(set(bad))


def cmd_shorts(a):
    video = Video(a.video)
    odir = video.out / "shorts"
    index = json.loads((odir / "shorts.json").read_text())
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    rows = [r for r in index if (not only or r["id"] in only or r["id"].removeprefix("short-") in only)
            and not r.get("skipped")]
    fails, sheet = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for r in rows:
            f = odir / r["file"]
            if not f.exists():
                print("%-24s missing" % r["id"])
                fails += 1
                continue
            pr = json.loads(run("ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                "-of", "json", f).stdout)
            v = [s for s in pr["streams"] if s["codec_type"] == "video"]
            au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
            d = float(pr["format"]["duration"])
            m = loudness(f)
            events, bad = caption_problems(video.work / "shorts" / ("captions_%s.ass" % r["id"]), tmp)
            probs, notes = [], []
            if not v or (v[0]["width"], v[0]["height"]) != (1080, 1920):
                probs.append("not 1080x1920")
            if not au:
                probs.append("no audio")
            if d > 180:
                probs.append("%.0f s: over the 3-minute Shorts limit" % d)
            elif d > 60:
                notes.append("%.0f s: over a minute" % d)
            if abs(float(m["input_i"]) + 14) > 1:
                probs.append("loudness %s LUFS" % m["input_i"])
            if float(m["input_tp"]) > -1:
                probs.append("true peak %s dBTP" % m["input_tp"])
            probs += ["caption off the safe area: " + b for b in bad]
            fails += bool(probs)
            print("%-24s %5.1f s %5.1f MB %6s LUFS %5s dBTP %3d captions  %s" % (
                r["id"], d, f.stat().st_size / 1048576, m["input_i"], m["input_tp"], events,
                "; ".join(probs + notes) or "ok"), flush=True)
            sheet.append((r["id"], frame(f, d / 2, 216, 384)))
    cols = 10
    im = Image.new("RGB", (cols * 216, max(1, (len(sheet) + cols - 1) // cols) * 384), "black")
    ft = font(16)
    for k, (sid, fr) in enumerate(sheet):
        dr = ImageDraw.Draw(fr)
        lab = sid.replace("short-", "")
        dr.rectangle([0, 360, 9 * len(lab) + 8, 384], fill="yellow")
        dr.text((4, 363), lab, fill="black", font=ft)
        im.paste(fr, ((k % cols) * 216, (k // cols) * 384))
    qa = video.out / "qa"
    qa.mkdir(exist_ok=True)
    p = qa / "shorts_all.jpg"
    im.save(p, quality=82)
    print("%d shorts checked, %d with problems; contact sheet %s" % (len(rows), fails, p))
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("video")
    r.add_argument("--tag", default="")
    s = sub.add_parser("shorts")
    s.add_argument("video")
    s.add_argument("--only", default="")
    a = ap.parse_args()
    {"render": cmd_render, "shorts": cmd_shorts}[a.cmd](a)


if __name__ == "__main__":
    main()

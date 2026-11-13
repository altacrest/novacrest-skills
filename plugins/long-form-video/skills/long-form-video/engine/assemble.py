#!/usr/bin/env python3
"""assemble.py: the long video, from the narration, the stills, the clips and the brand's cards.

  python3 engine/assemble.py <video folder> [--draft] [--sections 1,2] [--tag _pilot]

Order: the cold open (the title card first, then the open's own stills) -> for each section, its card (the iceberg
level on the berg, the argument's step, the answers' part) with the section's intro spoken over it -> each segment
over its stills, a still per look, split at the sentence nearest an even share of the segment, a Higgsfield clip
opening a look when clips/<look id>.mp4 exists -> the outro over the end card, then a 12-second hold for YouTube's
end screen. Music (the brand's track, when it's in the video folder) runs under everything and dips whenever the
narrator speaks. Loudness ends at -14 LUFS for YouTube. Every cut comes from the narration's lengths and word times;
nothing is judged by a model.

  --draft      faster encode (quick look; not for upload)
  --sections   only these sections (plus the open and the outro), for a pilot
  --tag        added to the output names

Writes out/<slug><tag>.mp4 and out/<slug><tag>.json (the timeline: items, chapters, card windows) for qa.py, meta.py
and shorts.py. Work files go to build/assembly<tag>/ and are reused on a rerun when nothing changed.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ENGINE, FORMATS, FPS, Video, align, dur, ff, find_phrase, run_json, script_words  # noqa: E402

W, H = 1920, 1080
PW, PH = 3840, 2160
PAD = {"open": (0.25, 0.35), "section": (1.0, 0.7), "segment": (0.3, 0.7), "outro": (0.6, 0.6)}
SECTION_SILENT = 2.6
TITLE_FIRST = 3.2          # the title card opens the video, under the first words of the cold open
END_HOLD = 12.0            # YouTube allows end-screen elements in the last 5 to 20 seconds
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def enc(draft):
    # tune stillimage suits slow moves over illustrations: about 9 to 14 MB a minute at crf 21 (measured Nov 2026)
    return ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "28" if draft else "21",
            "-g", "60", "-pix_fmt", "yuv420p", "-r", str(FPS), "-video_track_timescale", "15360"]


def frames(t):
    return max(1, int(round(t * FPS)))


# ---------------- pictures ----------------
def plate(src, out):
    """a 4K 16:9 plate: the picture filling the frame, or fitted over a blurred copy of itself"""
    from PIL import Image, ImageEnhance, ImageFilter
    if out.exists() and out.stat().st_mtime >= Path(src).stat().st_mtime:
        return out
    im = Image.open(src).convert("RGB")
    r = im.width / im.height
    if abs(r - PW / PH) / (PW / PH) < 0.12:
        s = max(PW / im.width, PH / im.height)
        im2 = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x, y = (im2.width - PW) // 2, (im2.height - PH) // 2
        im2.crop((x, y, x + PW, y + PH)).save(out, quality=92)
        return out
    s = max(PW / im.width, PH / im.height)
    bg = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (bg.width - PW) // 2, (bg.height - PH) // 2
    bg = bg.crop((x, y, x + PW, y + PH)).filter(ImageFilter.GaussianBlur(60))
    bg = ImageEnhance.Brightness(bg).enhance(0.75)
    s = min(PW / im.width, PH / im.height)
    fg = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    bg.paste(fg, ((PW - fg.width) // 2, (PH - fg.height) // 2))
    bg.save(out, quality=92)
    return out


def find_image(video, look_id):
    for ext in IMG_EXT:
        p = video.dir / "images" / (look_id + ext)
        if p.exists():
            return p
    return None


def find_clip(video, look_id):
    p = video.dir / "clips" / (look_id + ".mp4")
    return p if p.exists() else None


def last_frame(clip, out):
    if not out.exists():
        ff("-sseof", "-0.08", "-i", clip, "-frames:v", "1", "-q:v", "2", "-update", "1", out)
    return out


# ---------------- camera ----------------
def hold(n):
    return "loop=loop=%d:size=1:start=0,setpts=N/%d/TB" % (n - 1, FPS)


def zoom_expr(n, z0, z1, c0, c1):
    p = "min(on/%d,1)" % max(n - 1, 1)
    e = "(%s*%s*(3-2*%s))" % (p, p, p)
    z = "%s+(%s-%s)*%s" % (z0, z1, z0, e)
    cx = "%s+(%s-%s)*%s" % (c0[0], c1[0], c0[0], e)
    cy = "%s+(%s-%s)*%s" % (c0[1], c1[1], c0[1], e)
    x = "max(0,min(iw-iw/zoom,%s-iw/zoom/2))" % cx
    y = "max(0,min(ih-ih/zoom,%s-ih/zoom/2))" % cy
    return "zoompan=z='%s':x='%s':y='%s':d=1:s=%dx%d:fps=%d" % (z, x, y, W, H, FPS)


CENTER = (PW // 2, PH // 2)


def move_for(k, kind):
    if kind == "plate":
        return 1.0, 1.04, CENTER, CENTER
    drift = 110 if k % 2 else -110
    return 1.0, 1.08, CENTER, (CENTER[0] + drift, CENTER[1] + (40 if k % 3 else -40))


# ---------------- the plan ----------------
def chapter_title(fmt, sec):
    if fmt == "iceberg":
        n = re.sub(r"\D", "", sec["label"])
        return "Level %s: %s" % (n, sec["name"]) if sec["name"] else "Level %s" % n
    lab = sec["label"].capitalize()
    return "%s: %s" % (lab, sec["name"]) if sec["name"] else lab


def split_windows(seg_len, pre, text, words, k):
    """cut a segment of seg_len seconds into k windows at the sentence ends nearest an even share"""
    if k <= 1:
        return [seg_len]
    from common import sentence_ends
    ends = sorted(pre + e for e in sentence_ends(text, words) if 1.5 < pre + e < seg_len - 1.5)
    cuts, last = [], 0.0
    for i in range(1, k):
        target = seg_len * i / k
        cand = [e for e in ends if e - last >= 2.5 and seg_len - e >= 2.5 * (k - i)]
        c = min(cand, key=lambda e: abs(e - target)) if cand else target
        if c - last < 1.0:
            c = target
        cuts.append(c)
        last = c
    pts = [0.0] + cuts + [seg_len]
    return [pts[i + 1] - pts[i] for i in range(k)]


def build_plan(video, man, rep, sections_only=None):
    fmt = video.format
    segs = man["segments"]
    secs = {s["index"]: s for s in man["meta"]["sections"]}
    nlev = len(man["meta"]["sections"])
    numbered = [s for s in segs if s["kind"] == "segment"]
    steps = ["The problem", "Futures", "The verdict", "The fix"]
    items, seen_sections = [], set()
    for s in segs:
        if sections_only and s["kind"] in ("segment", "section") and s["section"] not in sections_only:
            continue
        if s["kind"] in ("segment",) and s["section"] not in seen_sections:
            seen_sections.add(s["section"])
            sec = secs[s["section"]]
            if not any(x["kind"] == "section" and x["section"] == s["section"] for x in segs):
                items.append({"kind": "section", "id": "card-%02d" % s["section"], "section": s["section"],
                              "voice": None, "voice_s": 0.0, "words": [], "text": "", "seg": None, "sec": sec})
        if s["kind"] == "section":
            seen_sections.add(s["section"])
        v = rep["segments"].get(s["id"])
        if not v:
            raise SystemExit("no narration for %s yet (voice.py makes it)" % s["id"])
        items.append({"kind": s["kind"], "id": s["id"], "section": s["section"], "voice": v["file"],
                      "voice_s": float(v["seconds"]), "words": v.get("words", []), "text": s["narration"], "seg": s,
                      "sec": secs.get(s["section"])})
    items.append({"kind": "end", "id": "end", "section": None, "voice": None, "voice_s": 0.0, "words": [], "text": "",
                  "seg": None, "sec": None})

    def step_of(sec):
        lab = sec["label"]
        return 0 if lab.startswith("THE PROBLEM") else 1 if lab.startswith("FUTURE") else 2 if lab.startswith(("THE VERDICT", "CONCLUSION")) else 3

    t = 0.0
    first_open = True
    for it in items:
        kind = it["kind"]
        if kind == "end":
            length = END_HOLD
        elif it["voice"] is None:
            length = SECTION_SILENT
        else:
            pre, post = PAD[kind]
            length = pre + it["voice_s"] + post
        it["pre"] = PAD.get(kind, (0, 0))[0] if it["voice"] else 0.0
        wins = []
        if kind in ("section",):
            sec = it["sec"]
            extra = {"format": fmt, "label": sec["label"], "name": sec["name"], "n": int(re.sub(r"\D", "", sec["label"]) or 0)}
            if fmt == "iceberg":
                extra["levels"] = nlev
                extra["label"] = "LEVEL %d OF %d" % (extra["n"], nlev)
            if fmt == "argument":
                extra["steps"], extra["step"] = steps, step_of(sec)
            wins.append({"type": "plate", "card": "section_%02d.png" % sec["index"], "extra": extra, "length": length})
        elif kind in ("outro", "end"):
            wins.append({"type": "plate", "card": "end.png", "length": length})
        else:
            looks = it["seg"]["looks"]
            shares = split_windows(length, it["pre"], it["text"], it["words"], max(1, len(looks)))
            if not looks:
                wins.append({"type": "stat", "card": "stat_%s.png" % it["id"], "length": length,
                             "extra": {"big": it["seg"]["title"] or "", "small": "", "kicker": kicker(fmt, it, numbered)}})
            for lk, share in zip(looks, shares):
                if lk.get("stat"):
                    wins.append({"type": "stat", "look": lk["id"], "card": "stat_%s.png" % lk["id"], "length": share,
                                 "extra": {"big": lk["stat"][0], "small": lk["stat"][1], "kicker": kicker(fmt, it, numbered)}})
                    continue
                img, clip = find_image(video, lk["id"]), find_clip(video, lk["id"])
                if img is None and clip is None:
                    wins.append({"type": "stat", "look": lk["id"], "card": "stat_%s.png" % lk["id"], "length": share,
                                 "missing": True,
                                 "extra": {"big": it["seg"]["title"] or "", "small": "", "kicker": kicker(fmt, it, numbered)}})
                    continue
                wins.append({"type": "still", "look": lk["id"], "image": str(img) if img else None,
                             "clip": str(clip) if clip else None, "length": share})
            if kind == "open" and first_open:
                first = wins[0]
                cut = min(TITLE_FIRST, first["length"] * 0.6) if first["type"] != "plate" else 0
                if cut > 1.0:
                    first["length"] -= cut
                    wins.insert(0, {"type": "plate", "card": "title.png", "length": cut})
                elif first["type"] == "stat" and first.get("missing"):
                    first.update({"type": "plate", "card": "title.png"})
            if kind == "open" and not looks:
                wins = [{"type": "plate", "card": "title.png", "length": length}]
        if kind == "open":
            first_open = False
        # whole frames per window; the item's length is their sum, so audio and video stay in step
        total = 0
        for w in wins:
            w["frames"] = frames(w["length"])
            total += w["frames"]
        it["frames"] = total
        it["length"] = total / FPS
        it["windows"] = wins
        it["start"] = round(t, 3)
        t += it["length"]
    return items


def kicker(fmt, it, numbered):
    sec = it.get("sec") or {}
    if fmt == "iceberg":
        n = re.sub(r"\D", "", sec.get("label", ""))
        return ("LEVEL %s · %s" % (n, sec.get("name", ""))).strip(" ·")
    if fmt == "answers":
        k = [s["id"] for s in numbered].index(it["id"]) + 1 if it["id"] in [s["id"] for s in numbered] else 0
        return "QUESTION %d OF %d" % (k, len(numbered))
    lab = sec.get("label", "")
    return ("%s · %s" % (lab, sec.get("name", ""))).strip(" ·")


# ---------------- cards and overlays ----------------
def card_spec(video, man, items, odir):
    fmt = video.format
    numbered = [s for s in man["segments"] if s["kind"] == "segment"]
    nsec = len(man["meta"]["sections"])
    kick = FORMATS[fmt]["kicker"].format(n=len(numbered), levels=nsec)
    spec = [{"file": "title.png", "kind": "title", "transparent": False,
             "extra": {"title": video.cfg["title"], "kicker": video.cfg.get("kicker") or kick}},
            {"file": "end.png", "kind": "end", "transparent": False, "extra": {"cta": video.brand.get("end_cta")}},
            {"file": "badge_image.png", "kind": "badge", "extra": {"text": "AI IMAGE"}},
            {"file": "badge_video.png", "kind": "badge", "extra": {"text": "AI VIDEO"}}]
    seen = set()
    for it in items:
        for w in it["windows"]:
            if w.get("card") and w["card"] not in seen and w["card"] not in ("title.png", "end.png"):
                seen.add(w["card"])
                spec.append({"file": w["card"], "kind": "section" if w["card"].startswith("section") else "stat",
                             "transparent": False, "extra": w.get("extra", {})})
        if it["kind"] == "segment":
            s = it["seg"]
            if fmt == "answers":
                spec.append({"file": "lower_%s.png" % it["id"], "kind": "question",
                             "extra": {"kicker": kicker(fmt, it, numbered), "title": s["title"]}})
            else:
                spec.append({"file": "lower_%s.png" % it["id"], "kind": "lower",
                             "extra": {"kicker": kicker(fmt, it, numbered), "n": s["number"], "title": s["title"]}})
            src = " · ".join(t for t, _ in s["sources"])[:150]
            if src:
                spec.append({"file": "source_%s.png" % it["id"], "kind": "source", "extra": {"source": src}})
            if s.get("card"):
                say = pitch_sentence(video, it)
                if say:
                    spec.append({"file": "pitch_%s.png" % it["id"], "kind": "pitch", "extra": {"say": say}})
    brand = dict(video.brand, dir=str(video.brand_dir))
    path = odir / "cards.json"
    path.write_text(json.dumps({"brand": brand, "out": str(odir / "png"), "items": spec}, indent=1, ensure_ascii=False))
    import subprocess
    r = subprocess.run(["node", str(ENGINE / "render.mjs"), str(path), "--force"], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("card render failed:\n" + r.stderr[-2500:])
    print(r.stdout.strip(), flush=True)
    return odir / "png"


def pitch_sentence(video, it):
    """the line the card shows while it's spoken: the sentence between the card's words that names the brand
    (else the first sentence of that stretch)"""
    s = it["seg"]
    if not s.get("card"):
        return None
    flat = lambda x: " ".join(re.findall(r"[\w']+", x.lower()))
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", s["narration"]) if x.strip()]
    a, b = flat(s["card"][0]), flat(s["card"][1])
    i0 = next((i for i, x in enumerate(sents) if a in flat(x)), None)
    i1 = next((i for i, x in enumerate(sents) if b in flat(x) and (i0 is None or i >= i0)), None)
    span = sents[i0:(i1 if i1 is not None else i0) + 1] if i0 is not None else sents
    pat = re.compile(video.brand.get("pitch_name") or "$^", re.I)
    return next((x for x in span if pat.search(x)), span[0] if span else None)


# ---------------- video ----------------
def fade_layer(i, a, b, fade=0.3):
    return ("[%d:v]format=rgba,fade=t=in:st=%.3f:d=%s:alpha=1,fade=t=out:st=%.3f:d=%s:alpha=1[o%d]"
            % (i, a, fade, max(a, b - fade), fade, i))


def render_item(video, it, png, work, k, draft):
    out = work / "clips" / ("%03d_%s.mp4" % (k, it["id"]))
    deps = [png / w["card"] for w in it["windows"] if w.get("card")]
    deps += [Path(w[x]) for w in it["windows"] for x in ("image", "clip") if w.get(x)]
    deps += [Path(l[0]) for l in it.get("layers", [])]
    stamps = [(str(p), hashlib.sha1(p.read_bytes()).hexdigest()[:10] if p.suffix == ".png" else
               (p.stat().st_mtime, p.stat().st_size)) for p in deps if p.exists()]   # cards are redrawn every run
    sig = hashlib.sha1(json.dumps([it["windows"], it.get("layers", []), it["frames"], enc(draft), stamps], sort_keys=True,
                                  default=str).encode()).hexdigest()[:12]
    stamp = out.with_suffix(".sig")
    if out.exists() and stamp.exists() and stamp.read_text() == sig:
        return out
    pdir = work / "plates"
    args, graph, labels, n_in = [], [], [], 0
    for j, w in enumerate(it["windows"]):
        if w["type"] in ("plate", "stat"):
            src = plate(png / w["card"], pdir / ("card_%s.jpg" % Path(w["card"]).stem))
            z0, z1, c0, c1 = move_for(j, "plate")
            parts = [(src, w["frames"], None)]
        else:
            parts = []
            fr = w["frames"]
            if w.get("clip"):
                cf = min(fr, frames(dur(w["clip"])))
                if fr - cf < FPS * 0.6:
                    cf = fr
                parts.append(("clip", cf, w["clip"]))
                fr -= cf
                if fr > 0:
                    lf = last_frame(Path(w["clip"]), pdir / ("last_%s.png" % w["look"]))
                    parts.append((plate(lf, pdir / ("lastp_%s.jpg" % w["look"])), fr, None))
            elif w.get("image"):
                parts.append((plate(Path(w["image"]), pdir / ("img_%s.jpg" % w["look"])), fr, None))
            z0, z1, c0, c1 = move_for(k + j, "still")
        for src, nf, clip in parts:
            if nf <= 0:
                continue
            lab = "w%d" % len(labels)
            if src == "clip":
                args += ["-i", clip]
                graph.append("[%d:v]setpts=PTS-STARTPTS,fps=%d,scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                             "setsar=1,tpad=stop_mode=clone:stop=%d,trim=end_frame=%d,format=yuv420p[%s]"
                             % (n_in, FPS, W, H, W, H, nf, nf, lab))
            else:
                args += ["-i", src]
                graph.append("[%d:v]%s,%s,setsar=1,format=yuv420p[%s]" % (n_in, hold(nf), zoom_expr(nf, z0, z1, c0, c1), lab))
            labels.append(lab)
            n_in += 1
    graph.append("%sconcat=n=%d:v=1:a=0[bg]" % ("".join("[%s]" % x for x in labels), len(labels)))
    last = "bg"
    L = it["length"]
    for png_file, a, b in it.get("layers", []):
        args += ["-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % L, "-i", png_file]
        graph.append(fade_layer(n_in, a, b))
        graph.append("[%s][o%d]overlay=0:0:enable='between(t,%.3f,%.3f)'[v%d]" % (last, n_in, a, b, n_in))
        last = "v%d" % n_in
        n_in += 1
    graph.append("[%s]format=yuv420p[v]" % last)
    ff(*args, "-filter_complex", ";".join(graph), "-map", "[v]", "-frames:v", it["frames"], *enc(draft), "-an", out)
    stamp.write_text(sig)
    return out


def layers_for(video, it, png):
    """the overlays of one item: (png, start, end) in the item's own seconds"""
    if it["kind"] != "segment":
        return []
    L, s, pre = it["length"], it["seg"], it["pre"]
    lays = [(str(png / ("lower_%s.png" % it["id"])), 0.5, min(L - 0.3, 6.5))]
    if (png / ("source_%s.png" % it["id"])).exists():
        lays.append((str(png / ("source_%s.png" % it["id"])), 1.2, L - 0.4))
    t = 0.0
    for w in it["windows"]:
        fl = w["frames"] / FPS
        if w["type"] == "still":
            clip_part = 0.0
            if w.get("clip"):
                cf = min(w["frames"], frames(dur(w["clip"])))
                clip_part = w["frames"] / FPS if w["frames"] - cf < FPS * 0.6 else cf / FPS
                lays.append((str(png / "badge_video.png"), t, t + clip_part))
            if fl - clip_part > 0.05:
                lays.append((str(png / "badge_image.png"), t + clip_part, t + fl))
        t += fl
    if s.get("card") and (png / ("pitch_%s.png" % it["id"])).exists():
        ws = script_words(it["text"], it["words"])
        a = find_phrase(ws, s["card"][0])
        b = find_phrase(ws, s["card"][1], after=a or 0, last=True)
        if a is not None and b is not None:
            a, b = pre + a - 0.2, pre + b + 1.2
            it["pitch_window"] = [round(it["start"] + max(a, 6.6), 2), round(it["start"] + min(b, L - 0.1), 2)]
            lays.append((str(png / ("pitch_%s.png" % it["id"])), max(a, 6.6), min(b, L - 0.1)))
        else:
            print("  note: the card words of %s weren't found in its take; no card" % it["id"])
    return lays


# ---------------- audio ----------------
def wav(src, out, length, pre=0.0):
    ms = int(round(pre * 1000))
    ff("-i", src, "-af", "aformat=sample_rates=48000:channel_layouts=stereo,adelay=%d|%d,apad=whole_dur=%.3f,atrim=0:%.3f"
       % (ms, ms, length, length), "-ar", 48000, "-ac", 2, out)


def silence(out, length):
    ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "%.3f" % length, "-ar", 48000, "-ac", 2, out)


def concat_audio(parts, out):
    lst = out.with_suffix(".txt")
    lst.write_text("".join("file '%s'\n" % p.resolve() for p in parts))
    ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", out)


def music_bed(track, seconds, out):
    n = max(1, int(seconds // max(dur(track) - 6, 30)) + 1)
    ins, graph = [], []
    for k in range(n):
        ins += ["-i", track]
        graph.append("[%d:a]aformat=sample_rates=48000:channel_layouts=stereo[m%d]" % (k, k))
    last = "m0"
    for k in range(1, n):
        graph.append("[%s][m%d]acrossfade=d=4:c1=tri:c2=tri[x%d]" % (last, k, k))
        last = "x%d" % k
    graph.append("[%s]apad,atrim=0:%.3f,afade=t=in:st=0:d=1.5,afade=t=out:st=%.3f:d=5[bed]" % (last, seconds, max(0, seconds - 5)))
    ff(*ins, "-filter_complex", ";".join(graph), "-map", "[bed]", "-ar", 48000, "-ac", 2, out)


def audio(video, items, work, out_aac):
    adir = work / "audio"
    adir.mkdir(parents=True, exist_ok=True)
    parts = []
    for k, it in enumerate(items):
        p = adir / ("%03d.wav" % k)
        if it["voice"]:
            wav(video.dir / "voice" / it["voice"], p, it["length"], it["pre"])
        else:
            silence(p, it["length"])
        parts.append(p)
    narr = adir / "narration.wav"
    concat_audio(parts, narr)
    total = sum(it["length"] for it in items)
    mixed = adir / "mix.wav"
    track = video.music()
    if track:
        bed = adir / "bed.wav"
        music_bed(track, total, bed)
        ff("-i", narr, "-i", bed, "-filter_complex",
           "[0:a]asplit=2[vo][sc];[1:a]volume=0.30[b];"
           "[b][sc]sidechaincompress=threshold=0.012:ratio=10:attack=15:release=500[duck];"
           "[vo][duck]amix=inputs=2:normalize=0[a]", "-map", "[a]", "-ar", 48000, "-ac", 2, mixed)
    else:
        print("  note: no music file in the video folder (brand.json, music); the video has narration only")
        mixed = narr
    m = run_json(["ffmpeg", "-hide_banner", "-i", str(mixed), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                  "-f", "null", "-"])
    ff("-i", mixed, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:"
       "offset=%s:linear=true,aresample=48000" % (m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"],
                                               m["target_offset"]), "-c:a", "aac", "-b:a", "192k", out_aac)


# ---------------- main ----------------
def chapters(video, man, items):
    fmt = video.format
    secs = {s["index"]: s for s in man["meta"]["sections"]}
    ch = [{"t": 0.0, "title": "Intro"}]
    done = set()
    for it in items:
        if FORMATS[fmt]["chapters"] == "sections" and it["kind"] in ("section", "segment") and it["section"] not in done:
            done.add(it["section"])
            ch.append({"t": it["start"], "title": chapter_title(fmt, secs[it["section"]])})
        if FORMATS[fmt]["chapters"] == "segments" and it["kind"] == "segment":
            ch.append({"t": it["start"], "title": it["seg"]["title"]})
        if it["kind"] in ("outro",) and "outro" not in done:
            done.add("outro")
            ch.append({"t": it["start"], "title": "Wrap-up"})
    keep = []
    end = sum(i["length"] for i in items)
    for c, nxt in zip(ch, ch[1:] + [{"t": end}]):
        if keep and nxt["t"] - c["t"] < 10:            # YouTube wants every chapter at least 10 seconds long
            continue
        keep.append(c)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--sections", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    video = Video(a.video)
    man, rep = video.manifest(), video.report()
    only = {int(x) for x in a.sections.split(",") if x.strip()} or None
    work = video.work / ("assembly" + a.tag)
    for d in ("cards", "plates", "clips", "audio"):
        (work / d).mkdir(parents=True, exist_ok=True)
    video.out.mkdir(parents=True, exist_ok=True)
    items = build_plan(video, man, rep, only)
    png = card_spec(video, man, items, work / "cards")
    missing = [w["look"] for it in items for w in it["windows"] if w.get("missing")]
    for it in items:
        it["layers"] = layers_for(video, it, png)
    total = sum(i["length"] for i in items)
    print("%d items, %.1f minutes%s" % (len(items), total / 60, "" if not missing else "; no picture yet for %s" % ", ".join(missing)), flush=True)
    clips = []
    for k, it in enumerate(items):
        clips.append(render_item(video, it, png, work, k, a.draft))
        print("  %3d/%d %-10s %-8s %6.1fs  %d window(s)" % (k + 1, len(items), it["id"], it["kind"], it["length"],
                                                            len(it["windows"])), flush=True)
    lst = work / "video.txt"
    lst.write_text("".join("file '%s'\n" % p.resolve() for p in clips))
    vid = work / "video.mp4"
    ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", vid)
    aac = work / "audio" / "final.m4a"
    audio(video, items, work, aac)
    slug = video.cfg["slug"] + a.tag
    out = video.out / (slug + ".mp4")
    ff("-i", vid, "-i", aac, "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", "-shortest", out)
    tl = {"seconds": dur(out), "format": video.format, "title": video.cfg["title"], "chapters": chapters(video, man, items),
          "pitch_cards": [{"id": it["id"], "window": it["pitch_window"]} for it in items if it.get("pitch_window")],
          "missing_pictures": missing,
          "items": [{"id": it["id"], "kind": it["kind"], "start": it["start"], "length": round(it["length"], 3),
                     "section": it["section"], "title": (it["seg"] or {}).get("title"), "number": (it["seg"] or {}).get("number"),
                     "windows": [{k: w.get(k) for k in ("type", "look", "image", "clip", "card", "frames")} for w in it["windows"]]}
                    for it in items]}
    out.with_suffix(".json").write_text(json.dumps(tl, indent=1, ensure_ascii=False))
    mb = out.stat().st_size / 1e6
    print("wrote %s (%.1f minutes, %.0f MB) and its timeline" % (out, tl["seconds"] / 60, mb))
    if mb > 380:
        print("note: over 380 MB; the copy back to the Mac takes one file of at most 400 MB")


if __name__ == "__main__":
    main()

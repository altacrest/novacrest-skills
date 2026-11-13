#!/usr/bin/env python3
"""shorts.py: vertical shorts (1080x1920) for YouTube Shorts and Instagram Reels, cut from the long video's assets.

  python3 engine/shorts.py <video folder> [--only seg-003,seg-007] [--force]

What becomes a short depends on the format (formats/*.md):
  iceberg, answers   every numbered segment (an entry, a question) is a short on its own
  argument           every *(short: "first words" "last words")* mark: the words between them, from one segment

Nothing is voiced or drawn again. Each short has the segment's own take (trimmed to the words for a marked short),
the brand's music under it (ducked) and loudness at -14 LUFS; the look's Higgsfield clip when there is one, then its
still panned across the frame; the head block (AI badge, kicker, title, source); word-by-word captions spelled from
the script and timed by the take's word times; the brand card on the card words; a 2.8-second end card that points
to the full video. Text stays inside the Shorts/Reels safe area. Writes out/shorts/<short id>.mp4 and
out/shorts/shorts.json. A short that already exists is kept unless --force.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ENGINE, FPS, Video, align, dur, ff, find_phrase, run_json, script_words  # noqa: E402
from assemble import PAD, find_clip, find_image, frames, split_windows  # noqa: E402

W, H = 1080, 1920
SS = 1.5
PRE, TAIL, ENDLEN = 0.3, 0.45, 2.8
CAP_FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
CAP_SIZE, CAP_ROOM = 86, 810
_capfont = []


def ass_color(hexcolor):
    h = hexcolor.lstrip("#")
    return "&H00%s%s%s&" % (h[4:6], h[2:4], h[0:2])


def cap_width(s):
    if not _capfont:
        from PIL import ImageFont
        try:
            _capfont.append(ImageFont.truetype(CAP_FONT, CAP_SIZE))
        except OSError:
            _capfont.append(ImageFont.truetype(str(ENGINE / "gfx" / "fonts" / "inter-latin-900-normal.woff2"), CAP_SIZE))
    l, _, r, _ = _capfont[0].getbbox(s)
    return 0.85 * (r - l)


def fit_word(w):
    if cap_width(w) <= CAP_ROOM:
        return w
    cuts = [i + 1 for i, ch in enumerate(w) if ch == "-" and 0 < i < len(w) - 1]
    if cuts:
        i = min(cuts, key=lambda i: max(cap_width(w[:i]), cap_width(w[i:])))
        if max(cap_width(w[:i]), cap_width(w[i:])) <= CAP_ROOM:
            return w[:i] + "\\N" + w[i:]
    return "{\\fs%d}%s{\\fs%d}" % (int(CAP_SIZE * CAP_ROOM / cap_width(w)), w, CAP_SIZE)


def chunks(aligned, most=3, chars=18):
    group, cur = [], []
    for w in aligned:
        if cap_width(w[0].upper()) > CAP_ROOM:
            if len(cur) == 1 and len(cur[0][0]) <= 3:
                group.append(cur + [w])
                cur = []
                continue
            if cur:
                group.append(cur)
                cur = []
            group.append([w])
            continue
        cur.append(w)
        if len(cur) >= most or sum(len(x[0]) + 1 for x in cur) >= chars or re.search(r"[.,!?;:]$", w[0]):
            group.append(cur)
            cur = []
    if cur:
        group.append(cur)
    return group


def stamp(t):
    t = max(0.0, t)
    return "%d:%02d:%02d.%02d" % (t // 3600, t % 3600 // 60, t % 60, round((t % 1) * 100) % 100)


def write_ass(aligned, offset, end_at, path, active):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Black,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,7,3,2,96,150,590,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, groups = [], chunks(aligned)
    for g_i, g in enumerate(groups):
        g_end = groups[g_i + 1][0][1] if g_i + 1 < len(groups) else min(g[-1][2] + 0.4, end_at - offset)
        for k, (word, s, e) in enumerate(g):
            a = s if k else g[0][1]
            b = g[k + 1][1] if k + 1 < len(g) else g_end
            if b - a < 0.02:
                continue
            txt = " ".join(("{\\c%s}%s{\\c&H00FFFFFF&}" % (active, fit_word(w.upper()))) if j == k else fit_word(w.upper())
                           for j, (w, _, _) in enumerate(g))
            pop = "{\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
            lines.append("Dialogue: 0,%s,%s,Cap,,0,0,0,,%s%s" % (stamp(a + offset), stamp(b + offset), pop, txt))
    Path(path).write_text(head + "\n".join(lines) + "\n")


def vplate(src, out, k, from_center=False):
    """the picture at 1.5x the frame's height, and the pan across it"""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    cw, ch = round(W * SS), round(H * SS)
    if im.width / im.height >= W / H:
        s = ch / im.height
        im = im.resize((max(cw, round(im.width * s)), ch), Image.LANCZOS)
        r = im.width - cw
        a, b = (0.2 * r, 0.8 * r) if k % 2 else (0.8 * r, 0.2 * r)
        if from_center:
            a = 0.5 * r
        pan = ("x", a, b)
    else:
        s = cw / im.width
        im = im.resize((cw, max(ch, round(im.height * s))), Image.LANCZOS)
        r = im.height - ch
        pan = ("y", 0.5 * r if from_center else 0.25 * r, 0.75 * r)
    im.save(out, quality=92)
    return pan


def kicker(video, man, seg):
    fmt = video.format
    secs = {s["index"]: s for s in man["meta"]["sections"]}
    sec = secs.get(seg["section"], {"label": "", "name": ""})
    numbered = [s for s in man["segments"] if s["kind"] == "segment"]
    if fmt == "iceberg":
        n = re.sub(r"\D", "", sec["label"])
        return ("LEVEL %s OF %d · %s" % (n, len(secs), sec["name"])).strip(" ·")
    if fmt == "answers":
        return "QUESTION %d OF %d" % ([s["id"] for s in numbered].index(seg["id"]) + 1, len(numbered))
    return ("%s · %s" % (sec["label"], sec["name"])).strip(" ·")


def jobs_for(video, man, rep, only):
    fmt = video.format
    out = []
    numbered = [s for s in man["segments"] if s["kind"] == "segment"]
    for s in man["segments"]:
        if s["kind"] != "segment":
            continue
        r = rep["segments"].get(s["id"])
        if not r:
            continue
        marks = []
        if fmt == "argument":
            ws = script_words(s["narration"], r["words"])
            for k, (a, b) in enumerate(s["shorts"], 1):
                t0 = find_phrase(ws, a)
                t1 = find_phrase(ws, b, after=t0 or 0, last=True)
                if t0 is None or t1 is None:
                    print("  note: short mark %d of %s: words not found in the take; skipped" % (k, s["id"]))
                    continue
                marks.append(("short-%s-%d" % (s["id"], k), t0, t1))
        else:
            marks.append(("short-%s" % s["id"], 0.0, float(r["seconds"])))
        for sid, t0, t1 in marks:
            if only and s["id"] not in only and sid not in only:
                continue
            out.append({"id": sid, "seg": s, "rep": r, "t0": max(0.0, t0 - 0.05), "t1": min(float(r["seconds"]), t1 + 0.15),
                        "index": numbered.index(s) + 1, "of": len(numbered)})
    return out


def picture_for(video, job):
    """the look on screen at the short's midpoint, in the long video's own split of the segment"""
    s, r = job["seg"], job["rep"]
    looks = s["looks"]
    if not looks:
        return None, None
    pre = PAD["segment"][0]
    L = pre + float(r["seconds"]) + PAD["segment"][1]
    shares = split_windows(L, pre, s["narration"], r.get("words", []), len(looks))
    mid, t = pre + (job["t0"] + job["t1"]) / 2, 0.0
    pick = looks[-1]
    for lk, share in zip(looks, shares):
        if t <= mid < t + share:
            pick = lk
            break
        t += share
    for lk in [pick] + [x for x in looks if x is not pick]:
        if lk.get("stat"):
            continue
        img, clip = find_image(video, lk["id"]), find_clip(video, lk["id"])
        if img or clip:
            return img, clip
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    video = Video(a.video)
    man, rep = video.manifest(), video.report()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    jobs = jobs_for(video, man, rep, only)
    odir = video.out / "shorts"
    work = video.work / "shorts"
    for d in (odir, work / "png", work / "plates"):
        d.mkdir(parents=True, exist_ok=True)
    look = video.brand.get("look", {})
    active = ass_color(look.get("caption_active", "#7CB6F2"))
    title = video.cfg["title"]
    spec = []
    for j in jobs:
        s = j["seg"]
        src = " · ".join(t for t, _ in s["sources"])[:90]
        j["img"], j["clip"] = picture_for(video, j)
        num = s["number"] if video.format == "iceberg" else None
        base = {"kicker": kicker(video, man, s), "n": num, "title": s["title"], "source": src}
        spec.append({"file": "head_%s.png" % j["id"], "page": "shorts.html", "kind": "head", "extra": dict(base, badge="AI IMAGE")})
        if j["clip"]:
            spec.append({"file": "headv_%s.png" % j["id"], "page": "shorts.html", "kind": "head", "extra": dict(base, badge="AI VIDEO")})
        eyebrow = ("This was #%d of %d" % (s["number"], j["of"])) if video.format == "iceberg" else \
                  ("Question %d of %d" % (j["index"], j["of"])) if video.format == "answers" else kicker(video, man, s).title()
        spec.append({"file": "end_%s.png" % j["id"], "page": "shorts.html", "kind": "end", "transparent": False,
                     "extra": {"eyebrow": eyebrow, "video_title": title}})
        j["say"], j["window"] = None, None
        if s.get("card"):
            ws = script_words(s["narration"], j["rep"]["words"])
            p0 = find_phrase(ws, s["card"][0])
            p1 = find_phrase(ws, s["card"][1], after=p0 or 0, last=True)
            if p0 is not None and p1 is not None and j["t0"] <= p0 and p1 <= j["t1"] + 0.2:
                from assemble import pitch_sentence
                j["say"] = pitch_sentence(video, {"seg": s})
                if j["say"]:
                    j["window"] = (PRE + p0 - j["t0"] - 0.2, PRE + p1 - j["t0"] + 1.2)
                    spec.append({"file": "pitch_%s.png" % j["id"], "page": "shorts.html", "kind": "pitch", "extra": {"say": j["say"]}})
    path = work / "cards.json"
    path.write_text(json.dumps({"brand": dict(video.brand, dir=str(video.brand_dir)), "out": str(work / "png"), "items": spec},
                               indent=1, ensure_ascii=False))
    r = subprocess.run(["node", str(ENGINE / "render.mjs"), str(path), "--force"],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("overlay render failed:\n" + r.stderr[-2500:])
    print(r.stdout.strip(), flush=True)
    png = work / "png"
    track = video.music()
    index = []
    for k, j in enumerate(jobs):
        out = odir / ("%s.mp4" % j["id"])
        s, rp = j["seg"], j["rep"]
        words = [w for w in rp["words"] if j["t0"] - 0.05 <= w["s"] <= j["t1"]]
        rel = [{"w": w["w"], "s": w["s"] - j["t0"], "e": w["e"] - j["t0"]} for w in words]
        text = s["narration"]
        if video.format == "argument":
            text = " ".join(x for x, st, en in align(s["narration"], rp["words"]) if j["t0"] - 0.05 <= st <= j["t1"])
        aligned = align(text, rel)
        narr = j["t1"] - j["t0"]
        tend = PRE + narr + TAIL
        T = tend + ENDLEN
        index.append({"id": j["id"], "segment": s["id"], "title": s["title"], "kicker": kicker(video, man, s),
                      "seconds": round(T, 1), "file": out.name, "hook": text[:240],
                      "picture": "AI clip + still" if j["clip"] else "AI still" if j["img"] else "none",
                      "brand_card": bool(j["window"])})
        if out.exists() and not a.force:
            continue
        if not (j["img"] or j["clip"]):
            print("  skip %s: no picture for its look yet" % j["id"])
            index[-1]["skipped"] = True
            continue
        cap = work / ("captions_%s.ass" % j["id"])
        write_ass(aligned, PRE, tend, cap, active)
        mix = work / ("mix_%s.wav" % j["id"])
        ms = int(PRE * 1000)
        voice = video.dir / "voice" / rp["file"]
        if track:
            off = (k * 23) % max(1, int(dur(track) - T - 1))
            ff("-ss", "%.3f" % j["t0"], "-t", "%.3f" % narr, "-i", voice, "-ss", off, "-i", track, "-filter_complex",
               "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=%d|%d,apad=whole_dur=%.3f,atrim=0:%.3f,asplit=2[vo][sc];"
               "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=0:%.3f,volume=0.30,"
               "afade=t=in:st=0:d=0.6,afade=t=out:st=%.3f:d=1.4[b];"
               "[b][sc]sidechaincompress=threshold=0.012:ratio=10:attack=15:release=500[duck];"
               "[vo][duck]amix=inputs=2:normalize=0[a]" % (ms, ms, T, T, T, T - 1.4),
               "-map", "[a]", "-ar", 48000, "-ac", 2, mix)
        else:
            ff("-ss", "%.3f" % j["t0"], "-t", "%.3f" % narr, "-i", voice, "-af",
               "aformat=sample_rates=48000:channel_layouts=stereo,adelay=%d|%d,apad=whole_dur=%.3f,atrim=0:%.3f" % (ms, ms, T, T),
               "-ar", 48000, "-ac", 2, mix)
        m = run_json(["ffmpeg", "-hide_banner", "-i", str(mix), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
        ln = ("loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true,"
              "aresample=48000" % (m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"]))
        hold = lambda i, d: "[%d:v]loop=loop=-1:size=1:start=0,setpts=N/(%d*TB),trim=duration=%.3f" % (i, FPS, d)
        ins, g = [], []
        clip_s = 0.0
        if j["clip"]:
            clip_s = min(dur(j["clip"]), tend - 1.0)
            ins += ["-i", j["clip"]]
            g.append("[0:v]setpts=PTS-STARTPTS,fps=%d,scale=-2:%d,crop=%d:%d,setsar=1,trim=duration=%.3f,format=yuv420p[c]"
                     % (FPS, H, W, H, clip_s))
            from assemble import last_frame
            src = last_frame(Path(j["clip"]), work / "plates" / ("last_%s.png" % j["id"]))
        else:
            src = j["img"]
        pl = work / "plates" / ("p_%s.jpg" % j["id"])
        axis, p0, p1 = vplate(src, pl, k, from_center=bool(j["clip"]))
        rest = T - clip_s
        span = max(0.5, rest - ENDLEN - 0.2)
        move = "%.1f+(%.1f)*min(t/%.2f,1)" % (p0, p1 - p0, span)
        crop = ("crop=%d:%d:x='%s':y=0" if axis == "x" else "crop=%d:%d:x=0:y='%s'") % (round(W * SS), round(H * SS), move)
        pi = len(ins) // 2
        ins += ["-i", pl]
        g.append("%s,%s,scale=%d:%d:flags=bicubic,setsar=1,format=yuv420p[p]" % (hold(pi, rest), crop, W, H))
        if j["clip"]:
            g.append("[c][p]concat=n=2:v=1:a=0[bg]")
        else:
            g.append("[p]null[bg]")
        hi = len(ins) // 2
        ins += ["-i", png / ("head_%s.png" % j["id"])]
        g.append("%s,format=rgba,fade=t=in:st=0:d=0.25:alpha=1[h]" % hold(hi, T))
        g.append("[bg][h]overlay=0:0:enable='between(t,%.3f,%.3f)'[v1]" % (clip_s if j["clip"] else 0.0, tend + 0.4))
        last = "v1"
        if j["clip"]:
            vi = len(ins) // 2
            ins += ["-i", png / ("headv_%s.png" % j["id"])]
            g.append("%s,format=rgba[hv]" % hold(vi, T))
            g.append("[v1][hv]overlay=0:0:enable='lt(t,%.3f)'[v1b]" % clip_s)
            last = "v1b"
        if j["window"]:
            a0, a1 = j["window"]
            pi2 = len(ins) // 2
            ins += ["-i", png / ("pitch_%s.png" % j["id"])]
            g.append("%s,format=rgba,fade=t=in:st=%.3f:d=0.3:alpha=1,fade=t=out:st=%.3f:d=0.3:alpha=1[pc]" % (hold(pi2, T), a0, a1 - 0.3))
            g.append("[%s][pc]overlay=0:0:enable='between(t,%.3f,%.3f)'[v2]" % (last, a0, a1))
            last = "v2"
        g.append("[%s]ass=%s[v3]" % (last, cap))
        ei = len(ins) // 2
        ins += ["-i", png / ("end_%s.png" % j["id"])]
        g.append("%s,format=rgba,fade=t=in:st=%.3f:d=0.35:alpha=1[e]" % (hold(ei, T), tend))
        g.append("[v3][e]overlay=0:0:enable='gte(t,%.3f)',format=yuv420p[v]" % tend)
        ai = len(ins) // 2
        ff(*ins, "-i", mix, "-filter_complex", ";".join(g), "-map", "[v]", "-map", "%d:a" % ai, "-af", ln,
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", 21, "-pix_fmt", "yuv420p", "-r", FPS,
           "-c:a", "aac", "-b:a", "192k", "-ar", 48000, "-movflags", "+faststart", "-t", "%.3f" % T, out)
        print("  %-22s %-40s %5.1fs%s%s" % (j["id"], (s["title"] or "")[:40], T, "  + clip" if j["clip"] else "",
                                             "  + brand card" if j["window"] else ""), flush=True)
    old = odir / "shorts.json"
    if old.exists() and only:
        keep = {r["id"]: r for r in json.loads(old.read_text())}
        keep.update({r["id"]: r for r in index})
        index = list(keep.values())
    old.write_text(json.dumps(index, indent=1, ensure_ascii=False))
    print("shorts.json lists %d shorts in %s" % (len(index), odir))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""mix.py: put each narration clip under its caption in an exported Claude Motion film.

  python3 mix.py cues --scenes scenes.json --modules DIR [--lines lines.json] [--out cues.json]
      Each caption's start and end in the film: the scene's start (the sum of the earlier scenes' dur)
      plus the caption's in and out times from its scene module (scene-<id>.js). Store documents saved
      from the film (scenes.json.json, scene-<id>.js.json) work too.
  python3 mix.py mix --film FILM.mp4 --voice voice --cues cues.json --out FINISHED.mp4 [--score 0.25] [--web]
      Starts each clip at its caption's start, keeps the film's own sound (the score) under the voice at
      25% when the export has sound, mixes with amix normalize=0, brings the voice to -16 LUFS (two-pass
      loudnorm, linear) and copies the picture. A clip longer than its caption is sped up to 1.15x at
      most; past that the line needs to be shorter. --web adds FINISHED-web.mp4 (1280x720, H.264, CRF 28).
  python3 mix.py frames --film FINISHED.mp4 --cues cues.json --out frames
      One JPEG at each caption's midpoint, to check the caption, the screen and that nothing private shows.
Needs ffmpeg and ffprobe.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_TEMPO = 1.15
LUFS = -16.0


def stop(msg):
    sys.exit("STOP: " + msg)


def load_text(path):
    """a plain file, or a Motion store document ({"kind": ..., "text": ...}) saved from the film"""
    t = Path(path).read_text()
    if str(path).endswith(".json"):
        try:
            d = json.loads(t)
            if isinstance(d, dict) and set(d) >= {"kind", "text"}:
                return d["text"]
        except ValueError:
            pass
    return t


def find(folder, name):
    for cand in (folder / name, folder / (name + ".json")):
        if cand.exists():
            return cand
    return None


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, text=True)
    if out.returncode != 0:
        stop("ffprobe couldn't read %s: %s" % (path, out.stderr.strip()[:200]))
    js = json.loads(out.stdout)
    kinds = [s.get("codec_type") for s in js.get("streams", [])]
    return float(js["format"]["duration"]), "audio" in kinds, "video" in kinds


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        stop("ffmpeg failed: %s" % p.stderr.strip()[-800:])
    return p


# ---------------- cues ----------------
CAP = re.compile(r"""['"](?P<id>[A-Za-z0-9_.-]+)['"]\s*,\s*(?P<a>-?\d+(?:\.\d+)?)\s*,\s*(?P<b>-?\d+(?:\.\d+)?)\s*\]""")


def cmd_cues(a):
    scenes = json.loads(load_text(a.scenes))
    lst = scenes.get("scenes", scenes) if isinstance(scenes, dict) else scenes
    lines = json.loads(load_text(a.lines)) if a.lines else None
    mods = Path(a.modules)
    cues, t0 = {}, 0.0
    for sc in lst:
        sid, dur = sc["id"], float(sc["dur"])
        f = find(mods, "scene-%s.js" % sid)
        if f is None:
            stop("no scene-%s.js in %s" % (sid, mods))
        for m in CAP.finditer(load_text(f)):
            lid = m.group("id")
            if lines is not None and lid not in lines:
                continue
            tin, tout = float(m.group("a")), float(m.group("b"))
            if not (0 <= tin < tout <= dur + 0.01):
                continue
            if lid in cues:
                stop("caption %s appears twice" % lid)
            cues[lid] = [round(t0 + tin, 3), round(t0 + tout, 3)]
        t0 += dur
    if lines is not None:
        missing = [k for k in lines if k not in cues]
        if missing:
            print("note: no caption timing found for %s (lines without a caption get no voice)" % ", ".join(missing))
    cues = dict(sorted(cues.items(), key=lambda kv: kv[1][0]))
    Path(a.out).write_text(json.dumps(cues, indent=2) + "\n")
    print("%d captions, film %.2fs -> %s" % (len(cues), t0, a.out))
    for k, (s, e) in cues.items():
        print("  %-12s %7.2f %7.2f" % (k, s, e))


# ---------------- mix ----------------
def clip_for(folder, lid):
    for ext in (".mp3", ".wav", ".m4a", ".aac", ".flac"):
        p = folder / (lid + ext)
        if p.exists():
            return p
    return None


def voice_graph(entries, first_input):
    parts, labels = [], []
    for n, (lid, start, tempo) in enumerate(entries):
        i = first_input + n
        f = "[%d:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo" % i
        if tempo > 1.001:
            f += ",atempo=%.4f" % tempo
        ms = int(round(start * 1000))
        f += ",adelay=%d|%d[c%d]" % (ms, ms, n)
        parts.append(f)
        labels.append("[c%d]" % n)
    parts.append("".join(labels) + "amix=inputs=%d:normalize=0:dropout_transition=0" % len(entries))
    return ";".join(parts)


def cmd_mix(a):
    film, voice, out = Path(a.film), Path(a.voice), Path(a.out)
    cues = json.loads(Path(a.cues).read_text())
    vdur, has_audio, has_video = probe(film)
    if not has_video:
        stop("%s has no picture" % film)
    entries, rows, problems = [], [], []
    for lid, (start, end) in sorted(cues.items(), key=lambda kv: kv[1][0]):
        clip = clip_for(voice, lid)
        if clip is None:
            problems.append("%s: no clip in %s" % (lid, voice))
            continue
        cdur = probe(clip)[0]
        window = end - start
        tempo = 1.0
        if cdur > window + 0.15:
            tempo = cdur / window
            if tempo > MAX_TEMPO:
                problems.append("%s: %.2fs of voice for a %.2fs caption; shorten the line or the caption's time"
                                % (lid, cdur, window))
                tempo = MAX_TEMPO
        entries.append((lid, start, tempo))
        rows.append((lid, start, window, cdur, tempo))
    print("%-12s %7s %7s %7s %6s" % ("line", "start", "window", "voice", "speed"))
    for lid, s, w, c, t in rows:
        print("%-12s %7.2f %7.2f %7.2f %6.3f" % (lid, s, w, c, t))
    if problems:
        print("\n".join(["", "Problems:"] + ["  " + p for p in problems]))
        if not a.force:
            stop("fix the problems above (or pass --force to mix anyway)")
    if a.dry_run or not entries:
        return
    inputs = ["-i", str(film)]
    for lid, _, _ in entries:
        inputs += ["-i", str(clip_for(voice, lid))]
    graph = voice_graph(entries, 1)
    # pass 1: measure the voice
    p = run(["ffmpeg", "-hide_banner", "-nostats"] + inputs + ["-filter_complex",
             graph + ",loudnorm=I=%g:TP=-1.5:LRA=11:print_format=json[m]" % LUFS, "-map", "[m]", "-f", "null", "-"])
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr)
    if not m:
        stop("couldn't measure the voice loudness")
    ms = json.loads(m[-1])
    norm = ("loudnorm=I=%g:TP=-1.5:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:"
            "offset=%s:linear=true" % (LUFS, ms["input_i"], ms["input_tp"], ms["input_lra"], ms["input_thresh"],
                                       ms["target_offset"]))
    graph += "," + norm + ",aresample=48000[vox]"
    if has_audio and a.score > 0:
        graph += (";[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=%g[bed]"
                  ";[vox][bed]amix=inputs=2:normalize=0:dropout_transition=0:duration=longest,apad[aout]" % a.score)
    else:
        graph += ";[vox]apad[aout]"
    tmp = out.with_name(out.stem + ".part.mp4")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inputs + [
        "-filter_complex", graph, "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-t", "%.3f" % vdur, "-movflags", "+faststart", str(tmp)])
    tmp.replace(out)
    print("\nwrote %s (%.2fs, voice measured %s LUFS before leveling to %g)" % (out, vdur, ms["input_i"], LUFS))
    if a.web:
        web = out.with_name(out.stem + "-web.mp4")
        tmpw = web.with_name(web.stem + ".part.mp4")
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(out), "-vf",
             "scale=1280:720:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "28",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmpw)])
        tmpw.replace(web)
        print("wrote %s" % web)


# ---------------- frames ----------------
def cmd_frames(a):
    cues = json.loads(Path(a.cues).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for lid, (s, e) in cues.items():
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", "%.3f" % ((s + e) / 2), "-i", a.film,
             "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "3", str(out / ("%s.jpg" % lid))])
    print("%d frames in %s" % (len(cues), out))


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        stop("ffmpeg and ffprobe are needed")
    ap = argparse.ArgumentParser(description="Mix narration clips under a Claude Motion film's captions.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cues")
    c.add_argument("--scenes", required=True)
    c.add_argument("--modules", required=True)
    c.add_argument("--lines")
    c.add_argument("--out", default="cues.json")
    m = sub.add_parser("mix")
    m.add_argument("--film", required=True)
    m.add_argument("--voice", default="voice")
    m.add_argument("--cues", default="cues.json")
    m.add_argument("--out", required=True)
    m.add_argument("--score", type=float, default=0.25, help="the film's own sound under the voice (0 drops it)")
    m.add_argument("--web", action="store_true")
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--force", action="store_true")
    f = sub.add_parser("frames")
    f.add_argument("--film", required=True)
    f.add_argument("--cues", default="cues.json")
    f.add_argument("--out", default="frames")
    a = ap.parse_args()
    {"cues": cmd_cues, "mix": cmd_mix, "frames": cmd_frames}[a.cmd](a)


if __name__ == "__main__":
    main()

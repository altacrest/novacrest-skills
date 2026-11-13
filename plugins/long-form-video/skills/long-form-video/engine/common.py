"""common.py: what every stage of the long-form video engine shares.

A video lives in its own folder (the "video folder"):

  video.json            title, slug, brand, format and a few settings (see SKILL.md, Step 1)
  script.md             the script, in the grammar compile.py reads
  manifest.json         compile.py's output: every spoken segment, in order
  say.json              optional spoken respellings, {"segment id": "text as the voice should say it"}
  voice/                voice.py's takes (<id>.mp3) and voice/report.json (seconds and word times per segment)
  images/               one still per look: <look id>.jpg (look ids are <segment id>-<k>, k from 1)
  clips/                optional Higgsfield clips: <look id>.mp4
  music/                the brand's music bed (not in the repo; see the brand's brand.json)
  out/                  everything the engine writes

The engine's own files (brands/, formats/, engine/) sit next to SKILL.md. Nothing here calls a model.
"""
import difflib
import json
import re
import subprocess
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
SKILL = ENGINE.parent
FPS = 30


def ff(*args, quiet=True):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed:\n" + " ".join(cmd)[:1500] + "\n" + r.stderr[-2500:])
    return r


def run_json(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    m = re.findall(r"\{[^{}]*\}", r.stderr, re.S)
    return json.loads(m[-1]) if m else {}


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise SystemExit("can't read the length of %s" % p)


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        if default is not None:
            return default
        raise SystemExit("missing %s" % p)
    d = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(d, dict) and set(d) >= {"kind", "text"} and isinstance(d.get("text"), str):   # a store document
        d = json.loads(d["text"])
    return d


class Video:
    """the video folder, its settings and the brand pack it names"""

    def __init__(self, folder):
        self.dir = Path(folder).expanduser().resolve()
        if not (self.dir / "video.json").exists():
            raise SystemExit("no video.json in %s (Step 1 of SKILL.md makes it)" % self.dir)
        self.cfg = load_json(self.dir / "video.json")
        for k in ("title", "slug", "brand", "format"):
            if not self.cfg.get(k):
                raise SystemExit("video.json needs %r" % k)
        if self.cfg["format"] not in FORMATS:
            raise SystemExit("format must be one of %s" % ", ".join(FORMATS))
        self.brand_dir = SKILL / "brands" / self.cfg["brand"]
        if not (self.brand_dir / "brand.json").exists():
            raise SystemExit("no brand pack brands/%s/brand.json" % self.cfg["brand"])
        self.brand = load_json(self.brand_dir / "brand.json")
        self.out = self.dir / "out"
        self.work = self.dir / "build"

    @property
    def format(self):
        return self.cfg["format"]

    def manifest(self):
        return load_json(self.dir / "manifest.json")

    def report(self):
        p = self.dir / "voice" / "report.json"
        if not p.exists():
            raise SystemExit("no voice/report.json yet: the narration comes first (voice.py, in the Terminal)")
        return load_json(p)

    def music(self):
        """the music bed: video.json's music, else the brand's, if the file is in the video folder"""
        name = self.cfg.get("music") or (self.brand.get("music") or {}).get("file")
        if not name:
            return None
        for cand in (self.dir / name, self.dir / "music" / Path(name).name):
            if cand.exists():
                return cand
        return None


# ---------------- formats ----------------
FORMATS = {
    # kicker: the small line on the title card; chapter: how chapters are named; shorts: what becomes a short
    "iceberg": {"kicker": "{n} STORIES · {levels} LEVELS", "chapters": "sections", "shorts": "segments"},
    "answers": {"kicker": "{n} QUESTIONS ANSWERED", "chapters": "segments", "shorts": "segments"},
    "argument": {"kicker": "THE PROBLEM · THE FUTURES · THE FIX", "chapters": "sections", "shorts": "marked"},
}


# ---------------- words and times ----------------
def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def find_phrase(words, phrase, after=0.0, last=False):
    """time of the first (or last) word of a phrase in a take's word list [{"w", "s", "e"}]"""
    want = [norm(x) for x in phrase.split() if norm(x)]
    ws = [norm(w["w"]) for w in words]
    if not want:
        return None
    hits = [i for i in range(len(ws) - len(want) + 1) if ws[i:i + len(want)] == want and words[i]["s"] >= after]
    if not hits:
        return None
    i = hits[0]
    return words[i + len(want) - 1]["e"] if last else words[i]["s"]


def align(text, words):
    """the script's words with the take's times: matched words keep their times, the rest share the span around
    them (the voice may have been sent a respelling, so the words differ here and there)"""
    toks = text.split()
    a, b = [norm(t) for t in toks], [norm(w["w"]) for w in words]
    times = [None] * len(toks)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (words[j1 + k]["s"], words[j1 + k]["e"])
        elif tag == "replace":
            s, e = words[j1]["s"], words[j2 - 1]["e"]
            lens = [max(1, len(a[i])) for i in range(i1, i2)]
            t = s
            for k, i in enumerate(range(i1, i2)):
                d = (e - s) * lens[k] / sum(lens)
                times[i] = (t, t + d)
                t += d
    for i in range(len(toks)):
        if times[i] is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            j = next((j for j in range(i + 1, len(toks)) if times[j]), None)
            nxt = times[j][0] if j is not None else prev + 0.35 * (len(toks) - i)
            gap = max(0.05, (nxt - prev) / ((j if j is not None else len(toks)) - i + 1))
            times[i] = (prev, prev + gap)
    out, last = [], 0.0
    for t, (s, e) in zip(toks, times):
        s = max(s, last)
        e = max(e, s + 0.05)
        out.append((t, s, e))
        last = s
    return out


def script_words(text, words):
    """the script's own words with the take's times, as [{"w", "s", "e"}]: card and short words are found in the
    script's spelling ("two thousand"), whatever the take's words say ("2,000", a respelling)"""
    return [{"w": t, "s": s, "e": e} for t, s, e in align(text, words)]


def sentence_ends(text, words):
    """the time each sentence of the narration ends, from the aligned words"""
    al = align(text, words)
    return [e for (t, s, e) in al if re.search(r"[.!?…][\"”')]*$", t)]


def ts(t):
    t = int(round(t))
    return "%d:%02d:%02d" % (t // 3600, t % 3600 // 60, t % 60) if t >= 3600 else "%d:%02d" % (t // 60, t % 60)

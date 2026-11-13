#!/usr/bin/env python3
"""lint.py: the mechanical half of the humanizer, for scripts that will be spoken.

  python3 engine/lint.py <video folder>            reads script.md, the brand's claims and competitors, and video.json

Checks a script the way the blog pipeline checks a post, plus what matters to the ear: no dashes, brackets, semicolons
or slashes (they can't be spoken), no sentence over 32 words, no AI tells or filler, no competitor named, and every
sentence that names the product close to a line in the brand's claims files (similarity 0.60 or more; needs
scikit-learn). Warnings for "not X, but Y", lists of three, rhetorical questions, repeated openers and overused words.

Exit 0 = no FAIL. The loop: lint, rewrite only the flagged sentences, red-team, lint again. Nothing here asks a model
for an opinion.
"""
import argparse, json, re, sys
from collections import Counter
from pathlib import Path

BANNED = [  # AI tells and vendor filler; extend in style/banned.txt (one phrase per line)
    "in today's fast-paced world", "fast-paced world", "unlock", "game-changer", "game changer", "delve", "tapestry",
    "testament to", "it's worth noting", "it is worth noting", "in conclusion", "navigate the complexities",
    "ever-evolving", "ever evolving", "the landscape of", "leverage", "seamless", "seamlessly", "robust",
    "cutting-edge", "revolutionize", "elevate", "harness the power", "at the end of the day", "buckle up",
    "let's dive in", "let's dive into", "dive deep", "without further ado", "a rich history", "plays a crucial role",
    "crucial role", "pivotal", "in the realm of", "nestled", "bustling", "vibrant", "embark", "journey into",
    "stands as", "serves as a reminder", "a reminder that", "the world of", "when it comes to", "a myriad of",
    "moreover", "furthermore", "additionally", "notably", "importantly", "ultimately,", "interestingly,",
    "fun fact", "spoiler alert", "smash that like button", "let that sink in", "here's the kicker", "here's the thing",
]
COMPETITORS = ["ShipStation", "Cin7", "Fishbowl", "Manhattan Associates", "Fluent Commerce", "Kibo", "Zoho Inventory",
               "Linnworks", "ShipHero", "Extensiv", "Logiwa", "Deposco", "NetSuite WMS", "Infoplus"]
OURS = re.compile(r"\b(bin ?logic)\b", re.I)   # replaced from brand.json in main()


def sentences(text):
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])", text) if s.strip()]


def spoken(md):
    """the words the narrator will say: drop headings, stage directions, links, comments and front matter"""
    md = re.sub(r"^---.*?---", "", md, flags=re.S)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"^\s*#.*$", "", md, flags=re.M)
    md = re.sub(r"^\s*\*\(.*?\)\*\s*$", "", md, flags=re.M)              # *(stage directions)*
    md = re.sub(r"^\*\*\d+\..*\*\*\s*$", "", md, flags=re.M)             # **N. Title.** is the on-screen label (compile.py)
    md = re.sub(r"^\s*-{3,}\s*$", "", md, flags=re.M)                     # --- section rules
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    md = re.sub(r"[*_`>]", "", md)
    return md


def similar(a, lines):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    v = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit(lines + [a])
    return float(cosine_similarity(v.transform([a]), v.transform(lines)).max())


def lint(md, claims=None, wpm=150, target=None, extra=()):
    say = spoken(md)
    ss = sentences(say)
    words = len(re.findall(r"[A-Za-z0-9']+", say))
    per_k = lambda n: n * 1000 / max(words, 1)
    out = []   # (level, check, detail)
    low = say.lower()
    for ch, name in (("—", "em dash"), ("–", "en dash")):
        for s in ss:
            if ch in s:
                out.append(("FAIL", name, s))
    for s in ss:
        if re.search(r"[()\[\];/]", s):
            out.append(("FAIL", "can't be spoken (bracket, semicolon or slash)", s))
        n = len(s.split())
        if n > 32:
            out.append(("FAIL", f"sentence of {n} words (max 32 for the ear)", s))
    for p in list(BANNED) + list(extra):
        for m in re.finditer(r"\b" + re.escape(p.lower()) + r"\b", low):
            ctx = say[max(0, m.start() - 50): m.end() + 50].replace("\n", " ")
            out.append(("FAIL", f'AI tell or filler: "{p}"', "..." + ctx + "..."))
    for c in COMPETITORS:
        if re.search(r"\b" + re.escape(c) + r"\b", say):
            out.append(("FAIL", f"competitor named: {c}", ""))
    notx = [s for s in ss if re.search(r"\b(it's|it is|this is|that's) not (just|only|about)\b|\bnot \w+(,| but)\b.*\bbut\b", s, re.I)]
    if per_k(len(notx)) > 1:
        out += [("WARN", "'not X, but Y' pattern (over 1 per 1,000 words)", s) for s in notx]
    triads = [s for s in ss if re.search(r"\b\w+(?: \w+)?, \w+(?: \w+)?,? and \w+", s)]
    if per_k(len(triads)) > 6:
        out.append(("WARN", f"lists of three: {len(triads)} ({per_k(len(triads)):.1f} per 1,000 words; keep under 6)", ""))
    qs = [s for s in ss if s.endswith("?")]
    if per_k(len(qs)) > 4:
        out.append(("WARN", f"rhetorical questions: {len(qs)} ({per_k(len(qs)):.1f} per 1,000 words; keep under 4)", ""))
    for a, b in zip(ss, ss[1:]):
        fa, fb = a.split()[0].lower(), b.split()[0].lower()
        if fa == fb and fa not in ("and", "but"):
            out.append(("WARN", f'two sentences in a row start with "{fa}"', a + " / " + b))
    for w, n in Counter(re.findall(r"\b[a-z]{6,}\b", low)).most_common(8):
        if n >= 5 and per_k(n) > 4:
            out.append(("WARN", f'"{w}" appears {n} times ({per_k(n):.1f} per 1,000 words)', ""))
    if claims:
        ok = [l["text"] for c in claims for l in json.loads(Path(c).expanduser().read_text())["lines"]
              if l.get("source") in ("public_site", "video_pitch")]
        try:
            import sklearn  # noqa: F401  (the similarity check needs it; without it, fail loudly rather than pass)
        except ImportError:
            out.append(("FAIL", "claims check didn't run: scikit-learn isn't installed (pip install scikit-learn)", ""))
            ok = []
        for s in (ss if ok else []):
            if OURS.search(s):
                score = similar(s, ok)
                if score < .60:
                    out.append(("FAIL", f"product sentence not in the claims library (similarity {score:.2f} < 0.60)", s))
    mean = sum(len(s.split()) for s in ss) / max(len(ss), 1)
    if mean > 18:
        out.append(("WARN", f"average sentence is {mean:.1f} words (aim for 18 or fewer)", ""))
    mins = words / wpm
    info = f"{words} spoken words, {len(ss)} sentences, about {mins:.1f} minutes at {wpm} words a minute"
    if target:
        info += f" (target {target:g} minutes = {int(target * wpm):,} words)"
    return out, info


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import Video
    global COMPETITORS, OURS
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--banned", default=None, help="a file of extra banned phrases, one per line")
    a = ap.parse_args()
    video = Video(a.video)
    COMPETITORS = video.brand.get("competitors", COMPETITORS)
    if video.brand.get("pitch_name"):
        OURS = re.compile(r"\b(%s)\b" % video.brand["pitch_name"], re.I)
    claims = [str(video.brand_dir / c) for c in video.brand.get("claims", [])]
    narr = dict(video.brand.get("narrator", {}), **video.cfg.get("narrator", {}))
    extra = Path(a.banned).read_text().split("\n") if a.banned else []
    res, info = lint((video.dir / "script.md").read_text(encoding="utf-8"), claims, int(narr.get("wpm", 150)),
                     video.cfg.get("target_minutes"), [x for x in extra if x.strip()])
    for lvl, check, detail in res:
        print(f"{lvl}  {check}" + (f"\n      {detail}" if detail else ""))
    fails = sum(1 for r in res if r[0] == "FAIL")
    print(f"\n{info}\n{fails} FAIL, {len(res) - fails} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

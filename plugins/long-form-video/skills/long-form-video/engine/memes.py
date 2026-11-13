#!/usr/bin/env python3
"""memes.py: the meme pass for spoken scripts.

Memes come only from Know Your Meme sitemaps a person saves by hand into a folder (default ~/Downloads/memes; no tool
here may fetch knowyourmeme.com or 9gag.com). This script never fetches anything. It lists candidates, the writer picks at
most one per entry and writes the spoken line, and `check` verifies the picks. Nothing here decides what's funny.

  python3 engine/memes.py scan                              # what's in the saved sitemaps, and how fresh
  python3 engine/memes.py suggest script/level1.md          # candidates per entry, as markdown
  python3 engine/memes.py suggest script/level1.md --want-volumes   # the search terms to look up in SE Ranking
  python3 engine/memes.py suggest script/level1.md --volumes data/meme_volumes.json
  python3 engine/memes.py check script/level1.md            # exit 1 if a pick breaks a rule

A pick is a stage direction under the entry: *(meme: elmo-rise. ...)*  (the slug from the KYM address).
Rules: spoken only, never the meme's image; at most one meme per entry; none on an entry where
people died; nothing from KYM's /sensitive/ pages, events or real people; re-save the sitemaps when the newest page
in them is 14 days old.
"""
import argparse, datetime as dt, json, math, re, sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
MEMES = Path.home() / "Downloads" / "memes"
STALE_DAYS = 14
ENTRY_RE = re.compile(r"^\*\*(\d+)\.\s*(.+?)\.?\*\*\s*$")          # the same grammar as compile.py
STAGE_RE = re.compile(r"^\*\((.*)\)\*\s*$")
DEATH = re.compile(r"\b(killed|died|dies|dead|deaths?|fatal|lives were lost)\b", re.I)
DENY = set("""death dead dies died killed kill kills murder murdered shooting shooter shot suicide nazi nazis hitler
porn porno sex sexual sexy nsfw nude nudes naked cocaine meth drug drugs rape racist racism slur fuck fucking shit
bitch ass hoe hoes cum penis dick boob boobs tits feces piss gore footjob onlyfans hentai rule34 bomb bombing
terrorist isis cartel abuse groomer pedo pedophile gun guns""".split())
STOP = set("""the a an and or of to in on at for with from by is are was were be been it its it's this that these those
you your yours we our they them their he she his her i me my not no but so if as than then there here what when
where who why how all any some one two three about into over under up down out off just only very can could would
should will shall do does did done have has had get got make made like know new old big small time day year meme
memes guy man woman people thing things way also more most much many say said says goes going went back""".split())
ALIASES = {     # the name people search for, when it isn't the KYM slug (SE Ranking, US, Nov 2026)
    "elmo-rise": "elmo fire meme",
}
EVERGREEN = {   # famous reaction memes, offered for any entry; the note says the situation each one fits
    "this-is-fine": "a disaster everyone in it keeps calling normal",
    "surprised-pikachu": "an outcome anyone could have predicted",
    "stonks": "a price or a number going somewhere absurd",
    "panik-kalm": "panic, relief, then panic again",
    "galaxy-brain": "a plan that gets cleverer and worse at each step",
    "distracted-boyfriend": "someone dropping the sure thing for the shiny thing",
    "is-this-a-pigeon": "confidently naming the wrong thing",
    "woman-yelling-at-a-cat": "an argument where one side has no idea",
    "elmo-rise": "pure chaos, cheerfully embraced",
    "always-has-been": "a twist that was true all along",
    "one-does-not-simply-walk-into-mordor": "a task harder than it sounds",
}


def toks(s):
    s = unquote(s).lower().replace("'", "")
    return [w for w in re.split(r"[^a-z0-9]+", s) if w]


def stem(w):
    return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w


def load(memes_dir):
    """every page in the saved sitemaps: kind, slug, words, lastmod; plus the newest lastmod per file"""
    pages, files = [], {}
    for f in sorted(Path(memes_dir).expanduser().glob("*.xml")):
        x = f.read_text(encoding="utf-8", errors="replace")
        rows = re.findall(r"<loc>\s*(\S+?)\s*</loc>\s*<lastmod>\s*(\S+?)\s*</lastmod>", x)
        newest = None
        for loc, mod in rows:
            path = loc.split("knowyourmeme.com/", 1)[-1].strip("/")
            parts = path.split("/")
            sensitive = parts[0] == "sensitive"
            if sensitive:
                parts = parts[1:]
            if parts[0] == "memes":
                kind = {2: "meme"}.get(len(parts), {"events": "event", "people": "person", "subcultures": "subculture",
                                                   "sites": "site", "cultures": "culture"}.get(parts[1], "other"))
                slug = parts[-1]
            elif parts[0] in ("photos", "videos"):
                kind, slug = parts[0][:-1], re.sub(r"^\d+-", "", parts[-1])
            else:
                kind, slug = "other", parts[-1]
            when = dt.datetime.fromisoformat(mod)
            newest = when if newest is None or when > newest else newest
            pages.append({"url": loc, "kind": kind, "slug": slug, "sensitive": sensitive, "file": f.name,
                          "words": toks(slug), "lastmod": mod[:10]})
        now = dt.datetime.now(dt.timezone.utc)
        files[f.name] = {"pages": len(rows), "newest": newest.isoformat() if newest else None,
                         "age_days": (now - newest).days if newest else None,
                         "file_age_days": (now - dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc)).days}
    return pages, files


def stale_lines(files):
    """The sitemaps are saved together, so the copy's age is the younger of: the file's own date (exact on his Mac,
    too young on a staged copy) and the newest page across all of them (KYM updates the confirmed list every hour,
    so that's within a day of the save). A small list like trending videos can have an old newest page and still
    be a fresh copy."""
    ages = [f["age_days"] for f in files.values() if f["age_days"] is not None]
    saved = min(ages) if ages else None
    out = []
    for name, f in files.items():
        age = f["file_age_days"] if saved is None else min(f["file_age_days"], saved)
        f["copy_age_days"] = age
        if age >= STALE_DAYS:
            out.append(f"STALE  {name}: saved about {age} days ago. Re-save it from knowyourmeme.com.")
    return out


def speakable(p):
    return (p["kind"] == "meme" and not p["sensitive"] and p["file"].startswith("kym")
            and not DENY.intersection(p["words"]) and not {"rule", "34"} <= set(p["words"]))


def entries(md):
    """[(number, title, narration, [stage directions])] with compile.py's rules: an entry is the first paragraph
    after its **N. Title.** line; stage directions up to the next entry or section belong to it"""
    out, cur, para, stage = [], None, [], []

    def close():
        nonlocal cur, para, stage
        if cur:
            out.append((cur[0], cur[1], " ".join(cur[2]), stage))
        cur, para, stage = None, [], []

    for raw in md.splitlines():
        line = raw.rstrip()
        m = ENTRY_RE.match(line)
        if m:
            close(); cur = (int(m.group(1)), m.group(2).strip(), []); continue
        if line.startswith("## ") or line.startswith("# "):
            close(); continue
        s = STAGE_RE.match(line)
        if s:
            if cur:
                stage.append(s.group(1).strip())
            continue
        if cur is None:
            continue
        if not line or line.startswith("---"):
            if cur[2]:
                cur = (cur[0], cur[1], cur[2], True)   # narration done; later stage directions still attach
            continue
        if len(cur) == 3:
            cur[2].append(line)
    close()
    return out


def picks(stage):
    return [re.split(r"[\s.]", s.split(":", 1)[1].strip())[0] for s in stage if s.lower().startswith("meme:")]


def no_meme(narr, stage):
    if DEATH.search(narr):
        return "people died in this story"
    if any("no meme" in s.lower() for s in stage):
        return "the script says no meme"
    return None


def suggest(md, pages, top=6, volumes=None):
    pool = [p for p in pages if speakable(p)]
    df = Counter(w for p in pool for w in set(map(stem, p["words"])))
    n = len(pool)
    idf = {w: math.log(n / c) for w, c in df.items()}
    trend = {w for p in pages if p["kind"] in ("photo", "video") for w in p["words"]}
    res = []
    for num, title, narr, stage in entries(md):
        why = no_meme(narr, stage)
        if why:
            res.append({"n": num, "title": title, "skip": why, "candidates": [], "picked": picks(stage)}); continue
        weight = Counter()
        for w in toks(title):
            weight[stem(w)] += 2
        for w in toks(narr):
            weight[stem(w)] += 1
        keys = {w: c for w, c in weight.items() if w not in STOP and len(w) > 2 and not w.isdigit()}
        cands = []
        for p in pool:
            pw = [stem(w) for w in p["words"]]
            shared = sorted(set(pw) & set(keys))
            if not shared or max(idf.get(w, 0) for w in shared) < 5.0:   # needs one rare shared word, like "elmo"
                continue
            score = sum(idf[w] * min(keys[w], 3) for w in shared) * math.sqrt(len(shared) / len(set(pw)))
            kw = ALIASES.get(p["slug"], " ".join(p["words"]) + " meme")
            cands.append({"slug": p["slug"], "url": p["url"], "shared": shared, "score": round(score, 1),
                          "lastmod": p["lastmod"], "trending": bool(set(p["words"]) & trend - STOP),
                          "search": kw, "volume": (volumes or {}).get(kw)})
        cands.sort(key=lambda c: (-(c["volume"] or 0) if volumes else 0, -c["score"]))
        res.append({"n": num, "title": title, "skip": None, "candidates": cands[:top], "picked": picks(stage)})
    return res


def report(res, files, pages):
    have = {p["slug"] for p in pages if speakable(p)}
    out = ["# Meme pass: candidates", ""]
    stale = stale_lines(files)
    out += [f"- {name}: {f['pages']:,} pages, saved about {f['copy_age_days']} days ago, newest page "
            f"{f['newest'][:10] if f['newest'] else 'none'}" for name, f in files.items()]
    out += [""] + (stale or ["All copies are under %d days old." % STALE_DAYS])
    out += ["", "## Evergreen reaction memes (fit by situation, any entry)", ""]
    out += [f"- `{s}`: {note}" for s, note in EVERGREEN.items() if s in have]
    for r in res:
        out += ["", f"## {r['n']}. {r['title']}", ""]
        if r["picked"]:
            out.append(f"Picked: {', '.join('`%s`' % p for p in r['picked'])}")
        if r["skip"]:
            out.append(f"No meme: {r['skip']}."); continue
        if not r["candidates"]:
            out.append("No keyword match. Use an evergreen meme only if one fits the situation, or none.")
            continue
        out += ["| meme | matched on | score | US searches a month | updated |", "| --- | --- | --- | --- | --- |"]
        for c in r["candidates"]:
            vol = "" if c["volume"] is None else f"{c['volume']:,}"
            out.append(f"| [{c['slug']}]({c['url']}){' (trending)' if c['trending'] else ''} | {', '.join(c['shared'])} "
                       f"| {c['score']} | {vol} | {c['lastmod']} |")
    return "\n".join(out) + "\n"


def check(md, pages, files):
    by = {p["slug"]: p for p in pages if p["file"].startswith("kym")}
    bad = []
    for num, title, narr, stage in entries(md):
        ps = picks(stage)
        if len(ps) > 1:
            bad.append(f"#{num} {title}: {len(ps)} memes (at most one per entry)")
        why = no_meme(narr, stage)
        if ps and why:
            bad.append(f"#{num} {title}: has a meme but {why}")
        for s in ps:
            p = by.get(s)
            if not p:
                bad.append(f"#{num} {title}: '{s}' isn't in the saved KYM confirmed list")
            elif not speakable(p):
                bad.append(f"#{num} {title}: '{s}' is {'sensitive' if p['sensitive'] else 'a ' + p['kind'] + ' page'} "
                           "or has a blocked word")
    return bad


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "suggest", "check"):
        p = sub.add_parser(name)
        if name != "scan":
            p.add_argument("script")
        p.add_argument("--memes", default=str(MEMES))
        if name == "suggest":
            p.add_argument("--volumes", help="JSON {search term: US searches a month}, from SE Ranking")
            p.add_argument("--want-volumes", action="store_true", help="print the search terms to look up")
            p.add_argument("--top", type=int, default=6)
            p.add_argument("--out")
    a = ap.parse_args()
    pages, files = load(a.memes)
    if not pages:
        sys.exit(f"No sitemaps in {a.memes}. Save them by hand from knowyourmeme.com (SKILL.md, the meme pass).")
    if a.cmd == "scan":
        kinds = Counter((p["file"], p["kind"], p["sensitive"]) for p in pages)
        for (f, k, s), c in sorted(kinds.items()):
            print(f"{f:28s} {k:11s} {'sensitive' if s else '':9s} {c:6,}")
        print(f"speakable memes: {sum(map(speakable, pages)):,}")
        for line in stale_lines(files) or ["fresh: every copy was saved under %d days ago" % STALE_DAYS]:
            print(line)
        return
    md = Path(a.script).read_text(encoding="utf-8")
    if a.cmd == "check":
        bad = check(md, pages, files)
        for line in stale_lines(files) + bad:
            print(line)
        print("meme check: %s" % ("FAIL" if bad else "ok"))
        sys.exit(1 if bad else 0)
    vols = json.loads(Path(a.volumes).read_text()) if a.volumes else None
    res = suggest(md, pages, a.top, vols)
    if a.want_volumes:
        print(json.dumps(sorted({c["search"] for r in res for c in r["candidates"]}), indent=1))
        return
    text = report(res, files, pages)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8"); print("wrote", a.out)
    else:
        print(text)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""compile.py: script.md -> manifest.json, the list every later stage reads.

  python3 engine/compile.py <video folder>            writes <video folder>/manifest.json and prints the checks

The grammar (the same for every format; formats/*.md say what goes in each part):

  # Title                                   optional; video.json holds the title
  (paragraphs before the first ##)          the cold open, one segment per paragraph
  ## COLD OPEN                              the same, written as a section
  ## LABEL: Name                            a section (LEVEL 3: The Twilight Zone, FUTURE 2: Fuel at $5)
  (paragraphs right after a ##)             the section's intro, spoken over its card
  **N. Title.**                             a numbered segment; its paragraphs are its narration. The title is the
                                            on-screen label and is never spoken
  ## OUTRO                                  the closing, spoken over the end card
  *(...)*                                   a stage direction, never spoken. It belongs to the block it sits in:
      *(sources: [Name](https://...), [Name](https://...))*
      *(look: what the still shows)*        one still per look, in order; several per segment split its time
      *(clip: how the hero moves)*          a Higgsfield clip for the look just above
      *(stat: "BIG NUMBER" "one short line")*   a fact card instead of a still, counted as a look
      *(card: "first words" "last words")*  the brand card, shown while those words are spoken
      *(short: "first words" "last words")* a short cut from these words (argument format)
      *(meme: slug)*                        the meme pass's pick (memes.py)

Checks are mechanical: numbering, sources, looks, card and short words that really are in the narration, and the
format's own rules (formats/*.md). Problems print as FAIL (fix before voicing) or NOTE.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Video, load_json  # noqa: E402

SEG_RE = re.compile(r"^\*\*(\d+)\.\s*(.+?)\*\*\s*$")
SEC_RE = re.compile(r"^##\s+(.+?)\s*$")
DIR_RE = re.compile(r"^\*\((.*)\)\*\s*$")
OPEN_LABELS = ("COLD OPEN", "OPEN", "INTRO")
OUTRO_LABELS = ("OUTRO", "END", "CLOSE", "CLOSING")
TTS = [("⚑", ""), ("×", " times "), ("→", " to "), ("≤", " at most "), ("≥", " at least "), ("**", ""), ("`", ""),
       ("—", ", "), ("–", " to ")]


def clean(text):
    t = text
    for a, b in TTS:
        t = t.replace(a, b)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)          # a link reads as its words
    t = re.sub(r"\s+,", ",", re.sub(r"\s+", " ", t)).strip()
    return t


def quoted(body):
    return re.findall(r'"([^"]+)"|“([^”]+)”', body)


def two_quotes(body):
    q = [a or b for a, b in quoted(body)]
    return q[:2] if len(q) >= 2 else None


def parse(md):
    blocks, title = [], None
    cur = None                      # the block directions attach to
    pending = []                    # directions written above the paragraph they belong to
    orphans = []                    # directions with no paragraph after them before the next heading
    section = {"index": 0, "label": "COLD OPEN", "name": "", "kind": "open"}
    sections = []
    para = []
    seg_open = None                 # (number, title) of the segment heading waiting for its narration

    def new_block(kind, text, number=None, seg_title=None):
        nonlocal pending
        b = {"kind": kind, "section": section["index"], "section_label": section["label"],
             "section_name": section["name"], "number": number, "title": seg_title, "text": text,
             "notes": {"sources": [], "looks": [], "card": None, "shorts": [], "memes": []}}
        blocks.append(b)
        for d in pending:
            apply(b, d)
        pending = []
        return b

    def flush():
        nonlocal para, cur
        text = " ".join(p.strip() for p in para).strip()
        para = []
        if not text:
            return
        kind = section["kind"]
        if kind in ("open", "outro"):
            cur = new_block(kind, text)                  # one segment per paragraph
        elif seg_open:
            if cur and cur["kind"] == "segment" and cur["number"] == seg_open[0]:
                cur["text"] += " " + text            # a second paragraph of the same segment
            else:
                cur = new_block("segment", text, *seg_open)
        else:
            if cur and cur["kind"] == "section" and cur["section"] == section["index"]:
                cur["text"] += " " + text
            else:
                cur = new_block("section", text)

    def heading():
        nonlocal pending, cur
        flush()
        if pending:
            orphans.extend(pending)
            pending = []
        cur = None

    def apply(b, body):
        low = body.lower()
        n = b["notes"]
        if low.startswith("sources:"):
            n["sources"] += [list(x) for x in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", body)]
        elif low.startswith("look:"):
            n["looks"].append({"brief": body.split(":", 1)[1].strip(), "clip": None, "stat": None})
        elif low.startswith("stat:"):
            q = two_quotes(body)
            n["looks"].append({"brief": None, "clip": None, "stat": q or [body.split(":", 1)[1].strip(), ""]})
        elif low.startswith("clip:"):
            if not n["looks"]:
                n["looks"].append({"brief": None, "clip": None, "stat": None})
            n["looks"][-1]["clip"] = body.split(":", 1)[1].strip()
        elif low.startswith("card:"):
            n["card"] = two_quotes(body)
        elif low.startswith("short:"):
            q = two_quotes(body)
            if q:
                n["shorts"].append(q)
        elif low.startswith("meme:"):
            n["memes"].append(body.split(":", 1)[1].strip().split()[0].strip(".") if body.split(":", 1)[1].strip() else "")

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("# ") and title is None and not blocks:
            title = line[2:].strip()
            continue
        if not line.strip() or line.strip() == "---":
            flush()
            continue
        m = DIR_RE.match(line.strip())
        if m:
            flush()
            if cur is not None:
                apply(cur, m.group(1))
            else:
                pending.append(m.group(1))
            continue
        m = SEC_RE.match(line)
        if m:
            heading()
            label, _, name = m.group(1).partition(":")
            label, name = label.strip().upper(), name.strip()
            seg_open = None
            if label in OPEN_LABELS:
                section = {"index": 0, "label": "COLD OPEN", "name": name, "kind": "open"}
            elif label in OUTRO_LABELS:
                section = {"index": len(sections) + 1, "label": "OUTRO", "name": name, "kind": "outro"}
            else:
                section = {"index": len(sections) + 1, "label": label, "name": name, "kind": "body"}
                sections.append({"index": section["index"], "label": label, "name": name})
            continue
        m = SEG_RE.match(line.strip())
        if m:
            heading()
            seg_open = (int(m.group(1)), m.group(2).strip().rstrip("."))
            if section["kind"] != "body":
                raise SystemExit("segment %s sits outside a section (put a ## heading above it)" % m.group(1))
            continue
        para.append(line)
    heading()
    return title, sections, blocks, orphans


def build(video):
    md = (video.dir / "script.md").read_text(encoding="utf-8")
    title, sections, blocks, orphans = parse(md)
    segs, counts = [], {}
    for b in blocks:
        k = b["kind"]
        counts[k] = counts.get(k, 0) + 1
        if k == "segment":
            sid = "seg-%03d" % b["number"]
        elif k == "section":
            sid = "sec-%02d" % b["section"]
        else:
            sid = "%s-%02d" % (k, counts[k])
        text = clean(b["text"])
        looks = [dict(l, id="%s-%d" % (sid, i + 1)) for i, l in enumerate(b["notes"]["looks"])]
        segs.append({"id": sid, "kind": k, "section": b["section"], "section_label": b["section_label"],
                     "section_name": b["section_name"], "number": b["number"], "title": b["title"],
                     "narration": text, "chars": len(text), "words": len(text.split()),
                     "sources": b["notes"]["sources"], "looks": looks, "card": b["notes"]["card"],
                     "shorts": b["notes"]["shorts"], "memes": b["notes"]["memes"]})
    ids = [s["id"] for s in segs]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SystemExit("FAIL two blocks share an id: %s (segment numbers must be unique)" % ", ".join(dupes))
    narr = dict(video.brand.get("narrator", {}))
    narr.update(video.cfg.get("narrator", {}))
    wpm = float(narr.get("wpm", 150))
    chars = sum(s["chars"] for s in segs)
    words = sum(s["words"] for s in segs)
    return {"meta": {"title": video.cfg["title"], "script_title": title, "format": video.format,
                     "brand": video.cfg["brand"], "narrator": narr, "sections": sections,
                     "segments": len(segs), "numbered": sum(1 for s in segs if s["kind"] == "segment"),
                     "chars": chars, "words": words, "est_minutes": round(words / wpm, 1),
                     "orphan_directions": orphans},
            "segments": segs}


def checks(video, man):
    fails, notes = [], []
    segs = man["segments"]
    body = [s for s in segs if s["kind"] == "segment"]
    fmt = video.format
    nums = [s["number"] for s in body]
    if not body:
        fails.append("no numbered segments (**1. Title.**)")
    if nums and nums != list(range(nums[0], nums[0] + len(nums))):
        notes.append("segment numbers skip or repeat: %s" % nums)
    if not any(s["kind"] == "open" for s in segs):
        fails.append("no cold open: the voice should start in the first few seconds, so open before the first ##")
    if not any(s["kind"] == "outro" for s in segs):
        notes.append("no ## OUTRO: the end card will have no narration")
    for d in man["meta"].get("orphan_directions", []):
        fails.append("*(%s)* has no paragraph after it before the next heading" % d[:60])
    for s in body:
        if not s["sources"]:
            fails.append("%s (%s) has no *(sources: ...)*" % (s["id"], s["title"]))
        if not s["looks"]:
            notes.append("%s has no *(look: ...)*: it will show a fact card with its title" % s["id"])
    for s in segs:
        low = " ".join(w.lower() for w in re.findall(r"[\w']+", s["narration"]))
        def present(phrase):
            p = " ".join(w.lower() for w in re.findall(r"[\w']+", phrase))
            return p and p in low
        if s["card"]:
            if not all(present(x) for x in s["card"]):
                fails.append("%s: the card words %s aren't both in its narration" % (s["id"], s["card"]))
        for sh in s["shorts"]:
            if not all(present(x) for x in sh):
                fails.append("%s: the short words %s aren't both in its narration" % (s["id"], sh))
        for lk in s["looks"]:
            if lk["brief"] is None and lk["stat"] is None:
                fails.append("%s: a *(clip: ...)* with no *(look: ...)* above it" % s["id"])
    secs = man["meta"]["sections"]
    if fmt == "iceberg":
        for sec in secs:
            if not re.match(r"LEVEL \d+$", sec["label"]):
                fails.append("iceberg sections are '## LEVEL n: Name', not %r" % sec["label"])
            n = sum(1 for s in body if s["section"] == sec["index"])
            if n < 2:
                fails.append("%s has %d entries; every level holds several stories" % (sec["label"], n))
        for s in body:
            if len([l for l in s["looks"] if l["brief"] or l["stat"]]) > 1:
                notes.append("%s has more than one look; an iceberg entry usually has one" % s["id"])
    elif fmt == "answers":
        for s in body:
            if not s["title"].endswith("?"):
                fails.append("%s: an answers segment's title is the question, ending in '?' (%r)" % (s["id"], s["title"]))
    elif fmt == "argument":
        labels = [x["label"] for x in secs]
        need = [("THE PROBLEM",), ("FUTURE",), ("THE VERDICT", "CONCLUSION"), ("THE FIX", "THE SOLUTION")]
        pos = []
        for alts in need:
            hit = [i for i, l in enumerate(labels) if any(l.startswith(a) for a in alts)]
            if not hit:
                fails.append("argument needs a '## %s' section" % alts[0])
            pos.append(hit[0] if hit else None)
        if all(p is not None for p in pos) and pos != sorted(pos):
            fails.append("argument sections go in this order: THE PROBLEM, FUTURE n, THE VERDICT, THE FIX")
        if sum(1 for l in labels if l.startswith("FUTURE")) < 2:
            fails.append("argument needs at least two '## FUTURE n: Name' sections")
        fix = [x["index"] for x in secs if x["label"].startswith(("THE FIX", "THE SOLUTION"))]
        main_words = sum(s["words"] for s in segs if s["kind"] in ("segment", "section"))
        fix_words = sum(s["words"] for s in segs if s["section"] in fix and s["kind"] in ("segment", "section"))
        if main_words and fix_words / main_words > 0.5:
            fails.append("the fix is %d%% of the body; the problem side gets at least half" % round(100 * fix_words / main_words))
        shorts = sum(len(s["shorts"]) for s in segs)
        if shorts < 3:
            notes.append("only %d *(short: ...)* marks; an argument video usually yields 3 to 6 shorts" % shorts)
        for s in body:
            n = len(s["looks"])
            if n and s["words"] / n > 60:
                notes.append("%s: %d words over %d looks; a story wants a new picture every 25 to 50 words"
                             % (s["id"], s["words"], n))
    return fails, notes


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    video = Video(sys.argv[1])
    man = build(video)
    fails, notes = checks(video, man)
    (video.dir / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    m = man["meta"]
    looks = sum(len(s["looks"]) for s in man["segments"])
    clips = sum(1 for s in man["segments"] for l in s["looks"] if l["clip"])
    print("%s (%s): %d segments, %d numbered, %d looks (%d with clips), %d words, %d characters, about %.1f minutes at %s wpm"
          % (m["title"], m["format"], m["segments"], m["numbered"], looks, clips, m["words"], m["chars"],
             m["est_minutes"], m["narrator"].get("wpm", 150)))
    for x in notes:
        print("NOTE " + x)
    for x in fails:
        print("FAIL " + x)
    print("wrote %s" % (video.dir / "manifest.json"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

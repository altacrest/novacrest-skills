#!/usr/bin/env python3
"""meta.py: the upload text, the sources page and the thumbnail.

  python3 engine/meta.py <video folder> [--video-url https://youtu.be/...] [--sources-url https://...] [--tag _pilot]

Writes, all from the script and the cut's own timeline (nothing invented here):
  out/youtube.txt          title, description (the hook, chapters, how it was made, the brand line, sources or a link to
                           them), tags. YouTube caps a description at 5,000 characters, so the sources go in the
                           description when they fit and on the sources page otherwise.
  out/sources.md           every segment's sources under its chapter
  out/shorts/shorts_upload.csv   per short: file, YouTube title (under 100 characters), YouTube description, Instagram
                           caption. The hook is the segment's own first sentences, so every fact is one the video says.
  out/thumbnail.png        1280x720: video.json's "thumbnail_look" still (else the first segment's), the title, the logo
Hook, title and tag ideas come from video.json when they're there ("youtube_title", "hook", "tags"); a YouTube SEO
skill can rework youtube.txt afterwards.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ENGINE, Video, ts  # noqa: E402
from assemble import find_image  # noqa: E402

LIMIT = 5000


def first_sentences(text, least=90, most=230):
    out = ""
    for sent in re.split(r"(?<=[.!?])(?<! [A-Z]\.)\s+", text.strip()):
        out = (out + " " + sent).strip()
        if len(out) >= least:
            break
    return out if len(out) <= most else out[:most].rsplit(" ", 1)[0] + "..."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--video-url", default="")
    ap.add_argument("--sources-url", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    video = Video(a.video)
    man = video.manifest()
    slug = video.cfg["slug"] + a.tag
    tl = json.loads((video.out / (slug + ".json")).read_text())
    segs = man["segments"]
    title = video.cfg.get("youtube_title") or video.cfg["title"]
    hook = video.cfg.get("hook") or " ".join(s["narration"] for s in segs if s["kind"] == "open")
    chapters = tl["chapters"]
    ch_lines = ["%s %s" % (ts(c["t"]), c["title"]) for c in chapters] if len(chapters) >= 3 else []

    # sources, grouped by chapter
    starts = {it["id"]: it["start"] for it in tl["items"]}
    by_ch = []
    for c, nxt in zip(chapters, chapters[1:] + [{"t": 1e9}]):
        rows = []
        for s in segs:
            if s["sources"] and c["t"] <= starts.get(s["id"], -1) < nxt["t"]:
                rows.append((s, s["sources"]))
        if rows:
            by_ch.append((c, rows))
    md = ["# Sources: %s" % video.cfg["title"], ""]
    for c, rows in by_ch:
        md += ["## %s (%s)" % (c["title"], ts(c["t"])), ""]
        for s, srcs in rows:
            label = ("#%d %s" % (s["number"], s["title"])) if s.get("number") else (s["title"] or s["id"])
            md.append("- %s: %s" % (label, "; ".join("[%s](%s)" % (t, u) for t, u in srcs)))
        md.append("")
    video.out.mkdir(parents=True, exist_ok=True)
    (video.out / "sources.md").write_text("\n".join(md), encoding="utf-8")

    made = ("How this was made: the script was researched and written with AI, and every fact was checked against a "
            "published source. The narrator is an AI voice. The pictures are AI illustrations, labeled AI IMAGE on "
            "screen%s." % (", and the moving shots are AI video, labeled AI VIDEO" if any(
                w.get("clip") for it in tl["items"] for w in it["windows"]) else ""))
    site = video.brand.get("site", "")
    cta = video.brand.get("cta", "").replace(site, "https://" + site) if site else video.brand.get("cta", "")
    brand = "Made by the %s team. %s" % (video.brand["name"], cta)        # the spoken frame lines say "dot io"; this links
    head = [hook.strip(), ""]
    if ch_lines:
        head += ["Chapters"] + ch_lines + [""]
    tail = [made, "", brand, ""]
    src_inline = ["Sources"]
    for c, rows in by_ch:
        for s, srcs in rows:
            label = ("#%d %s" % (s["number"], s["title"])) if s.get("number") else (s["title"] or "")
            src_inline.append("%s: %s" % (label, "; ".join("%s %s" % (t, u) for t, u in srcs)))
    hashtags = video.brand.get("youtube", {}).get("hashtags", "")
    desc = "\n".join(head + tail + src_inline + ["", hashtags]).strip()
    where = "in the description"
    if len(desc) > LIMIT:
        link = a.sources_url or "[link to the sources page]"
        desc = "\n".join(head + tail + ["Sources for every story: %s" % link, "", hashtags]).strip()
        where = "on the sources page (out/sources.md; put it online and pass --sources-url)"
    tags = list(dict.fromkeys((video.cfg.get("tags") or []) + video.brand.get("youtube", {}).get("tags", [])))
    while len(", ".join(tags)) > 480:
        tags.pop()
    yt = video.brand.get("youtube", {})
    settings = ["Settings in YouTube Studio:",
                "- Channel: %s" % yt.get("channel", "the brand's channel"),
                "- Category: %s" % {"27": "Education", "28": "Science & Technology", "22": "People & Blogs"}.get(yt.get("category_id", ""), yt.get("category_id", "")),
                "- Made for kids: No",
                "- Altered or synthetic content: Yes (AI voice and pictures)",
                "- Paid promotion: No",
                "- Thumbnail: out/thumbnail.png",
                "- End screen: the last 12 seconds hold the end card for its elements"]
    (video.out / "youtube.txt").write_text("TITLE\n%s\n\nDESCRIPTION\n%s\n\nTAGS\n%s\n\n%s\n" % (
        title, desc, ", ".join(tags), "\n".join(settings)), encoding="utf-8")
    print("wrote out/youtube.txt: title %d characters, description %d of %d, %d chapters, sources %s"
          % (len(title), len(desc), LIMIT, len(ch_lines), where))
    if len(title) > 100:
        print("PROBLEM the title is over YouTube's 100 characters")

    # shorts
    sj = video.out / "shorts" / "shorts.json"
    if sj.exists():
        rows = []
        segmap = {s["id"]: s for s in segs}
        for r in json.loads(sj.read_text()):
            if r.get("skipped"):
                continue
            s = segmap[r["segment"]]
            h = first_sentences(r["hook"])
            t = "%s | %s" % (s["title"], video.cfg["title"])
            if video.format == "iceberg":
                t = "%s | %s #%d" % (s["title"], video.cfg["title"], s["number"])
            if len(t) > 100:
                t = s["title"][:100]
            full = ("Full video: %s" % a.video_url) if a.video_url else "Full video on the %s channel." % video.brand["name"]
            ytd = "%s\n\n%s\n\n%s\n\n#shorts %s" % (h, full, cta, hashtags)
            ig = "%s\n\nFull video on YouTube: search \"%s %s\".\n\n%s" % (
                h, video.brand["name"], video.cfg["title"], (hashtags + " #reels").strip())
            rows.append({"id": r["id"], "file": r["file"], "youtube_title": t, "youtube_description": ytd, "instagram_caption": ig})
        if rows:
            out = video.out / "shorts" / "shorts_upload.csv"
            with out.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            print("wrote %s (%d rows, longest title %d characters)" % (out, len(rows), max(len(r["youtube_title"]) for r in rows)))

    # thumbnail
    look = video.cfg.get("thumbnail_look")
    img = find_image(video, look) if look else None
    if not img:
        for s in segs:
            for lk in s["looks"]:
                img = img or (find_image(video, lk["id"]) if s["kind"] == "segment" else None)
    numbered = [s for s in segs if s["kind"] == "segment"]
    from common import FORMATS
    kick = video.cfg.get("kicker") or FORMATS[video.format]["kicker"].format(n=len(numbered), levels=len(man["meta"]["sections"]))
    spec = {"brand": dict(video.brand, dir=str(video.brand_dir)), "out": str(video.out),
            "items": [{"file": "thumbnail.png", "kind": "thumb", "transparent": False, "size": [1280, 720],
                       "extra": {"title": video.cfg.get("thumbnail_title") or video.cfg["title"], "kicker": kick,
                                 "image": str(img) if img else ""}}]}
    p = video.work / "thumb.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(spec, ensure_ascii=False))
    r = subprocess.run(["node", str(ENGINE / "render.mjs"), str(p), "--force"], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr[-800:])


if __name__ == "__main__":
    main()

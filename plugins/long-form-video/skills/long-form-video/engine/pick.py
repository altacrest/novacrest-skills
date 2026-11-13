#!/usr/bin/env python3
"""pick.py: pick an iceberg's entries from the discovery passes on evidence, not taste.

Claude runs the research passes in formats/iceberg.md (a first pass plus investigators' lenses), puts every
candidate in one candidates.json with the `lens` that found it, checks each one against a source, marks what other
icebergs already covered, and scores on_topic, story and surprise. This script measures how well known each candidate
is and makes the final pick the same way every time.

  python3 engine/pick.py views <video folder>/candidates.json
      fills pageviews_12mo: English Wikipedia views over the last 12 full months, summed over the candidate's articles
      (Wikimedia's public pageviews API, no key). A candidate with no article counts 0, the most obscure.
      When wikimedia.org can't be reached, it counts the languages each candidate's article is in instead (from
      en.wikipedia.org; 0 without an article) and `pick` ranks on that. If neither works it stops and says so.
  python3 engine/pick.py pick <video folder>/candidates.json [--out <video folder>/picked.json]
      drops candidates that aren't sourced or are off topic (on_topic 0), sorts the rest from most to least known,
      cuts that order into video.json's levels bands, takes the best scored candidates in each band
      (2 x on_topic + story + surprise, minus 1 when another iceberg already covered it), holds current events (a year
      within the last two) to video.json's max_current_share, then prints the levels and a per-lens summary for the report.

A candidate in candidates.json:
  {"title": "...", "lens": "crime", "wiki": ["Article title"], "year": 2025, "sourced": true, "covered": false,
   "on_topic": 2, "on_topic_why": "...", "story": 1, "story_why": "...", "surprise": 2, "surprise_why": "...",
   "pageviews_12mo": null}
"""
import argparse
import datetime as dt
import json
import statistics
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user/"
       "%s/monthly/%s/%s")
UA = "long-form-video-skill/1.0 (iceberg entry research; https://github.com/altacrest/novacrest-skills)"
WIKI_API = "https://en.wikipedia.org/w/api.php"
CONTROL = "Main Page"  # always heavily viewed, so an empty answer means the API changed, not that it's obscure


def video_settings(candidates_file):
    """levels, entries and max_current_share from the video folder's video.json (defaults: 6 levels, 36 entries)"""
    cfg = Path(candidates_file).resolve().parent / "video.json"
    v = json.loads(cfg.read_text()) if cfg.exists() else {}
    return {"levels": v.get("levels", 6), "entries": v.get("entries", 36), "max_current_share": v.get("max_current_share", 0.34)}


def window(today):
    """the last 12 full months, as the API's YYYYMMDD stamps"""
    end = today.replace(day=1) - dt.timedelta(days=1)
    y, m = end.year, end.month - 11
    if m <= 0:
        y, m = y - 1, m + 12
    return "%04d%02d01" % (y, m), end.strftime("%Y%m%d")


def url(title, start, end):
    return API % (urllib.parse.quote(title.strip().replace(" ", "_"), safe=""), start, end)


def views(title, start, end):
    import requests
    r = requests.get(url(title, start, end), headers={"User-Agent": UA}, timeout=30)
    if r.status_code == 404:
        return 0  # no such article, or no views in the window
    r.raise_for_status()
    return sum(item["views"] for item in r.json().get("items", []))


def languages(title):
    """how many Wikipedia languages an English article exists in, English included (0 when there's no article)"""
    import requests
    r = requests.get(WIKI_API, params={"action": "query", "prop": "langlinks", "titles": title, "lllimit": "max",
                                       "redirects": 1, "format": "json", "formatversion": 2},
                     headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return 0
    return len(pages[0].get("langlinks", [])) + 1


def lens_of(c):
    return c.get("lens") or c.get("pool") or "?"


def titles_of(c):
    t = c.get("wiki") or []
    return [t] if isinstance(t, str) else list(t)


def cmd_views(a):
    path = Path(a.file)
    cands = json.loads(path.read_text())
    start, end = window(dt.date.today())
    todo = [c for c in cands if a.refresh or c.get("pageviews_12mo") is None]
    try:
        if views(CONTROL, start, end) <= 0:
            raise RuntimeError("the control lookup (%s) came back empty, so the API path may have changed" % CONTROL)
        for c in todo:
            c["pageviews_12mo"] = sum(views(t, start, end) for t in titles_of(c))
    except Exception as e:
        for c in todo:
            c.pop("pageviews_12mo", None)
        print("Couldn't measure page views (%s); counting each article's languages instead." % str(e)[:160],
              file=sys.stderr)
        try:
            for c in cands:
                c["languages"] = max([languages(t) for t in titles_of(c)] or [0])
        except Exception as e2:
            for c in cands:
                c.pop("languages", None)
            path.write_text(json.dumps(cands, indent=2, ensure_ascii=False))
            sys.exit("Couldn't count languages either (%s). Fill pageviews_12mo or languages for every candidate by "
                     "hand, then run `pick`." % str(e2)[:160])
        for c in cands:
            print("%5d languages  %-12s %s" % (c["languages"], lens_of(c), c["title"]))
        path.write_text(json.dumps(cands, indent=2, ensure_ascii=False))
        return
    for c in todo:
        print("%12s  %-12s %s" % ("{:,}".format(c["pageviews_12mo"]), lens_of(c), c["title"]))
    path.write_text(json.dumps(cands, indent=2, ensure_ascii=False))


def split(seq, k):
    """k contiguous bands, sizes as equal as possible, the larger ones first"""
    q, r = divmod(len(seq), k)
    out, i = [], 0
    for b in range(k):
        size = q + (1 if b < r else 0)
        out.append(seq[i:i + size])
        i += size
    return out


def cmd_pick(a):
    v = video_settings(a.file)
    n, levels = a.entries or int(v["entries"]), a.levels or int(v["levels"])
    share = a.max_current if a.max_current is not None else float(v.get("max_current_share", 1.0))
    this_year = dt.date.today().year
    path = Path(a.file)
    cands = json.loads(path.read_text())
    if all(c.get("pageviews_12mo") is not None for c in cands):
        key, label = "pageviews_12mo", "views"
    elif all(c.get("languages") is not None for c in cands):
        key, label = "languages", "languages"
    else:
        sys.exit("run `views` first (or, when it can't reach wikimedia.org, fill `languages` for every candidate)")
    for c in cands:
        c["score"] = (2 * int(c.get("on_topic", 0)) + int(c.get("story", 0)) + int(c.get("surprise", 0))
                      - (1 if c.get("covered") else 0))
        c["current"] = int(c.get("year") or 0) >= this_year - 1
    usable = [c for c in cands if c.get("sourced") and int(c.get("on_topic", 0)) > 0]
    if len(usable) < n:
        sys.exit("only %d usable candidates for %d entries; research more" % (len(usable), n))
    usable.sort(key=lambda c: (-c[key], c["title"]))  # best known first
    bands = split(usable, levels)
    quota = [len(b) for b in split(list(range(n)), levels)]
    picked = [sorted(band, key=lambda c: (-c["score"], -c[key], c["title"]))[:k] for band, k in zip(bands, quota)]

    cap = int(share * n + 1e-9)
    count = lambda: sum(c["current"] for lvl in picked for c in lvl)
    while count() > cap:  # swap the weakest current pick for the best unused, non-current candidate in its band
        swaps = []
        for i, lvl in enumerate(picked):
            spare = [c for c in bands[i] if c not in lvl and not c["current"]]
            cur = [c for c in lvl if c["current"]]
            if spare and cur:
                worst = min(cur, key=lambda c: (c["score"], c[key], c["title"]))
                best = max(spare, key=lambda c: (c["score"], c[key], c["title"]))
                swaps.append((worst["score"] - best["score"], i, worst, best))
        if not swaps:
            print("note: can't get current events under the cap with the candidates on hand", file=sys.stderr)
            break
        _, i, worst, best = min(swaps, key=lambda s: (s[0], s[1]))
        picked[i][picked[i].index(worst)] = best

    for lvl in picked:
        lvl.sort(key=lambda c: (-c[key], c["title"]))
    final = [c for lvl in picked for c in lvl]
    med = lambda xs: int(statistics.median(xs)) if xs else 0
    summary = {"measure": key, "entries": n, "levels": levels, "current": count(), "current_cap": cap,
               "dropped_unsourced": sum(1 for c in cands if not c.get("sourced")),
               "dropped_off_topic": sum(1 for c in cands if c.get("sourced") and int(c.get("on_topic", 0)) == 0),
               "lenses": {}}
    for lens in sorted({lens_of(c) for c in cands}):
        every = [c for c in cands if lens_of(c) == lens]
        kept = [c for c in final if lens_of(c) == lens]
        summary["lenses"][lens] = {"candidates": len(every), "picked": len(kept),
                                   "median_candidates": med([c[key] for c in every]),
                                   "median_picked": med([c[key] for c in kept])}
    out = Path(a.out) if a.out else path.with_name("picked.json")
    out.write_text(json.dumps({"levels": picked, "summary": summary}, indent=2, ensure_ascii=False))

    for i, lvl in enumerate(picked, 1):
        print("Level %d" % i)
        for c in lvl:
            print("  %-46s %-12s %12s %s  score %d%s" % (c["title"][:46], lens_of(c), "{:,}".format(c[key]), label,
                                                       c["score"], "  current" if c["current"] else ""))
    for lens, s in summary["lenses"].items():
        print("%-12s %d candidates (median %s %s), %d picked (median %s %s)" % (
            lens, s["candidates"], "{:,}".format(s["median_candidates"]), label, s["picked"],
            "{:,}".format(s["median_picked"]), label))
    print("ranked on %s; dropped before the pick: %d unsourced, %d off topic; current events %d of %d (cap %d); "
          "saved %s" % ("12-month page views" if key == "pageviews_12mo" else "languages", summary["dropped_unsourced"],
                        summary["dropped_off_topic"], summary["current"], n, cap, out))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("views", help="fill pageviews_12mo from Wikimedia")
    v.add_argument("file")
    v.add_argument("--refresh", action="store_true", help="fetch again even where views are filled in")
    p = sub.add_parser("pick", help="make the final pick")
    p.add_argument("file")
    p.add_argument("--out")
    p.add_argument("--entries", type=int)
    p.add_argument("--levels", type=int)
    p.add_argument("--max-current", type=float)
    a = ap.parse_args()
    (cmd_views if a.cmd == "views" else cmd_pick)(a)


if __name__ == "__main__":
    main()

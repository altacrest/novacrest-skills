#!/usr/bin/env python3
"""style_check.py: a deterministic check that a still has the Blueprint Reality look.

  python3 engine/style_check.py <video folder>/images/*.jpg

Fails a still when a corner is near black (the halo and rounded-corner bug the blog image pipeline checks for) or when the
outer band of the frame isn't mostly light, blue-leaning blueprint paper (a full photo, white paper, a dark or sepia
render). The hero sits in the middle, so the edges are where the paper shows. Prints one JSON line per file and exits 1
if any fails. Thresholds come from the style's own colors: #EAF2FB paper and #7CB6F2 fills pass; white and sepia fail.
"""
import json
import sys

import numpy as np
from PIL import Image

BAND = 0.05        # outer 5% of each side
MIN_PAPER = 0.55   # share of band pixels that look like blueprint paper or fill
MIN_CORNER = 40    # mean of R, G, B at each corner; lower is a black corner


def check(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    h, w, _ = a.shape
    corners = [int(a[y, x].mean()) for y, x in ((2, 2), (2, w - 3), (h - 3, 2), (h - 3, w - 3))]
    bh, bw = max(1, int(h * BAND)), max(1, int(w * BAND))
    band = np.concatenate([a[:bh].reshape(-1, 3), a[-bh:].reshape(-1, 3),
                           a[bh:h - bh, :bw].reshape(-1, 3), a[bh:h - bh, w - bw:].reshape(-1, 3)])
    r, g, b = band[:, 0], band[:, 1], band[:, 2]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    paper = float(((b >= r + 8) & (b >= g - 6) & (luma >= 120)).mean())
    problems = []
    if min(corners) < MIN_CORNER:
        problems.append("black corner")
    if paper < MIN_PAPER:
        problems.append("edges are not pale blueprint paper (%d%% paper-like)" % round(paper * 100))
    return {"file": path, "ok": not problems, "paper_share": round(paper, 3), "corners": corners, "problems": problems}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    results = [check(p) for p in sys.argv[1:]]
    for res in results:
        print(json.dumps(res))
    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()

// Back in claude.ai: plus, Upload or add files; then the mix prompt typed (hw_d, covered and revealed) and sent.
kit.scene('mix', SS.def({
  seq: [[0, 'hw_a'], [1.4, 'hw_c', 0.1], [4.2, 'hw_d', 0.15]],
  texts: [{ html: '<div style="width:604px;height:60px;background:#303030"></div>', x: 436, y: 344, t0: 4.2, fade: 0.15, style: { zIndex: 4 } }],
  patches: [
    { name: 'hw_d_l1', t0: 6.3, fade: 0, type: [6.3, 8.1], tx: [441, 1037], caret: [349, 21], caretOff: 8.1 },
    { name: 'hw_d_l2', t0: 8.1, fade: 0, type: [8.1, 9.2], tx: [441, 793], caret: [377.5, 21], caretOff: 11.35 },
  ],
  rings: [{ r: [444, 66, 210, 26], t0: 1.75, t1: 4.1, pad: 4 }, { r: [1044.5, 409.5, 26.5, 26.5], t0: 10.3, t1: 12.6, pad: 6 }],
  cam: [{ t: 0, x: 752, y: 262, z: 1.45, hold: 4.4 }, { t: 5.5, x: 752, y: 390, z: 1.9 }],
  cur: [[0, 900, 560], [0.4, 900, 560], [1.1, 446, 416], [1.45, 446, 416], [3.2, 540, 79], [3.85, 540, 79], [4.7, 700, 250], [5.5, 640, 362], [6.0, 640, 362], [6.6, 900, 280], [10.0, 900, 280], [10.9, 1058, 423], [13, 1058, 423]],
  clicks: [1.3, 3.75, 5.8, 11.35],
  caps: [['mix-a', 0.3, 5.65], ['mix-b', 6.0, 12.7]],
  build(R) { for (const q of R.patches) if (q.caretEl) q.caretEl.style.background = '#ECECEC'; },
}));

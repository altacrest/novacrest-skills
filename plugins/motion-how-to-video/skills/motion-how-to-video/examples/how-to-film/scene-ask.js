// claude.ai new chat: the film prompt is typed into the composer (hw_b is the typed state; its text is
// covered, then revealed line by line), then sent.
kit.scene('ask', SS.def({
  seq: [[0, 'hw_a'], [4.85, 'hw_b', 0.12]],
  texts: [{ html: '<div style="width:616px;height:88px;background:#303030"></div>', x: 436, y: 344, t0: 4.85, fade: 0, style: { zIndex: 4 } }],
  patches: [
    { name: 'hw_b_l1', t0: 5.3, fade: 0, type: [5.3, 7.1], tx: [441, 1023], caret: [349, 21], caretOff: 7.1 },
    { name: 'hw_b_l2', t0: 7.1, fade: 0, type: [7.1, 8.9], tx: [441, 1045], caret: [377.5, 21], caretOff: 8.9 },
    { name: 'hw_b_l3', t0: 8.9, fade: 0, type: [8.9, 9.5], tx: [441, 598], caret: [406, 21], caretOff: 14.6 },
  ],
  rings: [{ r: [1044.5, 438, 26.5, 26.5], t0: 13.2, t1: 15.3, pad: 6 }],
  cam: [{ t: 0, z: 1, hold: 2.1 }, { t: 3.7, x: 752, y: 403, z: 1.9 }],
  cur: [[0, 760, 600], [2.0, 760, 600], [3.6, 640, 362], [4.1, 640, 362], [4.8, 900, 296], [12.9, 900, 296], [14.0, 1058, 451], [15.5, 1058, 451]],
  clicks: [3.9, 14.55],
  caps: [['ask-a', 0.3, 4.85], ['ask-b', 5.2, 10.05], ['ask-c', 10.4, 15.2]],
  build(R) { for (const q of R.patches) if (q.caretEl) q.caretEl.style.background = '#ECECEC'; },
}));

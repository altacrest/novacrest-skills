// The film page with the finished film on the stage; the download arrow under the player exports the MP4.
kit.scene('export', SS.def({
  seq: [[0, 'hw_mp0']],
  patches: [{ name: 'hw_tf6', t0: 0, fade: 0 }],
  texts: [{ html: '<div style="width:28px;height:14px;background:#1A1A19;color:#F0EFEC;font:500 12.2px/14px var(--sans, system-ui, sans-serif);font-variant-numeric:tabular-nums;padding-left:2px;box-sizing:border-box">0:28</div>', x: 101, y: 677, t0: 0, fade: 0 }],
  rings: [{ r: [1358, 673, 22, 22], t0: 2.0, t1: 6.1, pad: 6 }],
  cam: [{ t: 0, z: 1, hold: 0.5 }, { t: 1.7, x: 1512, y: 745, z: 1.25 }],
  cur: [[0, 1330, 560], [0.7, 1330, 560], [2.6, 1369, 684], [6.5, 1369, 684]],
  clicks: [3.15],
  caps: [['export', 0.3, 6.1]],
}));

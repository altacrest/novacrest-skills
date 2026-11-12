// Capture flashes on the real OmniOrders screens, then the film page; play runs a montage of the
// transfer film's own frames inside the player, with the time readout and a pause icon drawn over.
kit.scene('build', SS.def({
  seq: [[0, 'tr_list'], [0.9, 'tr_s1', 0.1], [1.8, 'tr_s3_items', 0.1], [2.7, 'tr_s4', 0.1], [3.7, 'hw_mp0', 0.3]],
  patches: [
    { name: 'hw_tf1', t0: 6.05, t1: 7.07, fade: 0.12 },
    { name: 'hw_tf2', t0: 6.95, t1: 7.97, fade: 0.12 },
    { name: 'hw_tf3', t0: 7.85, t1: 8.87, fade: 0.12 },
    { name: 'hw_tf4', t0: 8.75, t1: 9.72, fade: 0.12 },
    { name: 'hw_tf5', t0: 9.6, t1: 10.52, fade: 0.12 },
    { name: 'hw_tf6', t0: 10.4, fade: 0.12 },
  ],
  cam: [{ t: 0, z: 1 }],
  cur: [[0, 1150, 640], [3.6, 1150, 640], [5.2, 24, 684], [5.85, 24, 684], [6.9, 1330, 560], [11, 1330, 560]],
  clicks: [5.65],
  caps: [['build-a', 0.3, 4.45], ['build-b', 4.8, 10.7]],
  build(R, kit) {
    this.flash = kit.h('<div style="position:absolute;left:0;top:0;width:1512px;height:745px;background:#fff;opacity:0;z-index:9;pointer-events:none"></div>');
    R.world.append(this.flash);
    this.clock = kit.h('<div style="position:absolute;left:101px;top:677px;width:28px;height:14px;background:#1A1A19;color:#F0EFEC;font:500 12.2px/14px var(--sans, system-ui, sans-serif);font-variant-numeric:tabular-nums;padding-left:2px;box-sizing:border-box;display:none;z-index:6"></div>');
    this.pause = kit.h('<div style="position:absolute;left:15px;top:675px;width:18px;height:18px;background:#1A1A19;display:none;z-index:6"><i style="position:absolute;left:4.5px;top:3.5px;width:1.7px;height:11px;border-radius:1px;background:#F0EFEC"></i><i style="position:absolute;left:11px;top:3.5px;width:1.7px;height:11px;border-radius:1px;background:#F0EFEC"></i></div>');
    R.world.append(this.clock, this.pause);
  },
  tick(R, t) {
    let o = 0;
    for (const c of [0.3, 1.2, 2.1, 3.0]) { const d = t - c; if (d >= 0 && d < 0.35) o = Math.max(o, 0.75 * (1 - d / 0.35)); }
    this.flash.style.opacity = o;
    const on = t >= 5.7;
    this.clock.style.display = this.pause.style.display = on ? 'block' : 'none';
    if (on) {
      const k = [[5.7, 0], [6.05, 4.9], [6.95, 8.0], [7.85, 13.2], [8.75, 15.6], [9.6, 22.6], [10.4, 26.8], [11.0, 27.4]];
      let v = k[k.length - 1][1];
      for (let i = 1; i < k.length; i++) if (t < k[i][0]) { const a = k[i - 1], b = k[i]; v = a[1] + (b[1] - a[1]) * (t - a[0]) / (b[0] - a[0]); break; }
      const s = Math.floor(v);
      this.clock.textContent = '0:' + String(Math.min(28, s)).padStart(2, '0');
    }
  },
}));

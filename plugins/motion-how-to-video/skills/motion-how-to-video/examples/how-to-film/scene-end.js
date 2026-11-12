// End card: the composer pulls back under the ground; the four steps and what you need.
kit.scene('end', {
  init(kit) {
    this.k = kit;
    const R = this.R = SS.rig(kit);
    R.seq([[0, 'hw_d', 0]]);
    R.view([{ t: 0, x: 752, y: 390, z: 1.9 }, { t: 1.1, z: 1 }]);
    this.veil = kit.h('<div style="position:absolute;inset:0;background:var(--ground);opacity:0"></div>');
    kit.stage.append(this.veil);
    const steps = [
      ['Ask Claude for the film', 'real screens, one step per scene, a caption on each'],
      ['Export the MP4', 'the download arrow under the film'],
      ['Voice each caption', 'ElevenLabs Text to Speech, Matilda'],
      ['Ask Claude to mix', 'each clip under its caption, one finished MP4'],
    ];
    const w = this.w = kit.h('<div class="words" style="left:170px;top:120px;width:1580px;gap:0"></div>');
    this.eyebrow = kit.h('<p class="eyebrow" style="font-size:30px;margin:0 0 40px">That\'s the recipe</p>');
    w.append(this.eyebrow);
    this.rows = steps.map(([a, b], i) => {
      const r = kit.h('<div style="display:flex;align-items:center;gap:32px;margin:0 0 30px"><div style="width:76px;height:76px;border-radius:50%;background:var(--accent);color:var(--ground);display:flex;align-items:center;justify-content:center;font-family:var(--display, var(--sans, system-ui, sans-serif));font-weight:700;font-size:40px;flex:none">' + (i + 1) + '</div><div><div class="line" style="font-size:60px"></div><div class="sub" style="font-size:30px;margin-top:8px"></div></div></div>');
      r.querySelector('.line').textContent = a; r.querySelector('.sub').textContent = b;
      w.append(r);
      return r;
    });
    this.need = kit.h('<p class="sub" style="font-size:28px;margin:14px 0 0"></p>');
    this.need.textContent = 'You need Claude in Chrome, the OmniOrders test account and ElevenLabs.';
    w.append(this.need);
    kit.stage.append(w);
    const L = SS.LINES(kit);
    this.caps = SS.caps(kit, [[L['end'] || 'end', 1.45, 6.7]]);
  },
  render(t) {
    const kit = this.k, { seg, eo, lerp } = kit;
    this.R.render(t);
    this.veil.style.opacity = 0.93 * eo(seg(t, 0.15, 1.15));
    const fade = (el, a) => { const p = eo(seg(t, a, a + 0.45)); el.style.opacity = p; el.style.transform = 'translateX(' + lerp(26, 0, p) + 'px)'; };
    fade(this.eyebrow, 0.8);
    this.rows.forEach((r, i) => fade(r, 1.05 + i * 0.3));
    fade(this.need, 2.5);
    SS.capsRun(kit, this.caps, t);
  },
});

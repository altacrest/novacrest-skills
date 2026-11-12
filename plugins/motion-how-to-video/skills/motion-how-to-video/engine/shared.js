// Screenshot engine for Claude Motion how-to films (first built for the OmniOrders quick start films, Oct 2026).
// Copy this file into a film as modules/shared.js unchanged. Per film settings live in shots.json ("host": the
// domain the browser bar shows before paths that start with /) and in each scene's SS.def / SS.open / SS.end options.
// World = the app's CSS px (1512 x 745 viewport, captured at 2x). The browser window sits at stage
// x 96..1824, bar 96..132, view 132..983 (scale 8/7). Camera keys, cursor keys and patches are all
// authored in world px; the rig converts. Everything in render(t) is a pure function of t.
window.SS = (() => {
  const S = 8 / 7, WX = 96, WT = 96, BAR = 36, WY = WT + BAR, VW = 1512, VH = 745;
  const WIN = { L: WX, R: WX + VW * S, T: WT, B: WY + VH * S };
  const SAFE_Y = 470; // stage y a framed subject centres on, clear of the caption plate
  const P = (x, y) => [WX + x * S, WY + y * S];
  const clamp01 = (x) => Math.max(0, Math.min(1, x));
  function clampCam(cx, cy, z) {
    const hw = 960 / z, hh = 540 / z;
    cx = WIN.R - WIN.L >= 2 * hw ? Math.max(WIN.L + hw, Math.min(WIN.R - hw, cx)) : (WIN.L + WIN.R) / 2;
    cy = WIN.B - WIN.T >= 2 * hh ? Math.max(WIN.T + hh, Math.min(WIN.B - hh, cy)) : (WIN.T + WIN.B) / 2;
    return [cx, cy];
  }
  // {t, x, y, z} puts world point (x, y) at stage (960, SAFE_Y); {t, fit: [x, y, w, h]} frames a box.
  function key(k) {
    let z = k.z || 1, x = k.x, y = k.y;
    if (k.fit) {
      const [fx, fy, fw, fh] = k.fit;
      z = Math.max(1, Math.min(k.zmax || 2.1, (1920 * 0.9) / (fw * S), 780 / (fh * S)));
      x = fx + fw / 2; y = fy + fh / 2;
    }
    let cx = (WIN.L + WIN.R) / 2, cy = (WIN.T + WIN.B) / 2;
    if (x != null) { const p = P(x, y); cx = p[0]; cy = p[1] + (540 - SAFE_Y) / z; }
    [cx, cy] = clampCam(cx, cy, z);
    const out = { t: k.t, cx, cy, z };
    for (const f of ['hold', 'from', 'cut', 'ease', 'drift']) if (k[f] != null) out[f] = k[f];
    return out;
  }
  function interp(keys, t, kit) { // [[t, v], ...] eased between keys
    if (!keys || !keys.length) return 0;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const a = keys[i - 1], b = keys[i];
      if (t < b[0]) return kit.lerp(a[1], b[1], kit.eio(kit.seg(t, a[0], b[0])));
    }
    return keys[keys.length - 1][1];
  }
  const ARROW = '<svg width="40" height="40" viewBox="0 0 24 24" style="margin:-1.8px 0 0 -4.7px"><path d="M5.2 2.9v17.4l4.3-4.1 2.7 6.2 2.9-1.25-2.65-6.05h5.85z" fill="#111" stroke="#fff" stroke-width="1.35" stroke-linejoin="round"/></svg>';
  const asset = (kit, name) => kit.assets.url(/\.\w+$/.test(name) ? name : name + '.webp');

  function rig(kit, o = {}) {
    const M = kit.json('shots.json') || { shots: {}, patches: {}, strips: {} };
    kit.stage.append(kit.h('<div class="ground"></div>'));
    const camEl = kit.h('<div class="cam"></div>');
    const win = kit.h('<div class="bwin"><div class="bbar"><i style="background:#FF5F57"></i><i style="background:#FEBC2E"></i><i style="background:#28C840"></i><div class="burl"><b></b><span></span></div></div><div class="bview"><div class="world"></div></div></div>');
    camEl.append(win);
    kit.stage.append(camEl);
    const world = win.querySelector('.world'), urlEl = win.querySelector('.burl span');
    const cam = new kit.Camera(camEl);
    cam.set([key({ t: 0 })]);
    const R = {
      kit, M, camEl, cam, win, world, urlEl, t: 0, P, S,
      imgs: {}, seqList: [], strips: [], patches: [], texts: [], rings: [], cur: null, url: o.url || null, urlNow: null, extra: [],
      img(name) {
        if (!R.imgs[name]) { const im = kit.h('<img class="shot" alt="">'); im.src = asset(kit, name); world.append(im); R.imgs[name] = im; }
        return R.imgs[name];
      },
      view(keys) { cam.set(keys.map(key)); return R; },
      seq(list) { R.seqList = list.map(([t, name, fade, url]) => ({ t, name, fade: fade == null ? 0.22 : fade, url })); list.forEach((e) => R.img(e[1])); return R; },
      strip(d) {
        const info = M.strips[d.name] || { css: [1272, 1821.5], origin_css: [240, 65] };
        const box = kit.h('<div class="strip"></div>');
        const [ox, oy] = info.origin_css;
        Object.assign(box.style, { left: ox + 'px', top: oy + 'px', width: VW - ox + 'px', height: VH - oy + 'px' });
        const inner = kit.h('<div style="position:absolute;left:0;top:0"></div>');
        const im = kit.h('<img alt="">'); im.src = asset(kit, d.name);
        Object.assign(im.style, { width: info.css[0] + 'px', height: info.css[1] + 'px' });
        inner.append(im); box.append(inner); world.append(box);
        const st = Object.assign({ box, inner, ox, oy, t0: -1e9, t1: 1e9, scroll: [[0, 0]] }, d);
        st.y = (t) => interp(st.scroll, t, kit);
        st.patch = (p) => R.patch(Object.assign({ parent: inner, space: 'strip:' + d.name }, p));
        st.text = (p) => R.text(Object.assign({ parent: inner }, p));
        R.strips.push(st);
        return st;
      },
      patch(p) {
        const m = M.patches[p.name];
        if (!m) throw new Error('no patch ' + p.name);
        const el = kit.h('<img class="patch" alt="">'); el.src = asset(kit, p.name);
        const [x, y, w, h] = m.rect;
        Object.assign(el.style, { left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' });
        (p.parent || world).append(el);
        const q = Object.assign({ el, rect: m.rect, t0: 0, t1: 1e9, fade: 0.12, fout: 0 }, p);
        if (q.caret) { q.caretEl = kit.h('<div class="tcaret"></div>'); (p.parent || world).append(q.caretEl); }
        R.patches.push(q);
        return q;
      },
      text(p) { // overlay html at world (or strip) coords
        const el = kit.h('<div class="ovl2">' + p.html + '</div>');
        Object.assign(el.style, { left: p.x + 'px', top: p.y + 'px' }, p.style || {});
        (p.parent || world).append(el);
        const q = Object.assign({ el, t0: 0, t1: 1e9, fade: 0.12 }, p);
        R.texts.push(q);
        return q;
      },
      ring(p) {
        const el = kit.h('<div class="ring"></div>');
        const [x, y, w, h] = p.r, pad = p.pad == null ? 6 : p.pad;
        Object.assign(el.style, { left: x - pad + 'px', top: y - pad + 'px', width: w + 2 * pad + 'px', height: h + 2 * pad + 'px' });
        (p.parent || world).append(el);
        const q = Object.assign({ el, t0: 0, t1: 1e9 }, p);
        R.rings.push(q);
        return q;
      },
      // stage point of a world point under the current camera
      sp(x, y) { const [X, Y] = P(x, y); const s = cam.state || { cx: 960, cy: 540, z: 1 }; return [960 + (X - s.cx) * s.z, 540 + (Y - s.cy) * s.z]; },
      cursor(keys, clicks, extra) {
        const cur = kit.cursor();
        cur.keys = keys.map(([t, x, y, opt]) => {
          const st = opt && opt.strip;
          const at = st ? () => R.sp(st.ox + x, st.oy + y - st.y(R.t)) : () => R.sp(x, y);
          return Object.assign({ t, at }, opt && opt.bow != null ? { bow: opt.bow } : {});
        });
        cur.clicks = clicks || [];
        cur.shapes = [{ spans: [[-1e9, 1e9]], gfx: ARROW }];
        if (extra) Object.assign(cur, extra);
        R.cur = cur;
        return cur;
      },
      render(t) {
        R.t = t;
        cam.apply(t);
        // shots
        const L = R.seqList;
        if (L.length) {
          let k = 0;
          for (let i = 0; i < L.length; i++) if (t >= L[i].t) k = i;
          const cur = L[k], prev = k > 0 ? L[k - 1] : null;
          const p = cur.fade > 0 && prev ? kit.eo(kit.seg(t, cur.t, cur.t + cur.fade)) : 1;
          for (const n in R.imgs) { const im = R.imgs[n]; if (n !== cur.name && !(prev && p < 1 && n === prev.name)) im.style.display = 'none'; }
          if (prev && p < 1 && prev.name !== cur.name) { const a = R.imgs[prev.name]; a.style.display = 'block'; a.style.opacity = 1; a.style.zIndex = 1; }
          const b = R.imgs[cur.name]; b.style.display = 'block'; b.style.opacity = prev && prev.name !== cur.name ? p : 1; b.style.zIndex = 2;
          const path = cur.url || (R.M.shots[cur.name] && R.M.shots[cur.name].path) || '';
          const u = R.url || (path.indexOf('/') === 0 ? (R.M.host != null ? R.M.host : 'app.omniorders.com') + path : path);
          if (u !== R.urlNow) { R.urlEl.textContent = u; R.urlNow = u; }
        } else if (R.url && R.urlNow !== R.url) { R.urlEl.textContent = R.url; R.urlNow = R.url; }
        // strips
        for (const st of R.strips) {
          const on = t >= st.t0 && t < st.t1;
          st.box.style.display = on ? 'block' : 'none';
          if (on) { st.inner.style.transform = 'translateY(' + -st.y(t) + 'px)'; st.box.style.opacity = st.fade ? kit.eo(kit.seg(t, st.t0, st.t0 + st.fade)) : 1; }
        }
        // patches
        for (const q of R.patches) {
          const on = t >= q.t0 && t < q.t1;
          if (!on) { q.el.style.display = 'none'; if (q.caretEl) q.caretEl.style.display = 'none'; continue; }
          let op = q.fade > 0 ? kit.eo(kit.seg(t, q.t0, q.t0 + q.fade)) : 1;
          if (q.fout > 0 && q.t1 < 1e8) op *= 1 - kit.seg(t, q.t1 - q.fout, q.t1);
          q.el.style.display = 'block'; q.el.style.opacity = op;
          const [rx, ry, rw, rh] = q.rect;
          const [sx, sy, sw, sh] = q.sub || q.rect;
          let right = sx + sw;
          if (q.type) {
            const [x0, x1] = q.tx || [sx, sx + sw];
            const n = q.chars || Math.max(4, Math.round((x1 - x0) / 7.5));
            const r = Math.floor(clamp01((t - q.type[0]) / (q.type[1] - q.type[0])) * n) / n;
            right = Math.min(sx + sw, x0 + (x1 - x0) * r);
            if (q.caretEl) {
              const show = t < q.type[1] + 0.05 || Math.floor((t - q.type[1]) / 0.53) % 2 === 1;
              const [cy0, ch] = q.caret;
              Object.assign(q.caretEl.style, { display: show && t < (q.caretOff || q.type[1] + 0.8) ? 'block' : 'none', left: right + 0.5 + 'px', top: cy0 + 'px', height: ch + 'px' });
            }
          }
          q.el.style.clipPath = q.sub || q.type ? 'inset(' + (sy - ry) + 'px ' + Math.max(0, rx + rw - right) + 'px ' + (ry + rh - sy - sh) + 'px ' + (sx - rx) + 'px)' : 'none';
        }
        for (const q of R.texts) {
          const on = t >= q.t0 && t < q.t1;
          q.el.style.display = on ? 'block' : 'none';
          if (on) q.el.style.opacity = q.fade > 0 ? kit.eo(kit.seg(t, q.t0, q.t0 + q.fade)) : 1;
        }
        for (const q of R.rings) {
          const on = t >= q.t0 && t < q.t1;
          q.el.style.display = on ? 'block' : 'none';
          if (on) {
            const a = kit.eo(kit.seg(t, q.t0, q.t0 + 0.3)) * (1 - kit.seg(t, q.t1 - 0.3, q.t1));
            q.el.style.opacity = a; q.el.style.transform = 'scale(' + kit.lerp(1.06, 1, kit.eo(kit.seg(t, q.t0, q.t0 + 0.35))) + ')';
          }
        }
        for (const f of R.extra) f(t);
        if (R.cur) R.cur.render(t);
      },
    };
    return R;
  }

  // captions: [[text, tin, tout], ...]
  function caps(kit, list) {
    return list.map(([text, tin, tout]) => { const el = kit.h('<p class="cap"></p>'); el.textContent = text; kit.stage.append(el); return { el, tin, tout }; });
  }
  function capsRun(kit, list, t) {
    for (const c of list) {
      const { el, tin, tout } = c;
      if (t < tin - 0.2 || (tout != null && t > tout + 0.45)) { el.style.opacity = 0; continue; }
      if (tout == null || t < tout) kit.TextFx.fadeFromRight(el, t, tin); else kit.TextFx.fadeOutLeft(el, t, tout);
      let p = kit.eo(kit.seg(t, tin - 0.15, tin + 0.2));
      if (tout != null) p *= 1 - kit.ei(kit.seg(t, tout + 0.15, tout + 0.4));
      el.style.opacity = p;
    }
  }
  const LINES = (kit) => kit.json('lines.json') || {};

  // A declarative scene: {cam, seq, strips, patches, texts, rings, cur, clicks, caps, url, build(R), tick(R, t)}
  function def(spec) {
    return {
      init(kit) {
        this.k = kit;
        const R = this.R = rig(kit, { url: spec.url });
        if (spec.seq) R.seq(spec.seq);
        const strips = {};
        for (const d of spec.strips || []) { const st = strips[d.name] = R.strip(d); for (const p of d.patches || []) st.patch(p); for (const x of d.texts || []) st.text(x); }
        for (const p of spec.patches || []) R.patch(p);
        for (const x of spec.texts || []) R.text(x);
        for (const r of spec.rings || []) R.ring(r);
        R.view(spec.cam || [{ t: 0 }]);
        if (spec.build) spec.build.call(this, R, kit, strips);
        if (spec.cur) R.cursor(spec.cur.map((k) => (k[3] && typeof k[3].strip === 'string' ? [k[0], k[1], k[2], Object.assign({}, k[3], { strip: strips[k[3].strip] })] : k)), spec.clicks || [], spec.curExtra);
        const L = LINES(kit);
        this.caps = caps(kit, (spec.caps || []).map(([id, a, b]) => [L[id] || id, a, b]));
      },
      render(t) {
        this.R.render(t);
        if (spec.tick) spec.tick.call(this, this.R, t, this.k);
        capsRun(this.k, this.caps, t);
      },
    };
  }

  function open(o) {
    return {
      init(kit) {
        this.k = kit;
        const R = this.R = rig(kit);
        R.seq([[0, o.shot, 0]]);
        this.veil = kit.h('<div style="position:absolute;inset:0;background:var(--ground)"></div>');
        kit.stage.append(this.veil);
        const words = this.words = kit.h('<div class="words" style="left:150px;top:300px;width:1600px"><p class="eyebrow" style="font-size:30px"></p><h2 class="line" style="font-size:150px"></h2><p class="sub" style="font-size:42px"></p></div>');
        words.children[0].textContent = o.eyebrow; words.children[1].textContent = o.title; words.children[2].textContent = o.sub;
        kit.stage.append(words);
      },
      render(t) {
        const kit = this.k, { seg, eo, eio, lerp } = kit, D = o.dur || 3, R = this.R;
        R.render(t);
        const p = eio(seg(t, 0.2, D)), s = lerp(0.84, 1, p), dy = lerp(150, 0, p);
        R.camEl.style.transform = 'translate(' + (960 - 960 * s) + 'px,' + (540 - 540 * s + dy) + 'px) scale(' + s + ')';
        this.veil.style.opacity = lerp(0.9, 0, eio(seg(t, D - 0.65, D)));
        const [eyebrow, line, sub] = this.words.children;
        const e = eo(seg(t, -0.3, 0.3));
        eyebrow.style.opacity = e; eyebrow.style.transform = 'translateX(' + lerp(26, 0, e) + 'px)';
        kit.TextFx.fadeFromRight(line, t, -0.5);
        const b = eo(seg(t, 0.7, 1.2));
        sub.style.opacity = b; sub.style.transform = 'translateX(' + lerp(26, 0, b) + 'px)';
        const out = eo(seg(t, D - 1.0, D - 0.55));
        this.words.style.opacity = 1 - out; this.words.style.transform = 'translateY(' + -36 * out + 'px)';
      },
    };
  }

  function end(o) {
    return {
      init(kit) {
        this.k = kit;
        const R = this.R = rig(kit);
        R.seq([[0, o.shot, 0]]);
        if (o.build) o.build(R, kit);
        const words = this.words = kit.h('<div class="words" style="left:0;right:0;top:360px;align-items:center;text-align:center;gap:26px"><h2 class="line" style="font-size:150px;letter-spacing:-.02em"></h2><p class="sub" style="font-size:46px;color:var(--second)"></p><p class="sub" style="font-size:28px"></p></div>');
        words.children[0].textContent = o.mark || 'omniorders'; words.children[1].textContent = o.next; words.children[2].textContent = o.url || 'omniorders.com/quick-start';
        kit.stage.append(words);
        this.dot = kit.h('<div style="position:absolute;left:960px;top:540px;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;background:var(--accent)"></div>');
        kit.stage.append(this.dot);
        this.mr = kit.srect(words.children[0]);
      },
      render(t) {
        const kit = this.k, { seg, eo, eio, eob, lerp } = kit, R = this.R;
        R.render(t);
        const p = eio(seg(t, 0, 0.95)), z0 = o.z0 || 2;
        const z = Math.exp(lerp(Math.log(z0), Math.log(0.1), p));
        const [fx, fy] = P(o.focus[0], o.focus[1]);
        const cx = lerp(fx, 960, p), cy = lerp(fy, 540, p);
        R.camEl.style.transform = 'translate(' + (960 - cx * z) + 'px,' + (540 - cy * z) + 'px) scale(' + z + ')';
        R.win.style.opacity = 1 - eo(seg(t, 0.5, 0.9));
        const [mark, next, url] = this.words.children;
        const dx = this.mr.x + this.mr.w + 16, dy = this.mr.y + this.mr.h - 30;
        const d = eob(seg(t, 0.75, 1.15), 1.6), mm = eio(seg(t, 1.05, 1.6));
        this.dot.style.transform = 'scale(' + d + ')';
        this.dot.style.left = lerp(960, dx, mm) + 'px';
        this.dot.style.top = lerp(540, dy, mm) + 'px';
        this.dot.style.opacity = t > 0.75 ? 1 : 0;
        kit.TextFx.fadeFromRight(mark, t, 1.0);
        const n = eo(seg(t, 1.6, 2.1)), u = eo(seg(t, 2.1, 2.6));
        next.style.opacity = n; next.style.transform = 'translateX(' + lerp(26, 0, n) + 'px)';
        url.style.opacity = u; url.style.transform = 'translateX(' + lerp(26, 0, u) + 'px)';
      },
    };
  }

  return { S, P, key, rig, def, open, end, caps, capsRun, interp, LINES };
})();

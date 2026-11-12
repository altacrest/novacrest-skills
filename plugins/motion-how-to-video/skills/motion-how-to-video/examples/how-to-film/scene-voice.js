// ElevenLabs: the voice picker searched for Matilda; then Text to Speech with Matilda chosen, one caption
// pasted (its text and the counter bar were covered until the paste), Generate speech.
kit.scene('voice', SS.def({
  seq: [[0, 'hw_pick'], [4.1, 'hw_tts', 0.25]],
  texts: [
    { html: '<div style="width:330px;height:32px;background:#fff"></div>', x: 298, y: 178, t0: 4.1, t1: 6.7, fade: 0.25, style: { zIndex: 4 } },
    { html: '<div style="width:452px;height:48px;background:#fff"></div>', x: 520, y: 655, t0: 4.1, t1: 6.7, fade: 0.25, style: { zIndex: 4 } },
  ],
  rings: [{ r: [494, 136, 846, 44], t0: 1.6, t1: 3.8, pad: 4 }, { r: [825.5, 661, 138.5, 36], t0: 8.2, t1: 10.5, pad: 5 }],
  cam: [{ t: 0, x: 917, y: 160, z: 1.75, hold: 4.1 }, { t: 4.1, x: 1265, y: 219, z: 1.75, cut: true, hold: 1.1 }, { t: 6.1, x: 640, y: 300, z: 1.35, hold: 1.3 }, { t: 8.3, z: 1 }],
  cur: [[0, 760, 420], [0.6, 760, 420], [2.4, 690, 158], [4.1, 690, 158], [5.4, 690, 158], [6.35, 470, 194], [6.9, 470, 194], [8.5, 895, 679], [10.0, 895, 679], [11.2, 1010, 560], [15, 1010, 560]],
  clicks: [3.0, 6.5, 8.95],
  caps: [['voice-a', 0.3, 4.95], ['voice-b', 5.3, 10.25], ['voice-c', 10.6, 14.6]],
}));

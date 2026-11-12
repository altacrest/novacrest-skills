#!/usr/bin/env python3
"""voice.py: English narration for a Claude Motion how-to film, made with ElevenLabs.

One MP3 per caption in lines.json, read by Matilda unless you pick another voice.
Run it in your own Terminal, inside the film folder Claude made (the one holding lines.json):

  python3 voice.py setup              save your ElevenLabs API key, first time only (typing is hidden)
  python3 voice.py check              the key works, and the credits left
  python3 voice.py                    make every clip that isn't made yet
  python3 voice.py --only open,ask-a  just these lines (a pilot, or a fix)
  python3 voice.py --only ask-a --redo    make a line again

Options: --voice NAME_OR_ID (default Matilda), --speed 0.7 to 1.2 (default 1.0), --stability (default 0.5),
--lines FILE (default lines.json), --say FILE (default say.json), --out DIR (default voice),
--env FILE (a file holding ELEVENLABS_API_KEY=...), --no-check (skip the Whisper check).

Writes voice/<id>.mp3 and voice/voice.json: each clip's length and, when faster-whisper is installed,
what Whisper heard and the word error rate. say.json (optional) holds a spoken respelling for a line
whose caption the voice says wrong ({"id": "Omni Orders ..."}); the caption itself stays as written.

The key is read from ELEVENLABS_API_KEY, --env, ./.env or ~/.config/elevenlabs/env and is never printed.
Needs Python 3.9 or later and nothing else (curl, which every Mac has, is used if Python's SSL fails).
Endpoints (ElevenLabs API reference, Nov 2026): POST /v1/text-to-speech/{voice_id}, GET /v1/user,
GET /v1/user/subscription, GET /v2/voices. Header xi-api-key.
"""
import argparse
import getpass
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io"
KEY_FILE = Path.home() / ".config" / "elevenlabs" / "env"
MODEL = "eleven_multilingual_v2"        # the model the Oct 2026 OmniOrders films used; reads English text in English
FORMAT = "mp3_44100_128"
SEED = 1112
WER_LIMIT = 0.05
VOICES = {  # ElevenLabs default voices; any other voice in the account works by name or id
    "matilda": "XrExE9yKIg1WjnnlVkGX", "alice": "Xb7hH8MSUJpSbSDYk0k2", "brian": "nPczCjzI2devNBz1zQrb",
    "eric": "cjVigY5qzO86Huf0OWal", "sarah": "EXAVITQu4vr4xnSDxMaL", "will": "bIHbv24MWmeRgasZH58o",
}


def stop(msg):
    sys.exit("STOP: " + msg)


# ---------------- the key ----------------
def find_key(env_file=None):
    if os.environ.get("ELEVENLABS_API_KEY", "").strip():
        return os.environ["ELEVENLABS_API_KEY"].strip(), "the environment"
    files = [Path(env_file).expanduser()] if env_file else []
    files += [Path(".env"), KEY_FILE, Path.home() / ".elevenlabs.env"]
    for f in files:
        try:
            text = f.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            m = re.match(r"\s*(?:export\s+)?ELEVENLABS_API_KEY\s*=\s*(.*)$", line)
            if m and m.group(1).strip().strip("'\""):
                return m.group(1).strip().strip("'\""), str(f)
    return None, None


def need_key(a):
    key, where = find_key(a.env)
    if not key:
        stop("no ElevenLabs key yet. Run: python3 voice.py setup")
    return key, where


# ---------------- HTTP (urllib, or curl when Python's SSL certificates are missing) ----------------
class _CertProblem(Exception):
    pass


def _urllib(method, url, headers, data, timeout):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read()
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError) or "CERTIFICATE" in str(e.reason).upper():
            raise _CertProblem()
        raise


def _curl(method, url, headers, data, timeout):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "body"
        cmd = ["curl", "-sS", "-X", method, url, "-H", "@-", "-o", str(out), "--max-time", str(timeout),
               "-w", "%{http_code} %{content_type}"]
        if data is not None:
            (Path(td) / "data").write_bytes(data)
            cmd += ["--data-binary", "@" + str(Path(td) / "data")]
        hdr = "".join("%s: %s\n" % kv for kv in headers.items())   # the key goes through stdin, not the command line
        p = subprocess.run(cmd, input=hdr.encode(), capture_output=True)
        if p.returncode != 0:
            stop("couldn't reach ElevenLabs (curl: %s)" % p.stderr.decode(errors="replace").strip()[:200])
        code, _, ctype = p.stdout.decode().partition(" ")
        return int(code or 0), ctype, out.read_bytes() if out.exists() else b""


def request(method, path, key, params=None, body=None, accept="application/json", timeout=180):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    headers = {"xi-api-key": key, "Accept": accept}
    if data is not None:
        headers["Content-Type"] = "application/json"
    status, ctype, content = 0, "", b""
    for wait in (0, 5, 15, 45):
        if wait:
            time.sleep(wait)
        try:
            status, ctype, content = _urllib(method, url, headers, data, timeout)
        except _CertProblem:
            status, ctype, content = _curl(method, url, headers, data, timeout)
        except urllib.error.URLError as e:
            stop("couldn't reach ElevenLabs (%s). Run this in your own Terminal, not in Claude." % e.reason)
        if status in (429, 500, 502, 503, 504):
            print("  ElevenLabs is busy (%d), trying again shortly..." % status)
            continue
        break
    return status, ctype, content


def why(status, content):
    text = content.decode("utf-8", errors="replace")[:400]
    if "invalid_api_key" in text:
        return "the key was refused. Make a new one and run: python3 voice.py setup"
    if "missing_permissions" in text:
        return "the key doesn't have this permission (%s)" % text
    if "quota" in text.lower() or "credits" in text.lower():
        return "the ElevenLabs account is out of credits (%s)" % text
    return "ElevenLabs answered %d: %s" % (status, text)


# ---------------- audio length (MP3 frames, no ffmpeg needed) ----------------
_BR1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
_BR2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
_SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_seconds(path):
    b = Path(path).read_bytes()
    i = 0
    if b[:3] == b"ID3" and len(b) > 10:
        size = (b[6] << 21) | (b[7] << 14) | (b[8] << 7) | b[9]
        i = 10 + size + (10 if b[5] & 0x10 else 0)
    total = 0.0
    while i + 4 <= len(b):
        h = int.from_bytes(b[i:i + 4], "big")
        ver, layer, bri, sri, pad = (h >> 19) & 3, (h >> 17) & 3, (h >> 12) & 15, (h >> 10) & 3, (h >> 9) & 1
        if (h >> 21) & 0x7FF != 0x7FF or ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
            i += 1
            continue
        sr = _SR[ver][sri]
        if ver == 3:
            size, samples = 144 * _BR1[bri] * 1000 // sr + pad, 1152
        else:
            size, samples = 72 * _BR2[bri] * 1000 // sr + pad, 576
        total += samples / sr
        i += size
    return round(total, 3)


# ---------------- Whisper check (only when faster-whisper is installed) ----------------
def whisper():
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return None
    try:
        return WhisperModel("small", device="cpu", compute_type="int8")
    except Exception as e:
        print("  (Whisper didn't load: %s. Listen to the clips instead.)" % e)
        return None


def heard(model, path):
    segs, _ = model.transcribe(str(path), language="en", beam_size=5)
    return " ".join(s.text.strip() for s in segs).strip()


_NUM = dict(zip([str(i) for i in range(21)], "zero one two three four five six seven eight nine ten eleven twelve "
                "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()))


def words(t):
    """lower-case words, numbers 0-20 spelled out (Whisper writes "11 Labs" for ElevenLabs)"""
    t = t.lower().replace("’", "'").replace("-", " ")
    return [_NUM.get(w, w) for w in re.sub(r"[^a-z0-9' ]+", " ", t).split()]


def cer(ref, hyp):
    """character error rate with spaces dropped, so "NovaCrest" and "Novacrest", or "11 Labs" and "ElevenLabs", match"""
    a, b = "".join(words(ref)).replace("'", ""), "".join(words(hyp)).replace("'", "")
    if not a:
        return 0.0 if not b else 1.0
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(b)] / len(a)


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    if not r:
        return 0.0 if not h else 1.0
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / len(r)


# ---------------- commands ----------------
def cmd_setup(a):
    print("Paste your ElevenLabs API key and press Enter. Typing is hidden.")
    key = getpass.getpass("Key: ").strip()
    if not key:
        stop("no key entered")
    status, _, content = request("GET", "/v1/user", key)
    if status in (401, 403) and b"invalid_api_key" in content:
        stop("ElevenLabs refused that key. Copy it again (or make a new one) and run setup again.")
    if status not in (200, 401, 403):
        stop(why(status, content))
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("ELEVENLABS_API_KEY=%s\n" % key)
    os.chmod(str(KEY_FILE), 0o600)
    print("Saved in %s (only you can read it). Next: python3 voice.py check" % KEY_FILE)


def cmd_check(a):
    key, where = need_key(a)
    print("key: found in %s" % where)
    status, _, content = request("GET", "/v1/user/subscription", key)
    if status == 200:
        s = json.loads(content)
        left = (s.get("character_limit") or 0) - (s.get("character_count") or 0)
        print("plan: %s | credits used %s of %s, %s left" % (s.get("tier"), s.get("character_count"),
                                                           s.get("character_limit"), left))
    else:
        print("plan: this key can't read the plan (fine if it has Text to Speech access)")
    vid, name = voice_id(a.voice, key, quiet=True)
    print("voice: %s (%s)" % (name, vid))
    lines_path = Path(a.lines)
    if lines_path.exists():
        lines, say = load_lines(a)
        n = sum(len(say.get(k, v)) for k, v in lines.items())
        print("lines.json: %d lines, %d characters (about %d credits with %s)" % (len(lines), n, n, MODEL))


def voice_id(arg, key, quiet=False):
    if arg.lower() in VOICES:
        return VOICES[arg.lower()], arg.capitalize()
    if re.fullmatch(r"[A-Za-z0-9]{20}", arg):
        return arg, arg
    status, _, content = request("GET", "/v2/voices", key, params={"search": arg, "page_size": 100})
    if status != 200:
        stop("looking up the voice %r: %s" % (arg, why(status, content)))
    hits = [v for v in json.loads(content).get("voices", []) if v.get("name", "").lower() == arg.lower()]
    if not hits:
        stop("no voice named %r in this account" % arg)
    return hits[0]["voice_id"], hits[0]["name"]


def load_json(path):
    d = json.loads(Path(path).read_text())
    if isinstance(d, dict) and set(d) >= {"kind", "text"}:   # a Motion store document
        d = json.loads(d["text"])
    return d


def load_lines(a):
    if not Path(a.lines).exists():
        stop("no %s here. cd into the film folder Claude made, then run this again." % a.lines)
    lines = load_json(a.lines)
    if not isinstance(lines, dict) or not all(isinstance(v, str) for v in lines.values()):
        stop("%s should look like {\"id\": \"caption\", ...}" % a.lines)
    say = load_json(a.say) if Path(a.say).exists() else {}
    for k in say:
        if k not in lines:
            stop("%s has %r, which isn't in %s" % (a.say, k, a.lines))
    return lines, say


def cmd_make(a):
    lines, say = load_lines(a)
    order = list(lines)
    ids = order
    if a.only:
        ids = [x.strip() for x in a.only.split(",") if x.strip()]
        bad = [x for x in ids if x not in lines]
        if bad:
            stop("not in %s: %s" % (a.lines, ", ".join(bad)))
    if not 0.7 <= a.speed <= 1.2:
        stop("--speed must be between 0.7 and 1.2")
    key, _ = need_key(a)
    vid, vname = voice_id(a.voice, key)
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    rec_path = out / "voice.json"
    rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
    settings = {"stability": a.stability, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True,
                "speed": a.speed}
    rec.update({"voice": vname, "voice_id": vid, "model": MODEL, "settings": settings, "language": "en"})
    rec.setdefault("lines", {})
    todo = [i for i in ids if a.redo or not (out / (i + ".mp3")).exists()]
    chars = sum(len(say.get(i, lines[i])) for i in todo)
    print("Voice %s, %s, speed %g. %d of %d lines to make, %d characters (about %d credits)."
          % (vname, MODEL, a.speed, len(todo), len(ids), chars, chars))
    model = None if a.no_check else whisper()
    if model is None and not a.no_check:
        print("(faster-whisper isn't installed, so no word check: listen to the clips.)")
    for lid in ids:
        dest = out / (lid + ".mp3")
        sent = say.get(lid, lines[lid])
        if lid in todo:
            k = order.index(lid)
            body = {"text": sent, "model_id": MODEL, "voice_settings": settings, "seed": SEED + k}
            if k > 0:
                body["previous_text"] = say.get(order[k - 1], lines[order[k - 1]])
            if k + 1 < len(order):
                body["next_text"] = say.get(order[k + 1], lines[order[k + 1]])
            status, ctype, content = request("POST", "/v1/text-to-speech/" + vid, key,
                                             params={"output_format": FORMAT}, body=body, accept="audio/mpeg")
            if status != 200:
                stop("%s: %s" % (lid, why(status, content)))
            if "json" in ctype or "text" in ctype:
                stop("%s: ElevenLabs sent text instead of audio: %s" % (lid, content[:300]))
            part = dest.with_name(dest.stem + ".part.mp3")
            part.write_bytes(content)
            part.replace(dest)
        row = {"text": lines[lid], "sent": sent, "seconds": mp3_seconds(dest)}
        if model:
            h = heard(model, dest)
            row.update(heard=h, wer=round(wer(sent, h), 3), cer=round(cer(sent, h), 3))
            row["flag"] = row["wer"] > WER_LIMIT and row["cer"] > 0.02   # both: a misreading, not a spelling
        rec["lines"][lid] = row
        rec_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
        note = ""
        if "wer" in row:
            note = "  heard ok" if not row["flag"] else "  LISTEN: heard \"%s\"" % row["heard"]
        print("%-12s %5.2fs%s%s" % (lid, row["seconds"], "" if lid in todo else "  (already made)", note))
    flagged = [k for k in ids if rec["lines"].get(k, {}).get("flag")]
    if flagged:
        print("\nListen to: %s. Then tell Claude what sounds wrong." % ", ".join(flagged))
    print("\nDone: %d clips in %s/. Tell Claude the voice is ready." % (len(ids), out))


def main():
    ap = argparse.ArgumentParser(description="English narration for a Claude Motion how-to film (ElevenLabs).")
    ap.add_argument("command", nargs="?", default="make", choices=["make", "setup", "check"])
    ap.add_argument("--lines", default="lines.json")
    ap.add_argument("--say", default="say.json")
    ap.add_argument("--out", default="voice")
    ap.add_argument("--only", help="comma-separated line ids")
    ap.add_argument("--redo", action="store_true", help="make the clips again even if they exist")
    ap.add_argument("--voice", default="Matilda")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--env", help="a file holding ELEVENLABS_API_KEY=...")
    ap.add_argument("--no-check", action="store_true", help="skip the Whisper word check")
    a = ap.parse_args()
    {"make": cmd_make, "setup": cmd_setup, "check": cmd_check}[a.command](a)


if __name__ == "__main__":
    main()

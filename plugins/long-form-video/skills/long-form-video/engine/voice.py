#!/usr/bin/env python3
"""voice.py: the narration for a long-form video, made with ElevenLabs. Runs in your own Terminal.

Claude puts this file in the video folder (next to manifest.json). Then, in Terminal:

  cd ~/Downloads/<video folder>
  python3 voice.py setup                 save your ElevenLabs API key, first time only (typing is hidden)
  python3 voice.py check                 the key works, the credits left, and what this video needs
  python3 voice.py --only open-01,open-02,seg-001     a pilot: just these segments
  python3 voice.py                       every segment not voiced yet (safe to run again)
  python3 voice.py --only seg-007 --redo     voice one segment again

The narrator (voice, model, settings) comes from manifest.json, which comes from the brand pack. Each segment is
read with the segments before and after it as context, so the reading flows. Every take comes back with its word
times (ElevenLabs' timestamps endpoint), which the edit uses for captions and cards. When faster-whisper is installed
(pip3 install faster-whisper), every take is also checked by Whisper's word error rate, and a take that misreads is
made again, up to --takes times, keeping the best. No model judges the voice.

Writes voice/<segment id>.mp3 and voice/report.json. say.json (optional) holds spoken respellings
({"seg-004": "the text as it should be said"}); the captions keep the script's spelling.

The key is read from ELEVENLABS_API_KEY, --env, ./.env or ~/.config/elevenlabs/env and is never printed.
Needs Python 3.9+ and nothing else (curl, which every Mac has, is used if Python's SSL certificates fail).
Endpoints (ElevenLabs API, Nov 2026): POST /v1/text-to-speech/{voice_id}/with-timestamps, GET /v1/user,
GET /v1/user/subscription. Header xi-api-key.
"""
import argparse
import base64
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
FORMAT = "mp3_44100_128"
WER_LIMIT, CER_LIMIT = 0.08, 0.03


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


def request(method, path, key, params=None, body=None, timeout=300):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    headers = {"xi-api-key": key, "Accept": "application/json"}
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
    if "voice_not_found" in text or ("voice" in text.lower() and status == 404):
        return ("the narrator voice isn't in this ElevenLabs account. In ElevenLabs open Voices, then Voice Library, "
                "find the voice named in manifest.json (narrator) and add it to My Voices. Then run this again.")
    if "missing_permissions" in text:
        return "the key doesn't have this permission (%s)" % text
    if "free" in text.lower() and any(w in text.lower() for w in ("library", "upgrade", "subscription")):
        return ("the narrator is a Voice Library voice, and ElevenLabs doesn't let free accounts use those through the API. "
                "Use a key from an account on a paid plan (%s)" % text)
    if "quota" in text.lower() or "credits" in text.lower():
        return "the ElevenLabs account is out of credits (%s)" % text
    return "ElevenLabs answered %d: %s" % (status, text)


def credits_left(key):
    status, _, content = request("GET", "/v1/user/subscription", key)
    if status != 200:
        return None, None
    s = json.loads(content)
    return (s.get("character_limit") or 0) - (s.get("character_count") or 0), s.get("tier")


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


# ---------------- word times from the character alignment ----------------
def word_times(al):
    """ElevenLabs' character alignment -> [{"w", "s", "e"}], one per word as it was spoken"""
    chars = al.get("characters") or []
    st = al.get("character_start_times_seconds") or []
    en = al.get("character_end_times_seconds") or []
    out, cur, s0, e0 = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur.strip():
                out.append({"w": cur, "s": round(s0, 3), "e": round(e0, 3)})
            cur, s0, e0 = "", None, None
            continue
        if s0 is None:
            s0 = s
        cur += c
        e0 = e
    if cur.strip():
        out.append({"w": cur, "s": round(s0, 3), "e": round(e0, 3)})
    return out


# ---------------- Whisper check (only when faster-whisper is installed) ----------------
def whisper():
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return None
    try:
        return WhisperModel("small", device="cpu", compute_type="int8")
    except Exception as e:
        print("  (Whisper didn't load: %s. Listen to the takes instead.)" % e)
        return None


def heard(model, path):
    segs, _ = model.transcribe(str(path), language="en", beam_size=5)
    return " ".join(s.text.strip() for s in segs).strip()


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def say_number(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + say_number(n % 100))
    return str(n)


def words(t):
    """lower-case words with numbers under 1,000 spelled out (Whisper writes "29" where the script says
    "twenty-nine"), so a spelling difference isn't counted as a misreading"""
    t = t.lower().replace("’", "'").replace("-", " ").replace(",", "")
    t = re.sub(r"\$(\d+)", r"\1 dollars", t)
    t = re.sub(r"(\d+)%", r"\1 percent", t)
    out = []
    for w in re.sub(r"[^a-z0-9' ]+", " ", t).split():
        out += say_number(int(w)).split() if w.isdigit() and int(w) < 1000 else [w]
    return out


def _dist(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(b)]


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    return (_dist(r, h) / len(r)) if r else (0.0 if not h else 1.0)


def cer(ref, hyp):
    a, b = "".join(words(ref)).replace("'", ""), "".join(words(hyp)).replace("'", "")
    return (_dist(a, b) / len(a)) if a else (0.0 if not b else 1.0)


# ---------------- the video ----------------
def load(a):
    if not Path(a.manifest).exists():
        stop("no %s here. cd into the video folder Claude made, then run this again." % a.manifest)
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    segs = man["segments"]
    say = json.loads(Path(a.say).read_text(encoding="utf-8")) if Path(a.say).exists() else {}
    ids = [s["id"] for s in segs]
    for k in say:
        if k not in ids:
            stop("%s has %r, which isn't a segment in %s" % (a.say, k, a.manifest))
    return man, segs, say


def spoken(s, say):
    return say.get(s["id"], s["narration"])


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
    left, tier = credits_left(key)
    if left is None:
        print("plan: this key can't read the plan (fine if it has Text to Speech access; give it User: Read to see credits)")
    else:
        print("plan: %s, %s credits left" % (tier, format(left, ",")))
    if Path(a.manifest).exists():
        man, segs, say = load(a)
        n = man["meta"]["narrator"]
        out = Path(a.out)
        todo = [s for s in segs if not (out / (s["id"] + ".mp3")).exists()]
        need = sum(len(spoken(s, say)) for s in todo)
        print("narrator: %s (%s), %s" % (n.get("voice"), n.get("voice_id"), n.get("model")))
        print("this video: %d segments, %d still to voice, about %s credits" % (len(segs), len(todo), format(need, ",")))
        if left is not None and need > left:
            print("NOT ENOUGH CREDITS for the whole video: voice a pilot with --only, or wait for the monthly reset.")


def make_take(key, s, segs, say, narr, k, seed):
    body = {"text": spoken(s, say), "model_id": narr.get("model", "eleven_multilingual_v2"),
            "voice_settings": narr.get("settings", {}), "seed": seed}
    if k > 0:
        body["previous_text"] = spoken(segs[k - 1], say)[-1000:]
    if k + 1 < len(segs):
        body["next_text"] = spoken(segs[k + 1], say)[:1000]
    status, ctype, content = request("POST", "/v1/text-to-speech/%s/with-timestamps" % narr["voice_id"], key,
                                     params={"output_format": FORMAT}, body=body)
    if status != 200:
        stop("%s: %s" % (s["id"], why(status, content)))
    try:
        js = json.loads(content)
        audio = base64.b64decode(js["audio_base64"])
    except Exception:
        stop("%s: ElevenLabs sent something other than audio with timestamps: %r" % (s["id"], content[:200]))
    return audio, word_times(js.get("alignment") or js.get("normalized_alignment") or {})


def cmd_make(a):
    man, segs, say = load(a)
    narr = man["meta"].get("narrator") or {}
    if not narr.get("voice_id"):
        stop("manifest.json names no narrator voice_id (brand.json, narrator)")
    ids = [s["id"] for s in segs]
    want = ids
    if a.only:
        want = [x.strip() for x in a.only.split(",") if x.strip()]
        bad = [x for x in want if x not in ids]
        if bad:
            stop("not in %s: %s" % (a.manifest, ", ".join(bad)))
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    rep_path = out / "report.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    if rep.get("voice_id") and rep["voice_id"] != narr["voice_id"] and not a.redo:
        stop("voice/ was made with another voice (%s). One video has one voice: use --redo to start over." % rep.get("voice"))
    rep.update({"voice": narr.get("voice"), "voice_id": narr["voice_id"], "model": narr.get("model"),
                "settings": narr.get("settings"), "format": FORMAT})
    rep.setdefault("segments", {})
    todo = [i for i in want if a.redo or not (out / (i + ".mp3")).exists()]
    chars = sum(len(spoken(segs[ids.index(i)], say)) for i in todo)
    key, _ = need_key(a)
    left, _ = credits_left(key)
    print("Narrator %s. %d of %d segments to voice, %s characters (about %s credits a take)%s."
          % (narr.get("voice"), len(todo), len(want), format(chars, ","), format(chars, ","),
             "" if left is None else ", %s credits left" % format(left, ",")))
    if left is not None and chars > left and not a.force:
        stop("not enough credits for these segments. Voice fewer (--only) or wait for the reset (--force to try anyway).")
    if a.dry_run:
        return
    model = None if a.no_check else whisper()
    if model is None and not a.no_check:
        print("(faster-whisper isn't installed, so no word check: listen to the takes. pip3 install faster-whisper)")
    base = int(narr.get("seed", 1941))
    for sid in want:
        k = ids.index(sid)
        s = segs[k]
        dest = out / (sid + ".mp3")
        sent = spoken(s, say)
        if sid in todo:
            best = None
            for take in range(1, max(1, a.takes) + 1):
                audio, wt = make_take(key, s, segs, say, narr, k, base + k + 1000 * (take - 1))
                part = out / (sid + ".take%d.mp3" % take)
                part.write_bytes(audio)
                row = {"file": dest.name, "sent": sent, "text": s["narration"], "seconds": mp3_seconds(part),
                       "words": wt, "take": take}
                if model:
                    h = heard(model, part)
                    row.update(heard=h, wer=round(wer(sent, h), 3), cer=round(cer(sent, h), 3))
                    row["flag"] = row["wer"] > WER_LIMIT and row["cer"] > CER_LIMIT
                if best is None or (model and row.get("wer", 1) < best[1].get("wer", 1)):
                    if best:
                        best[0].unlink(missing_ok=True)
                    best = (part, row)
                else:
                    part.unlink(missing_ok=True)
                if not model or not best[1]["flag"]:
                    break
                print("  %s take %d misread (heard \"%s\"), trying again" % (sid, take, row.get("heard", "")[:80]))
            best[0].replace(dest)
            rep["segments"][sid] = best[1]
            rep_path.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
        row = rep["segments"].get(sid, {})
        note = ""
        if "wer" in row:
            note = "  heard ok" if not row.get("flag") else "  LISTEN: heard \"%s\"" % row.get("heard", "")[:90]
        print("%-10s %6.2fs%s%s" % (sid, row.get("seconds", 0), "" if sid in todo else "  (already made)", note))
    flagged = [i for i in want if rep["segments"].get(i, {}).get("flag")]
    print("\nListen to: %s. Then tell Claude what sounds wrong." % ", ".join(flagged) if flagged else "")
    print("Done: %d segments in %s/. Tell Claude the voice is ready." % (len(want), out))


def main():
    ap = argparse.ArgumentParser(description="Narration for a long-form video (ElevenLabs), run in your own Terminal.")
    ap.add_argument("command", nargs="?", default="make", choices=["make", "setup", "check"])
    ap.add_argument("--manifest", default="manifest.json")
    ap.add_argument("--say", default="say.json")
    ap.add_argument("--out", default="voice")
    ap.add_argument("--only", help="comma-separated segment ids (a pilot, or a fix)")
    ap.add_argument("--redo", action="store_true", help="voice these segments again even if they exist")
    ap.add_argument("--takes", type=int, default=3, help="most takes per segment when Whisper flags a misreading")
    ap.add_argument("--env", help="a file holding ELEVENLABS_API_KEY=...")
    ap.add_argument("--no-check", action="store_true", help="skip the Whisper word check")
    ap.add_argument("--dry-run", action="store_true", help="count the characters and stop")
    ap.add_argument("--force", action="store_true", help="try even when the credits look short")
    a = ap.parse_args()
    {"make": cmd_make, "setup": cmd_setup, "check": cmd_check}[a.command](a)


if __name__ == "__main__":
    main()
